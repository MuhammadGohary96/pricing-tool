from backend.config import settings
import logging

logger = logging.getLogger(__name__)


def latest_bq_modified(client):
    """Max last-modified timestamp across BOTH source tables — the pricing table
    AND the competitor table. The two are updated independently, so change
    detection must watch both: a refresh should fire when EITHER changes.

    Returns a tz-aware datetime, or None if neither table's metadata is readable
    (callers treat None as "couldn't determine" rather than "unchanged").
    """
    if client is None:
        return None
    latest = None
    for table in (settings.BQ_TABLE, settings.BQ_COMPETITOR_TABLE):
        if not table:
            continue
        try:
            tbl = client.get_table(f"{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET}.{table}")
            m = tbl.modified
            if m is not None and (latest is None or m > latest):
                latest = m
        except Exception as exc:
            logger.warning(f"[Sync] Could not read modified time for {table}: {exc}")
    return latest


def _upgrade_to_duckdb(service, parquet_from_source: bool = False):
    """Re-class an existing BigQueryPricingDataService instance into a
    DuckDBPricingDataService and attach the DuckDB connection.

    parquet_from_source=True means `_df` was just read FROM the fp-grain Parquet,
    so `_init_duckdb` must NOT rewrite it (the file is authoritative and its
    mtime drives the background-refresh staleness check). Cold/pickle loads pass
    False so the Parquet is (re)written to match the freshly-built `_df`.
    """
    from backend.services.duckdb_service import DuckDBPricingDataService

    service.__class__ = DuckDBPricingDataService
    service._parquet_path = __import__("pathlib").Path(settings.DUCKDB_PARQUET_PATH)
    service._max_parquet_age_hours = 24
    service._parquet_from_source = parquet_from_source
    service._duckdb_conn = None
    service._duckdb_lock = __import__("threading").Lock()
    service._init_duckdb()
    return service


def create_data_service(startup_status: dict = None):
    """Create data service by loading from BigQuery or mock data."""
    if settings.DATA_SOURCE == "bigquery":
        from backend.services.bigquery_service import BigQueryPricingDataService
        service = BigQueryPricingDataService(
            project_id=settings.BQ_PROJECT_ID,
            dataset=settings.BQ_DATASET,
            table=settings.BQ_TABLE,
            location=settings.BQ_LOCATION,
            startup_status=startup_status,
        )
        if settings.USE_DUCKDB:
            service = _upgrade_to_duckdb(service)
        return service
    else:
        from backend.services.mock_data_service import MockPricingDataService
        return MockPricingDataService()


def create_data_service_from_parquet():
    """Rehydrate the data service from the Parquet cache (no pickle).

    Reads `_df` from the fp-grain Parquet and `_competitor_df` from the
    competitor-grain Parquet, re-aggregates `_global_df`, then upgrades to
    DuckDB. Returns None if the fp-grain Parquet is absent (caller falls back).
    """
    if settings.DATA_SOURCE != "bigquery":
        return None

    from pathlib import Path
    import pandas as pd
    from backend.services import parquet_cache as pc
    from backend.services.bigquery_service import BigQueryPricingDataService

    fp_path = Path(settings.DUCKDB_PARQUET_PATH)
    if not pc.exists(fp_path):
        logger.info("[Parquet] No fp-grain Parquet found — cannot load from Parquet cache")
        return None

    service = BigQueryPricingDataService.__new__(BigQueryPricingDataService)
    from google.cloud import bigquery
    service._client = bigquery.Client(project=settings.BQ_PROJECT_ID, location=settings.BQ_LOCATION)
    service._project = settings.BQ_PROJECT_ID
    service._dataset = settings.BQ_DATASET
    service._table = settings.BQ_TABLE
    service._location = settings.BQ_LOCATION
    service._startup_status = None

    # The 4.9M-row pandas `_df` is NOT loaded on the serving path: DuckDB queries
    # the Parquet directly, now_price/now_sale_price come from the base SQL,
    # GLOBAL is served by `global_base`, and filter/fp options are SQL. Skipping
    # it frees ~300-400 MB RAM and the Parquet→pandas read. `_df` is rebuilt only
    # during a fresh BigQuery load (cold start / background refresh).
    service._df = None
    service._global_df = None

    # _competitor_df from competitor-grain Parquet (rebuild derived date cols).
    # Kept as pandas — small (~150K rows) and the competitor tab is pandas-based.
    comp_path = Path(settings.COMPETITOR_PARQUET_PATH)
    if pc.exists(comp_path):
        cdf = pc.read_df(comp_path)
        cdf = service._derive_competitor_date_cols(cdf)
        service._competitor_df = cdf.reset_index(drop=True)
    else:
        logger.warning("[Parquet] No competitor-grain Parquet — competitor tab will be empty until refresh")
        service._competitor_df = pd.DataFrame()

    logger.info(
        f"[Parquet] Loaded service from Parquet (no pandas _df): "
        f"{len(service._competitor_df):,} competitor rows; GLOBAL via DuckDB global_base"
    )

    if settings.USE_DUCKDB:
        service = _upgrade_to_duckdb(service, parquet_from_source=True)
    return service


