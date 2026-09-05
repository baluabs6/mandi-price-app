from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
cache = Cache()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
