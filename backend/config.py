from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATA_SOURCE: str = "mock"
    BQ_PROJECT_ID: str = "bf-data-dev-qz06"
    BQ_DATASET: str = "dbt_gohary"
    BQ_TABLE: str = "pricing_index_analysis"
    BQ_LOCATION: str = "EU"
    BF_CATALOG_URL: str = "https://catalog.breadfast.com/products"
    GOOGLE_CLIENT_ID: str = ""
    BF_CATALOG_TOKEN: str = ""
    CACHE_TTL_SECONDS: int = 900
    CORS_ORIGINS: list[str] = ["http://localhost:5174"]

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

