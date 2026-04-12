"""
Archetype clustering module for UFC fight analytics.

Uses UMAP for dimensionality reduction and HDBSCAN for density-based clustering
to assign each fighter a style archetype based on their feature vector.

Pipeline
--------
1. load_features       — pull fighter_features + fighters metadata from Neon
2. normalize_features  — StandardScaler on 19 numeric feature columns
3. run_umap            — 2D embedding (viz) + 10D embedding (clustering)
4. run_hdbscan         — density clusters on the 10D embedding
5. label_archetypes    — heuristic archetype names from cluster centroids
6. save_archetypes     — upsert fighter_archetypes table + parquet export
7. run_clustering      — orchestrates the full pipeline
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Tuple

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler

# Suppress noisy numba / umap deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import umap
import hdbscan

# Allow running as `python ml/archetypes.py` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.features import FEATURE_COLS

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_PARQUET = "data/processed/archetypes.parquet"

DDL_FIGHTER_ARCHETYPES = """
CREATE TABLE IF NOT EXISTS fighter_archetypes (
    fighter_id     INT PRIMARY KEY REFERENCES fighters(id),
    archetype_id   INT,
    archetype_name TEXT,
    umap_x         FLOAT,
    umap_y         FLOAT,
    computed_at    TIMESTAMP DEFAULT NOW()
);
"""

# ---------------------------------------------------------------------------
# 1. Load features
# ---------------------------------------------------------------------------

def load_features(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    """
    Join fighter_features with the fighters table to produce a DataFrame
    with fighter_id, name, weight_class, and all 19 FEATURE_COLS.

    Nulls in reach_in / height_in are filled with the per-weight-class median.
    """
    feature_cols_sql = ", ".join(f"ff.{c}" for c in FEATURE_COLS)

    query = f"""
        SELECT
            ff.fighter_id,
            fi.name,
            COALESCE(
                fi.weight_class,
                (
                    SELECT f.weight_class
                    FROM fights f
                    WHERE (f.fighter1_id = fi.id OR f.fighter2_id = fi.id)
                      AND f.weight_class IS NOT NULL
                    ORDER BY f.date DESC NULLS LAST
                    LIMIT 1
                )
            ) AS weight_class,
            ff.fights_used,
            {feature_cols_sql}
        FROM fighter_features ff
        JOIN fighters fi ON fi.id = ff.fighter_id
        ORDER BY ff.fighter_id
    """

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        raise ValueError("fighter_features table is empty — run pipeline/run.py first.")

    df = pd.DataFrame(rows, columns=["fighter_id", "name", "weight_class", "fights_used"] + FEATURE_COLS)

    # Fill reach_in / height_in with per-weight-class median
    for col in ("reach_in", "height_in"):
        medians = df.groupby("weight_class")[col].transform("median")
        # Fallback to global median if weight_class is null
        global_median = df[col].median()
        df[col] = df[col].fillna(medians).fillna(global_median)

    # Fill any remaining feature nulls with 0 (shouldn't happen but guards downstream)
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0.0)

    print(f"Loaded {len(df)} fighters from fighter_features.")
    return df


# ---------------------------------------------------------------------------
# 2. Normalize features
# ---------------------------------------------------------------------------

def normalize_features(df: pd.DataFrame) -> Tuple[np.ndarray, StandardScaler]:
    """
    Apply StandardScaler to the 19 FEATURE_COLS.

    Returns
    -------
    X_scaled : np.ndarray of shape (n_fighters, 19)
    scaler   : fitted StandardScaler (for inverse-transform if needed)
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[FEATURE_COLS].values.astype(float))
    return X_scaled, scaler


# ---------------------------------------------------------------------------
# 3. UMAP reduction
# ---------------------------------------------------------------------------

def run_umap(
    X_scaled: np.ndarray,
    n_components: int = 2,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    random_state: int = 42,
) -> np.ndarray:
    """
    Reduce X_scaled to n_components dimensions with UMAP.

    Call once with n_components=2 (visualization) and once with
    n_components=10 (clustering — more dimensions improve separation).
    """
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        random_state=random_state,
        low_memory=False,
    )
    embedding = reducer.fit_transform(X_scaled)
    print(f"UMAP {n_components}D embedding: shape {embedding.shape}")
    return embedding


# ---------------------------------------------------------------------------
# 4. HDBSCAN clustering
# ---------------------------------------------------------------------------

