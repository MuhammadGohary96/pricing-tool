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
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to Parquet with snappy compression and 100K row groups.

    Rows are sorted by `fp_name` first so DuckDB's zone-map pruning can skip
    most row groups when an FP filter is pushed down (the dominant filter
    pattern in this app). Within each FP, rows are sorted by sub_category_name
    so subcategory-filtered queries also benefit.

    The atomic-rename pattern guards against half-written files when an
    in-flight DuckDB query opens the file mid-write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    t0 = time.time()
    # Sort for zone-map effectiveness on hot-path filters
    sort_keys = [c for c in ("fp_name", "sub_category_name", "product_id") if c in df.columns]
    if sort_keys:
        df = df.sort_values(sort_keys, kind="mergesort").reset_index(drop=True)

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
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2))


def read_df(path: Path) -> pd.DataFrame:
    """Read a Parquet file back into a pandas DataFrame (no row-order guarantee).

    Used to rehydrate the in-memory pandas frames on startup instead of
    deserializing the old multi-GB pickle.
    """
    path = Path(path)
    t0 = time.time()
    df = pq.read_table(path).to_pandas()
    size_mb = path.stat().st_size / 1024 / 1024
    logger.info(
        f"[Parquet] Read {path.name}: {len(df):,} rows, {size_mb:.0f} MB in {time.time() - t0:.1f}s"
    )
    return df


def exists(path: Path) -> bool:
    """True if the Parquet file is present (any age)."""
    return Path(path).exists()


def is_fresh(path: Path, max_age_hours: int = 24) -> bool:
    """Check if a Parquet file exists and is within the freshness window."""
    path = Path(path)
    if not path.exists():
        return False
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours < max_age_hours


def write_sync_state(
    cache_dir: Path,
    synced_at_iso: str,
    bq_table_modified_iso: str | None,
    last_checked_at_iso: str | None = None,
) -> None:
    """Record the last successful BigQuery PULL (data actually changed).

    `synced_at`         = when the data was materialized locally (tooltip / "data as of").
    `bq_table_modified` = source table's last-modified at that pull (change-detection baseline).
    `last_checked_at`   = when freshness was last verified; a pull IS a verification,
                          so it defaults to synced_at. (A no-change check advances only
                          this, via touch_last_checked.)
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "synced_at": synced_at_iso,
        "bq_table_modified": bq_table_modified_iso,
        "last_checked_at": last_checked_at_iso or synced_at_iso,
    }
    tmp = cache_dir / "sync_state.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, cache_dir / "sync_state.json")


def touch_last_checked(cache_dir: Path, checked_at_iso: str) -> None:
    """Record a freshness check that found NO change (data already current).
    Advances only `last_checked_at`, preserving synced_at + bq_table_modified."""
    cache_dir = Path(cache_dir)
    state = read_sync_state(cache_dir) or {}
    state["last_checked_at"] = checked_at_iso
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache_dir / "sync_state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, cache_dir / "sync_state.json")


def read_sync_state(cache_dir: Path) -> dict | None:
    """Read the last-sync marker, or None if absent/unreadable."""
    f = Path(cache_dir) / "sync_state.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def data_age_hours(path: Path) -> float | None:
    """Age of the data in hours, preferring the sidecar `written_at` (set when
    the Parquet was last materialized from a BigQuery fetch) over raw file
    mtime. Returns None if the file is absent. More robust than mtime alone —
    a non-fetch touch of the file won't masquerade as fresh data.
    """
    path = Path(path)
    if not path.exists():
        return None
    meta = get_metadata(path)
    if meta and meta.get("written_at"):
        try:
            written = datetime.fromisoformat(meta["written_at"])
            if written.tzinfo is None:
                # Legacy sidecars carry naive timestamps written in UTC.
                written = written.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - written).total_seconds() / 3600
        except Exception:
            pass
    return (time.time() - path.stat().st_mtime) / 3600


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
