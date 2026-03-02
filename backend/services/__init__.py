from backend.config import settings


def create_data_service(startup_status: dict = None):
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