def run_hdbscan(
    X_umap_10d: np.ndarray,
    min_cluster_size: int = 8,
    min_samples: int = 3,
) -> np.ndarray:
    """
    Cluster the 10-dimensional UMAP embedding with HDBSCAN.

    Returns
    -------
    labels : np.ndarray of int, shape (n_fighters,)
             -1 = noise / outlier
    """
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(X_umap_10d)

    unique_labels, counts = np.unique(labels, return_counts=True)
    print("\nHDBSCAN cluster distribution:")
    for lbl, cnt in zip(unique_labels, counts):
        tag = "noise" if lbl == -1 else f"cluster {lbl}"
        print(f"  {tag:>12}: {cnt} fighters")
    print()

    return labels


# ---------------------------------------------------------------------------
# 5. Label archetypes
# ---------------------------------------------------------------------------

def label_archetypes(df: pd.DataFrame, labels: np.ndarray) -> dict:
    """
    Assign a human-readable archetype name to each cluster.

    For each cluster, compute mean feature values and apply priority-ordered
    heuristics to select the best matching archetype.

    Returns
    -------
    archetype_map : dict mapping cluster_id (int) -> archetype_name (str)
                    Cluster -1 always maps to "Unclassified".
    """
    archetype_map: dict[int, str] = {-1: "Unclassified"}

    unique_labels = sorted(set(labels))
    feature_arr = df[FEATURE_COLS].values.astype(float)

    # Build a dict of feature -> index for fast lookup
    col_idx = {c: i for i, c in enumerate(FEATURE_COLS)}

    def feat(centroid: np.ndarray, name: str) -> float:
        return centroid[col_idx[name]]

    for lbl in unique_labels:
        if lbl == -1:
            continue

        mask = labels == lbl
        centroid = feature_arr[mask].mean(axis=0)

        # Retrieve key features
        ctrl       = feat(centroid, "ctrl_pct")
        td         = feat(centroid, "td_eff")
        sub_att    = feat(centroid, "sub_att_per_min")
        ground     = feat(centroid, "ground_pct")
        sig        = feat(centroid, "sig_str_eff")
        dist       = feat(centroid, "distance_pct")
        kd         = feat(centroid, "kd_per_min")
        finish     = feat(centroid, "finish_rate")
        leg        = feat(centroid, "leg_pct")
        str_def    = feat(centroid, "str_defense")
        td_def     = feat(centroid, "td_defense")
        dec_rate   = feat(centroid, "decision_rate")

        # Global medians across all fighters (for relative comparisons)
        global_med = {c: float(np.median(feature_arr[:, col_idx[c]])) for c in FEATURE_COLS}
        gm = global_med  # shorthand

        # Priority-ordered heuristic rules
        # Each condition checks whether the cluster is notably above the median
        # on the defining dimensions.

        name: str

        if ctrl > gm["ctrl_pct"] * 1.3 and td > gm["td_eff"] * 1.2:
            name = "Wrestler"

        elif sub_att > gm["sub_att_per_min"] * 1.3 and ground > gm["ground_pct"] * 1.2:
            name = "Submission Grappler"

        elif (
            kd > gm["kd_per_min"] * 1.3
            and finish > gm["finish_rate"] * 1.2
            and sig > gm["sig_str_eff"] * 1.1
        ):
            name = "Power Puncher"

        elif (
            sig > gm["sig_str_eff"] * 1.15
            and dist > gm["distance_pct"] * 1.1
            and ctrl < gm["ctrl_pct"] * 0.9
        ):
            name = "Pressure Striker"

        elif leg > gm["leg_pct"] * 1.3 and dist > gm["distance_pct"] * 1.1:
            name = "Kickboxer"

        elif (
            str_def > gm["str_defense"] * 1.05
            and td_def > gm["td_defense"] * 1.05
            and finish < gm["finish_rate"] * 0.85
        ):
            name = "Counter Fighter"

        else:
            # No dominant dimension — balanced across styles
            name = "Complete Fighter"

        archetype_map[lbl] = name
        print(f"  Cluster {lbl:>2}: {name}")

    return archetype_map


# ---------------------------------------------------------------------------
# 6. Save archetypes
# ---------------------------------------------------------------------------

