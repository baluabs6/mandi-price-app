import os

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config_by_name
from extensions import cache, configure_cache_backend, cors, db, limiter, migrate
from logging_config import configure_logging
from routes.assistant import assistant_bp
from routes.prices import prices_bp


def create_app(env=None):
    env = env or os.environ.get("FLASK_ENV", "production")
    app = Flask(__name__)
    app.config.from_object(config_by_name[env])

    configure_logging(app)

    # Trust exactly N proxy hops (nginx in docker-compose / Azure Container
    # Apps ingress in prod) so request.remote_addr reflects the real client
    # IP for rate limiting, instead of the proxy's IP for every request.
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=app.config["TRUSTED_PROXY_COUNT"],
        x_proto=1,
        x_host=1,
    )

    configure_cache_backend(app)

    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    cors.init_app(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    limiter.init_app(app)

    app.register_blueprint(prices_bp)
    app.register_blueprint(assistant_bp)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "internal server error"}), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "rate limit exceeded", "detail": str(e.description)}), 429

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