def save_parquet_cache(service) -> None:
    """Persist the service's in-memory frames to the Parquet cache.

    Replaces the legacy multi-GB pickle. Writes the fp-grain Parquet (also the
    artifact DuckDB queries) and a competitor-grain Parquet (derived `*_date`
    columns dropped — they're rebuilt on load).
    """
    from datetime import datetime
    from pathlib import Path
    from backend.services import parquet_cache as pc

    fp_path = Path(settings.DUCKDB_PARQUET_PATH)
    pc.write_parquet(service._df, fp_path)

    comp = getattr(service, "_competitor_df", None)
    if comp is not None and not comp.empty:
        comp = comp.drop(
            columns=[c for c in comp.columns if c.endswith("_date")],
            errors="ignore",
        )
        pc.write_parquet(comp, Path(settings.COMPETITOR_PARQUET_PATH))

    # Record the sync marker (powers the UI "last synced" + the smart hourly
    # refresh's change-detection). Use the latest modified across BOTH source
    # tables so a competitor-table-only change is still captured.
    latest = latest_bq_modified(getattr(service, "_client", None))
    bq_modified_iso = latest.isoformat() if latest is not None else None
    pc.write_sync_state(fp_path.parent, datetime.now().isoformat(), bq_modified_iso)


def create_data_service_from_cache(cached_data: dict):
    """
    Create data service from cached DataFrames.

    Args:
        cached_data: Dictionary containing _df, _global_df, and optionally _competitor_df

    Returns:
        Initialized data service with cached data
    """
    if settings.DATA_SOURCE == "bigquery":
        from backend.services.bigquery_service import BigQueryPricingDataService

        # Create service without loading from BigQuery
        service = BigQueryPricingDataService.__new__(BigQueryPricingDataService)

        # Initialize basic attributes
        from google.cloud import bigquery
        service._client = bigquery.Client(
            project=settings.BQ_PROJECT_ID,
            location=settings.BQ_LOCATION
        )
        service._project = settings.BQ_PROJECT_ID
        service._dataset = settings.BQ_DATASET
        service._table = settings.BQ_TABLE
        service._location = settings.BQ_LOCATION
        service._startup_status = None

        # Load cached DataFrames
        service._df = cached_data["_df"]

        # Always re-aggregate _global_df with current aggregation logic
        # (cheap operation ~5s; ensures _global_df matches latest code)
        logger.info("[Cache] Re-aggregating _global_df with current logic...")
        import time
        t0 = time.time()
        service._global_df = service._aggregate_to_global(service._df)
        logger.info(
            f"[Cache] Re-aggregated _global_df: {len(service._global_df):,} rows "
            f"in {time.time() - t0:.1f}s"
        )

        if "_competitor_df" in cached_data:
            service._competitor_df = cached_data["_competitor_df"]
        else:
            # Initialize empty competitor df if not in cache
            import pandas as pd
            service._competitor_df = pd.DataFrame()

        logger.info(
            f"[Cache] Created service from cache: "
            f"{len(service._df):,} rows (FP grain), "
            f"{len(service._global_df):,} rows (GLOBAL)"
        )

        # If DuckDB flag is on, upgrade the service to DuckDBPricingDataService
        # in-place: copy state, then attach DuckDB connection
        if settings.USE_DUCKDB:
            service = _upgrade_to_duckdb(service)

        return service

    else:
        from backend.services.mock_data_service import MockPricingDataService

        # Create service and load cached data
        service = MockPricingDataService.__new__(MockPricingDataService)
        service._df = cached_data["_df"]
        service._global_df = cached_data["_global_df"]

        logger.info(
            f"[Cache] Created mock service from cache: "
            f"{len(service._df):,} rows"
        )

        return service
