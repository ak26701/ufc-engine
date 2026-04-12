"""
Feature engineering pipeline for UFC fight analytics.

Reads raw fight stats from Neon PostgreSQL and produces recency-weighted
style feature vectors per fighter. Normalization by fight time follows the
approach validated in the KTH paper on UFC outcome prediction.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Feature names (defines column order for parquet + DB)
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "sig_str_eff",
    "ctrl_pct",
    "td_eff",
    "sub_att_per_min",
    "kd_per_min",
    "finish_rate",
    "decision_rate",
    "distance_pct",
    "clinch_pct",
    "ground_pct",
    "head_pct",
    "leg_pct",
    "str_defense",
    "td_defense",
    "activity_rate",
    "reach_in",
    "height_in",
    "orthodox",
    "southpaw",
]

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection() -> psycopg2.extensions.connection:
    """Return a new psycopg2 connection using DATABASE_URL from env."""
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def ensure_fighter_features_table(conn: psycopg2.extensions.connection) -> None:
    """Create the fighter_features table if it does not already exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS fighter_features (
        fighter_id      INT PRIMARY KEY REFERENCES fighters(id),
        computed_at     TIMESTAMP DEFAULT NOW(),
        fights_used     INT,
        sig_str_eff     FLOAT,
        ctrl_pct        FLOAT,
        td_eff          FLOAT,
        sub_att_per_min FLOAT,
        kd_per_min      FLOAT,
        finish_rate     FLOAT,
        decision_rate   FLOAT,
        distance_pct    FLOAT,
        clinch_pct      FLOAT,
        ground_pct      FLOAT,
        head_pct        FLOAT,
        leg_pct         FLOAT,
        str_defense     FLOAT,
        td_defense      FLOAT,
        activity_rate   FLOAT,
        reach_in        FLOAT,
        height_in       FLOAT,
        orthodox        FLOAT,
        southpaw        FLOAT
    );
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


# ---------------------------------------------------------------------------
# Per-fight feature computation
# ---------------------------------------------------------------------------

def _safe_div(num: float, denom: float, fallback: float = 0.0) -> float:
    """Divide num by denom, returning fallback when denom is zero."""
    return num / denom if denom > 0 else fallback


def _compute_per_fight_features(row: dict, opp: dict, fight_time: float) -> dict:
    """
    Compute a single-fight feature dict for one fighter's row.

    Parameters
    ----------
    row       : fight_stats row for the focal fighter
    opp       : fight_stats row for the opponent in the same fight
    fight_time: duration of the fight in seconds (from fights.time_sec)
    """
    t = max(fight_time, 1.0)  # guard against 0-second fights

    ssl = float(row["sig_str_landed"] or 0)
    ssa = float(row["sig_str_attempted"] or 0)

    # sig_str_eff = (landed/attempted) * (landed/time)  — KTH paper key variable
    sig_str_eff = _safe_div(ssl, ssa) * _safe_div(ssl, t)

    ctrl_pct = _safe_div(float(row["ctrl_sec"] or 0), t)

    td_l = float(row["td_landed"] or 0)
    td_a = float(row["td_attempted"] or 0)
    td_eff = _safe_div(td_l, max(td_a, 1.0))

    minutes = t / 60.0
    sub_att_per_min = _safe_div(float(row["sub_att"] or 0), minutes)
    kd_per_min      = _safe_div(float(row["kd"] or 0),      minutes)

    activity_rate = _safe_div(float(row["total_str_landed"] or 0), t)

    sig_base     = max(ssl, 1.0)
    distance_pct = _safe_div(float(row["distance_landed"] or 0), sig_base)
    clinch_pct   = _safe_div(float(row["clinch_landed"]   or 0), sig_base)
    ground_pct   = _safe_div(float(row["ground_landed"]   or 0), sig_base)
    head_pct     = _safe_div(float(row["head_landed"]     or 0), sig_base)
    leg_pct      = _safe_div(float(row["leg_landed"]      or 0), sig_base)

    # Defensive features derived from opponent's attacking stats
    opp_ssl = float(opp.get("sig_str_landed") or 0)
    opp_ssa = float(opp.get("sig_str_attempted") or 0)
    str_defense = 1.0 - _safe_div(opp_ssl, max(opp_ssa, 1.0))

    opp_tdl = float(opp.get("td_landed") or 0)
    opp_tda = float(opp.get("td_attempted") or 0)
    td_defense = 1.0 - _safe_div(opp_tdl, max(opp_tda, 1.0))

    return {
        "sig_str_eff":     sig_str_eff,
        "ctrl_pct":        ctrl_pct,
        "td_eff":          td_eff,
        "sub_att_per_min": sub_att_per_min,
        "kd_per_min":      kd_per_min,
        "distance_pct":    distance_pct,
        "clinch_pct":      clinch_pct,
        "ground_pct":      ground_pct,
        "head_pct":        head_pct,
        "leg_pct":         leg_pct,
        "str_defense":     str_defense,
        "td_defense":      td_defense,
        "activity_rate":   activity_rate,
    }