def save_archetypes(
    df: pd.DataFrame,
    labels: np.ndarray,
    archetype_names: dict,
    embedding_2d: np.ndarray,
    conn: psycopg2.extensions.connection,
    output_path: str = OUTPUT_PARQUET,
) -> pd.DataFrame:
    """
    Attach archetype labels and UMAP coordinates to df, upsert to DB,
    and save to parquet.

    Modifies df in-place (adds archetype_id, archetype_name, umap_x, umap_y)
    and returns the augmented DataFrame.
    """
    df = df.copy()
    df["archetype_id"]   = labels.astype(int)
    df["archetype_name"] = [archetype_names.get(lbl, "Unclassified") for lbl in labels]
    df["umap_x"]         = embedding_2d[:, 0].astype(float)
    df["umap_y"]         = embedding_2d[:, 1].astype(float)

    # --- Create table if needed ---
    with conn.cursor() as cur:
        cur.execute(DDL_FIGHTER_ARCHETYPES)
    conn.commit()

    # --- Upsert rows ---
    upsert_sql = """
        INSERT INTO fighter_archetypes
            (fighter_id, archetype_id, archetype_name, umap_x, umap_y, computed_at)
        VALUES
            (%(fighter_id)s, %(archetype_id)s, %(archetype_name)s,
             %(umap_x)s, %(umap_y)s, NOW())
        ON CONFLICT (fighter_id) DO UPDATE SET
            archetype_id   = EXCLUDED.archetype_id,
            archetype_name = EXCLUDED.archetype_name,
            umap_x         = EXCLUDED.umap_x,
            umap_y         = EXCLUDED.umap_y,
            computed_at    = NOW()
    """

    records = df[["fighter_id", "archetype_id", "archetype_name", "umap_x", "umap_y"]].to_dict("records")

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, upsert_sql, records)
    conn.commit()
    print(f"Upserted {len(records)} rows into fighter_archetypes.")

    # --- Save parquet ---
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    df.to_parquet(output_path, index=False)
    print(f"Saved archetypes to {output_path}")

    return df


# ---------------------------------------------------------------------------
# 7. Main pipeline entry point
# ---------------------------------------------------------------------------

def run_clustering(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    """
    Execute the full archetype clustering pipeline.

    Steps
    -----
    1. load_features
    2. normalize_features
    3. run_umap (2D for viz, 10D for clustering)
    4. run_hdbscan on 10D embedding
    5. label_archetypes
    6. save_archetypes (DB + parquet)

    Returns
    -------
    df : DataFrame with fighter_id, name, weight_class, all features,
         archetype_id, archetype_name, umap_x, umap_y
    """
    print("=" * 60)
    print("UFC Archetype Clustering Pipeline")
    print("=" * 60)

    # Step 1 — load
    df = load_features(conn)

    # Step 2 — normalize
    X_scaled, scaler = normalize_features(df)
    print(f"Feature matrix: {X_scaled.shape[0]} fighters × {X_scaled.shape[1]} features")

    # Step 3 — UMAP (2D for visualization, 10D for clustering)
    print("\nRunning UMAP (2D) ...")
    embedding_2d = run_umap(X_scaled, n_components=2, n_neighbors=15, min_dist=0.1, random_state=42)

    print("Running UMAP (10D) ...")
    embedding_10d = run_umap(X_scaled, n_components=10, n_neighbors=15, min_dist=0.1, random_state=42)

    # Step 4 — HDBSCAN
    print("Running HDBSCAN ...")
    labels = run_hdbscan(embedding_10d, min_cluster_size=8, min_samples=3)

    # Step 5 — label archetypes
    print("Labelling archetypes ...")
    archetype_names = label_archetypes(df, labels)

    # Step 6 — save
    print("\nSaving results ...")
    df = save_archetypes(df, labels, archetype_names, embedding_2d, conn)

    # --- Summary ---
    n_clustered = int((labels != -1).sum())
    n_noise     = int((labels == -1).sum())

    print("\n" + "=" * 60)
    print(f"Clustering complete.")
    print(f"  Total fighters : {len(df)}")
    print(f"  Clustered      : {n_clustered}")
    print(f"  Noise/outliers : {n_noise}")
    print("\nArchetype distribution:")

    dist = df["archetype_name"].value_counts()
    for archetype, count in dist.items():
        bar = "#" * int(count / max(dist) * 30)
        print(f"  {archetype:<25} {count:>4}  {bar}")

    print("=" * 60)

    return df
