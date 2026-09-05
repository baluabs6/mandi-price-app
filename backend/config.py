import os
from datetime import timedelta


class Config:
    """Base configuration, values pulled from environment variables so the
    same image can be deployed to dev / staging / prod (Azure) without
    rebuilding it."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-prod")

    # --- PostgreSQL -------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://mandi_user:mandi_pass@localhost:5432/mandi_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # --- Redis --------------------------------------------------------
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 60 * 30))  # 30 min

    # --- Rate limiting (protects the public API from scraping) --------
    RATELIMIT_STORAGE_URI = REDIS_URL

    # --- CORS -----------------------------------------------------------
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

    # --- Agmarknet ingestion job ----------------------------------------
    AGMARKNET_BASE_URL = os.environ.get(
        "AGMARKNET_BASE_URL", "https://agmarknet.gov.in"
    )
    DATA_GOV_IN_API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "")
    DATA_GOV_IN_RESOURCE_ID = os.environ.get(
        "DATA_GOV_IN_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070"
    )  # "Variety-wise Daily Market Prices Data of Commodity" dataset on data.gov.in

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://mandi_user:mandi_pass@localhost:5432/mandi_test_db"
    )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