# ---------------------------------------------------------------------------
# Main feature computation — single fighter
# ---------------------------------------------------------------------------

def compute_fighter_features(
    fighter_id: int,
    conn: psycopg2.extensions.connection,
    n_fights: int = 10,
    decay: float = 0.85,
) -> Optional[dict]:
    """
    Compute recency-weighted feature vector for a single fighter.

    Returns a dict of feature_name -> float, or None if the fighter has
    no recorded fight stats.
    """
    # ------------------------------------------------------------------
    # 1. Fetch the fighter's physical attributes
    # ------------------------------------------------------------------
    with conn.cursor() as cur:
        cur.execute(
            "SELECT height_in, reach_in, stance FROM fighters WHERE id = %s",
            (fighter_id,),
        )
        fighter_row = cur.fetchone()

    if fighter_row is None:
        return None

    reach_in  = fighter_row["reach_in"]
    height_in = fighter_row["height_in"]
    stance    = fighter_row["stance"] or ""

    orthodox = 1.0 if stance.lower() == "orthodox" else 0.0
    southpaw = 1.0 if stance.lower() == "southpaw" else 0.0

    # ------------------------------------------------------------------
    # 2. Fetch the last N fights (ordered most-recent first)
    # ------------------------------------------------------------------
    query = """
        SELECT
            fs.fight_id,
            fs.kd,
            fs.sig_str_landed,
            fs.sig_str_attempted,
            fs.total_str_landed,
            fs.td_landed,
            fs.td_attempted,
            fs.sub_att,
            fs.ctrl_sec,
            fs.head_landed,
            fs.body_landed,
            fs.leg_landed,
            fs.distance_landed,
            fs.clinch_landed,
            fs.ground_landed,
            fs.is_winner,
            f.time_sec,
            f.method,
            f.date
        FROM fight_stats fs
        JOIN fights f ON f.id = fs.fight_id
        WHERE fs.fighter_id = %s
          AND f.time_sec IS NOT NULL
          AND f.time_sec > 0
        ORDER BY f.date DESC NULLS LAST, fs.fight_id DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (fighter_id, n_fights))
        fight_rows = cur.fetchall()

    if not fight_rows:
        return None

    # ------------------------------------------------------------------
    # 3. Fetch opponent stats for each fight in one batch query
    # ------------------------------------------------------------------
    fight_ids = [r["fight_id"] for r in fight_rows]

    opp_query = """
        SELECT fight_id,
               sig_str_landed, sig_str_attempted,
               td_landed, td_attempted
        FROM fight_stats
        WHERE fight_id = ANY(%s)
          AND fighter_id != %s
    """
    with conn.cursor() as cur:
        cur.execute(opp_query, (fight_ids, fighter_id))
        opp_rows = cur.fetchall()

    # Index opponent rows by fight_id for O(1) lookup
    opp_by_fight: dict[int, dict] = {r["fight_id"]: r for r in opp_rows}

    # ------------------------------------------------------------------
    # 4. Compute per-fight features and assign exponential decay weights
    #    fight_rows is already sorted most-recent -> oldest
    # ------------------------------------------------------------------
    per_fight_features: list[dict] = []
    weights: list[float] = []

    for i, row in enumerate(fight_rows):
        fight_id   = row["fight_id"]
        fight_time = float(row["time_sec"] or 1)

        opp = opp_by_fight.get(fight_id)
        if opp is None:
            opp = {"sig_str_landed": 0, "sig_str_attempted": 0,
                   "td_landed": 0, "td_attempted": 0}

        pf = _compute_per_fight_features(row, opp, fight_time)
        per_fight_features.append(pf)
        weights.append(decay ** i)  # most recent gets weight 1.0

    weights_arr = np.array(weights, dtype=float)
    total_w = weights_arr.sum()

    # ------------------------------------------------------------------
    # 5. Weighted average of per-fight features
    # ------------------------------------------------------------------
    agg: dict[str, float] = {}
    for key in per_fight_features[0]:
        vals = np.array([pf[key] for pf in per_fight_features], dtype=float)
        agg[key] = float((vals * weights_arr).sum() / total_w)

    # ------------------------------------------------------------------
    # 6. Outcome-based features (finish_rate, decision_rate)
    #    Equal-weight across last N fights — binary flags don't benefit
    #    meaningfully from exponential weighting.
    # ------------------------------------------------------------------
    n = len(fight_rows)
    finish_count   = 0
    decision_count = 0

    for row in fight_rows:
        method    = (row["method"] or "").upper()
        is_winner = bool(row["is_winner"])
        if is_winner and ("KO" in method or "TKO" in method or "SUB" in method):
            finish_count += 1
        if "DEC" in method or "DECISION" in method:
            decision_count += 1

    agg["finish_rate"]   = finish_count   / n
    agg["decision_rate"] = decision_count / n

    # ------------------------------------------------------------------
    # 7. Append physical attributes (may be None for missing data)
    # ------------------------------------------------------------------
    agg["reach_in"]  = float(reach_in)  if reach_in  is not None else None
    agg["height_in"] = float(height_in) if height_in is not None else None
    agg["orthodox"]  = orthodox
    agg["southpaw"]  = southpaw

    return agg


# ---------------------------------------------------------------------------
# Batch computation across all fighters in target weight classes
# ---------------------------------------------------------------------------

def compute_all_features(
    conn: psycopg2.extensions.connection,
    weight_classes: list[str] | None = None,
    n_fights: int = 10,
    decay: float = 0.85,
) -> list[dict]:
    """
    Compute feature vectors for all fighters in the given weight classes.

    Parameters
    ----------
    conn          : active psycopg2 connection
    weight_classes: list of weight-class strings to filter on;
                    defaults to ["lightweight", "welterweight", "heavyweight"]
    n_fights      : look-back window per fighter
    decay         : exponential decay factor (most recent fight = 1.0)

    Returns
    -------
    List of dicts with keys: fighter_id, name, weight_class, features, fights_used
    """
    if weight_classes is None:
        weight_classes = ["lightweight", "welterweight", "heavyweight"]

    wc_lower = [wc.lower() for wc in weight_classes]

    # fighters.weight_class is often NULL in practice; derive the fighter's
    # primary weight class from their most recent fight instead.
    fighter_query = """
        SELECT
            fi.id,
            fi.name,
            recent.weight_class
        FROM fighters fi
        JOIN LATERAL (
            SELECT f.weight_class
            FROM fights f
            WHERE (f.fighter1_id = fi.id OR f.fighter2_id = fi.id)
              AND f.weight_class IS NOT NULL
            ORDER BY f.date DESC NULLS LAST
            LIMIT 1
        ) recent ON TRUE
        WHERE LOWER(recent.weight_class) = ANY(%s)
        ORDER BY fi.id
    """
    with conn.cursor() as cur:
        cur.execute(fighter_query, (wc_lower,))
        fighters = cur.fetchall()

    results: list[dict] = []
    total = len(fighters)
    print(f"Computing features for {total} fighters in {wc_lower} ...")

    for idx, fighter in enumerate(fighters, 1):
        fid  = fighter["id"]
        name = fighter["name"]
        wc   = fighter["weight_class"]

        feats = compute_fighter_features(fid, conn, n_fights=n_fights, decay=decay)

        if feats is None:
            print(f"  [{idx:>4}/{total}] SKIP  {name} ({wc}) — no fight data")
            continue

        # Count fights actually used (capped at n_fights)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM fight_stats fs
                JOIN fights f ON f.id = fs.fight_id
                WHERE fs.fighter_id = %s
                  AND f.time_sec IS NOT NULL AND f.time_sec > 0
                """,
                (fid,),
            )
            total_fights_row = cur.fetchone()

        fights_used = min(int(total_fights_row["cnt"]), n_fights)
        print(f"  [{idx:>4}/{total}] OK    {name} ({wc}) — {fights_used} fights")

        results.append(
            {
                "fighter_id":   fid,
                "name":         name,
                "weight_class": wc,
                "features":     feats,
                "fights_used":  fights_used,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_features(
    features_list: list[dict],
    output_path: str = "data/processed/features.parquet",
) -> None:
    """
    Persist feature vectors to a parquet file.

    Parameters
    ----------
    features_list : output of compute_all_features()
    output_path   : destination file path (directories created if necessary)
    """
    if not features_list:
        print("save_features: nothing to save — features_list is empty")
        return

    rows = []
    for item in features_list:
        row = {
            "fighter_id":   item["fighter_id"],
            "name":         item["name"],
            "weight_class": item["weight_class"],
            "fights_used":  item["fights_used"],
        }
        row.update(item["features"])
        rows.append(row)

    df = pd.DataFrame(rows)

    # Guarantee all expected feature columns exist (fill missing with NaN)
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = np.nan

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")


def save_features_to_db(
    features_list: list[dict],
    conn: psycopg2.extensions.connection,
) -> None:
    """
    Upsert feature vectors into the fighter_features table.

    Creates the table first if it does not exist.
    """
    if not features_list:
        print("save_features_to_db: nothing to save — features_list is empty")
        return

    ensure_fighter_features_table(conn)

    upsert_sql = f"""
        INSERT INTO fighter_features (
            fighter_id, computed_at, fights_used,
            {", ".join(FEATURE_COLS)}
        )
        VALUES (
            %(fighter_id)s, NOW(), %(fights_used)s,
            {", ".join(f"%({c})s" for c in FEATURE_COLS)}
        )
        ON CONFLICT (fighter_id) DO UPDATE SET
            computed_at = NOW(),
            fights_used = EXCLUDED.fights_used,
            {", ".join(f"{c} = EXCLUDED.{c}" for c in FEATURE_COLS)}
    """

    records = []
    for item in features_list:
        rec = {
            "fighter_id": item["fighter_id"],
            "fights_used": item["fights_used"],
        }
        for col in FEATURE_COLS:
            rec[col] = item["features"].get(col)  # None -> SQL NULL
        records.append(rec)

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, upsert_sql, records)
    conn.commit()
    print(f"Upserted {len(records)} rows into fighter_features")
