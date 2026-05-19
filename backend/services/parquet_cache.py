"""
Parquet cache helpers for DuckDB-backed data service.

The Parquet file is read directly by DuckDB at query time (no pandas in the
hot path). We materialize it from either:
  - The existing pickle cache (one-time migration from pandas cache), or
  - A fresh BigQuery load.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to Parquet with snappy compression and 100K row groups.

    The atomic-rename pattern guards against half-written files when an
    in-flight DuckDB query opens the file mid-write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    t0 = time.time()
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        tmp,
        compression="snappy",
        row_group_size=100_000,
        use_dictionary=True,
    )
    os.replace(tmp, path)  # atomic rename
    size_mb = path.stat().st_size / 1024 / 1024
    logger.info(
        f"[Parquet] Wrote {path.name}: {len(df):,} rows, {size_mb:.0f} MB in {time.time() - t0:.1f}s"
    )

    # Write metadata sidecar
    meta = {
        "row_count": len(df),
        "columns": list(df.columns),
        "written_at": datetime.now().isoformat(),
    }
    meta_path = path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2))


def is_fresh(path: Path, max_age_hours: int = 24) -> bool:
    """Check if a Parquet file exists and is within the freshness window."""
    path = Path(path)
    if not path.exists():
        return False
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours < max_age_hours


def get_metadata(path: Path) -> dict | None:
    """Read sidecar metadata if available."""
    path = Path(path)
    meta_path = path.with_suffix(".json")
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except Exception:
        return None
