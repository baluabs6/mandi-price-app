import os
import sys
from datetime import timedelta


def _get_secret_key(env):
    """Fail loudly in production if SECRET_KEY isn't set, instead of
    silently running with a publicly-known default (was the #1 security
    gap in the original scaffold)."""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if env == "production":
        sys.exit(
            "FATAL: SECRET_KEY environment variable is not set. "
            "Refusing to start in production with a default key. "
            "Set SECRET_KEY (e.g. from Azure Key Vault / a GitHub secret)."
        )
    return "dev-only-insecure-key-do-not-use-in-prod"


class Config:
    """Base configuration, values pulled from environment variables so the
    same image can be deployed to dev / staging / prod (Azure) without
    rebuilding it."""

    SECRET_KEY = _get_secret_key(os.environ.get("FLASK_ENV", "production"))

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
    # CACHE_TYPE is resolved dynamically in extensions.py: falls back to an
    # in-memory cache if Redis is unreachable at startup, instead of the
    # whole API 500ing on every request when Redis has an outage.
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "RedisCache")
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 60 * 30))  # 30 min

    # --- Rate limiting (protects the public API from scraping) --------
    RATELIMIT_STORAGE_URI = REDIS_URL
    # Fail open (allow the request) rather than 500ing if the Redis-backed
    # limiter storage is unreachable — protects availability over the
    # (secondary) scraping-protection goal.
    RATELIMIT_SWALLOW_ERRORS = True
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = True
    RATELIMIT_IN_MEMORY_FALLBACK = ["200 per minute"]

    # --- CORS -----------------------------------------------------------
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

    # --- Trust exactly one reverse proxy hop (nginx / Azure Container
    # Apps ingress) so request.remote_addr / X-Forwarded-For based rate
    # limiting sees the real client IP instead of the proxy's IP.
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "1"))

    # --- Agmarknet ingestion job ----------------------------------------
    AGMARKNET_BASE_URL = os.environ.get(
        "AGMARKNET_BASE_URL", "https://agmarknet.gov.in"
    )
    DATA_GOV_IN_API_KEY = os.environ.get("DATA_GOV_IN_API_KEY", "")
    DATA_GOV_IN_RESOURCE_ID = os.environ.get(
        "DATA_GOV_IN_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070"
    )  # "Variety-wise Daily Market Prices Data of Commodity" dataset on data.gov.in

    # --- AI assistant (RAG over price data) ------------------------------
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    ASSISTANT_ENABLED = bool(ANTHROPIC_API_KEY)

    # --- Anomaly / forecast tuning ---------------------------------------
    ANOMALY_DEVIATION_PCT = float(os.environ.get("ANOMALY_DEVIATION_PCT", "25"))
    FORECAST_MAX_DAYS = int(os.environ.get("FORECAST_MAX_DAYS", "14"))

    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    # Default to a fast in-memory SQLite DB so `pytest` works out of the
    # box with no Postgres/Redis running; CI can still override with a
    # real Postgres via TEST_DATABASE_URL if it wants integration coverage.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )
    CACHE_TYPE = "NullCache"
    RATELIMIT_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
