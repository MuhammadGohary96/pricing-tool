from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATA_SOURCE: str = "mock"
    BQ_PROJECT_ID: str = "bf-data-dev-qz06"
    BQ_DATASET: str = "dbt_gohary"
    BQ_TABLE: str = "pricing_index_analysis"
    BQ_COMPETITOR_TABLE: str = "competitor_products_analysis"
    BQ_LOCATION: str = "EU"
    BF_CATALOG_URL: str = "https://catalog.breadfast.com/products"
    GOOGLE_CLIENT_ID: str = ""
    BF_CATALOG_TOKEN: str = ""
    CACHE_TTL_SECONDS: int = 900
    CORS_ORIGINS: list[str] = ["http://localhost:5174"]
    USE_DUCKDB: bool = True  # Feature flag: route filter queries through DuckDB
    DUCKDB_PARQUET_PATH: str = "cache/pricing_data/fp_grain.parquet"
    COMPETITOR_PARQUET_PATH: str = "cache/pricing_data/competitor_grain.parquet"
    # Parquet-only cache: rehydrate in-memory frames from Parquet on startup
    # instead of the legacy multi-GB pickle.
    USE_PARQUET_CACHE: bool = True

    # Hourly background auto-refresh. "Smart": each interval, a cheap BQ
    # table-metadata check runs first and the full pull happens only when the
    # source table changed since the last sync (non-blocking, hot-swapped).
    AUTO_REFRESH_ENABLED: bool = True
    REFRESH_INTERVAL_SECONDS: int = 3600

    TIER_ORDER: dict = {
        "Top+": 5, "Top": 4, "Medium": 3, "Low": 2, "Very Low": 1
    }
    ACTION_TYPES: dict = {
        "Needs Mapping": {"symbol": "\u2298", "priority": 1},
        "Review Match": {"symbol": "\u26A1", "priority": 2},
        "Needs Price Update": {"symbol": "\u27F3", "priority": 3},
        "Complete": {"symbol": "\u2713", "priority": 4},
    }

    class Config:
        env_file = ".env"


settings = Settings()

