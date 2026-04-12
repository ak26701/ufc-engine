"""
Entry point for the UFC feature engineering pipeline.

Usage
-----
    python pipeline/run.py

Computes recency-weighted style feature vectors for all Lightweight,
Welterweight, and Heavyweight fighters, then saves results to:
  - data/processed/features.parquet
  - fighter_features table in the Neon PostgreSQL database

Optional env overrides (all have sensible defaults):
  N_FIGHTS  — look-back window per fighter (default: 10)
  DECAY     — exponential decay factor     (default: 0.85)
"""

import os
import sys
import time

# Allow running as `python pipeline/run.py` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.features import (
    compute_all_features,
    get_connection,
    save_features,
    save_features_to_db,
)

TARGET_WEIGHT_CLASSES = ["lightweight", "welterweight", "heavyweight"]
OUTPUT_PARQUET = "data/processed/features.parquet"


def main() -> None:
    n_fights = int(os.environ.get("N_FIGHTS", 10))
    decay    = float(os.environ.get("DECAY", 0.85))

    print("=" * 60)
    print("UFC Feature Engineering Pipeline")
    print(f"  Weight classes : {TARGET_WEIGHT_CLASSES}")
    print(f"  Look-back (N)  : {n_fights}")
    print(f"  Decay factor   : {decay}")
    print("=" * 60)

    t0 = time.time()

    conn = get_connection()
    try:
        features_list = compute_all_features(
            conn,
            weight_classes=TARGET_WEIGHT_CLASSES,
            n_fights=n_fights,
            decay=decay,
        )

        if not features_list:
            print("\nNo features computed — check that the DB contains fight data.")
            return

        print(f"\nComputed features for {len(features_list)} fighters.")

        # Save to parquet
        save_features(features_list, output_path=OUTPUT_PARQUET)

        # Upsert into DB
        save_features_to_db(features_list, conn)

    finally:
        conn.close()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Parquet : {OUTPUT_PARQUET}")
    print(f"DB table: fighter_features")


if __name__ == "__main__":
    main()
