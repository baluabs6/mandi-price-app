import logging

import redis
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])


def configure_cache_backend(app):
    """Probe Redis before wiring Flask-Caching to it. If Redis is down
    (or was never configured), fall back to an in-process cache instead
    of letting every cached endpoint 500. This is a deliberate trade-off:
    a cold in-memory cache per replica is worse for Postgres load, but
    it keeps the site up during a Redis outage, which matters more for a
    public transparency site than serving from a warm cache."""
    if app.config.get("CACHE_TYPE") == "RedisCache":
        try:
            client = redis.Redis.from_url(app.config["CACHE_REDIS_URL"], socket_connect_timeout=2)
            client.ping()
        except Exception:  # noqa: BLE001 - genuinely want to catch anything here
            logger.warning(
                "Redis unreachable at startup — falling back to in-memory cache. "
                "Rate limiting also falls back to in-memory (see RATELIMIT_IN_MEMORY_FALLBACK)."
            )
            app.config["CACHE_TYPE"] = "SimpleCache"
