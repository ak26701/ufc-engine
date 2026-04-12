"""
Entry point for the UFC archetype clustering pipeline.

Usage
-----
    python ml/run.py

Runs UMAP + HDBSCAN clustering on fighter feature vectors from the
fighter_features table and saves results to:
  - fighter_archetypes table in Neon PostgreSQL
  - data/processed/archetypes.parquet

Requires fighter_features to be populated first:
    python pipeline/run.py
"""

from __future__ import annotations

import os
import sys
import time

# Allow running as `python ml/run.py` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.features import get_connection
from ml.archetypes import run_clustering


def main() -> None:
    t0 = time.time()

    conn = get_connection()
    try:
        df = run_clustering(conn)
    finally:
        conn.close()

    elapsed = time.time() - t0
    print(f"\nFinished in {elapsed:.1f}s")
    print(f"Parquet  : data/processed/archetypes.parquet")
    print(f"DB table : fighter_archetypes")


if __name__ == "__main__":
    main()
