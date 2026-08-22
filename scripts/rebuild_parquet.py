"""Force a full BigQuery → Parquet cache rebuild.

A restart is NOT enough after adding a column: `_load_data` in backend/main.py
rehydrates whatever Parquet is already on disk. This runs the same path the
hourly background refresh uses (`create_data_service` → `save_parquet_cache`),
so the cache ends up exactly as a real refresh would leave it.

    python scripts/rebuild_parquet.py
"""

import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    from backend.config import settings
    from backend.services import create_data_service, save_parquet_cache
    from backend.services import parquet_cache as pc

    print(f"source: {settings.BQ_PROJECT_ID}.{settings.BQ_DATASET}.{settings.BQ_TABLE}")
    print(f"target: {settings.DUCKDB_PARQUET_PATH}")

    svc = create_data_service()
    save_parquet_cache(svc)

    fp_path = Path(settings.DUCKDB_PARQUET_PATH)
    meta = pc.get_metadata(fp_path)
    print(f"\nrows:    {meta['row_count']:,}")
    print(f"columns: {len(meta['columns'])}")
    print(f"written: {meta['written_at']}")
    print(f"size:    {fp_path.stat().st_size / 1024 / 1024:.0f} MB")


if __name__ == "__main__":
    main()
