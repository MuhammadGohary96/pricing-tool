from backend.config import settings
import logging

logger = logging.getLogger(__name__)


def create_data_service(startup_status: dict = None):
    """Create data service by loading from BigQuery or mock data."""
    if settings.DATA_SOURCE == "bigquery":
        from backend.services.bigquery_service import BigQueryPricingDataService
        return BigQueryPricingDataService(
            project_id=settings.BQ_PROJECT_ID,
            dataset=settings.BQ_DATASET,
            table=settings.BQ_TABLE,
            location=settings.BQ_LOCATION,
            startup_status=startup_status,
        )
    else:
        from backend.services.mock_data_service import MockPricingDataService
        return MockPricingDataService()


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
