from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from extensions import cache, db, limiter
from models import Crop, District, Market, PriceRecord, State
from utils.anomaly import find_anomalies
from utils.forecast import forecast_prices

prices_bp = Blueprint("prices", __name__, url_prefix="/api")

ALLOWED_LANGS = {"en", "hi", "te"}


def _lang():
    lang = request.args.get("lang", "en")
    return lang if lang in ALLOWED_LANGS else "en"


def _cache_key():
    """Cache key includes every querystring param so different filters
    don't collide, but stays short-lived via CACHE_DEFAULT_TIMEOUT."""
    return f"prices:{request.query_string.decode()}"


@prices_bp.route("/states", methods=["GET"])
@cache.cached(timeout=6 * 60 * 60)  # states change essentially never
def list_states():
    lang = _lang()
    states = State.query.order_by(State.name_en).all()
    return jsonify([
        {"id": s.id, "name": getattr(s, f"name_{lang}") or s.name_en}
        for s in states
    ])


@prices_bp.route("/districts", methods=["GET"])
@cache.cached(timeout=6 * 60 * 60, query_string=True)
def list_districts():
    lang = _lang()
    state_id = request.args.get("state_id", type=int)
    q = District.query
    if state_id:
        q = q.filter_by(state_id=state_id)
    districts = q.order_by(District.name_en).all()
    return jsonify([
        {"id": d.id, "name": getattr(d, f"name_{lang}") or d.name_en, "state_id": d.state_id}
        for d in districts
    ])


@prices_bp.route("/crops", methods=["GET"])
@cache.cached(timeout=6 * 60 * 60, query_string=True)
def list_crops():
    lang = _lang()
    category = request.args.get("category")
    q = Crop.query
    if category:
        q = q.filter_by(category=category)
    crops = q.order_by(Crop.name_en).all()
    return jsonify([
        {
            "id": c.id,
            "name": getattr(c, f"name_{lang}") or c.name_en,
            "category": c.category,
        }
        for c in crops
    ])


@prices_bp.route("/prices", methods=["GET"])
@limiter.limit("60 per minute")
@cache.cached(timeout=15 * 60, query_string=True)  # mandi prices refresh ~daily, 15 min cache is safe
def get_prices():
    """
    Query params:
      crop_id, district_id, state_id  -> filters
      date=YYYY-MM-DD                 -> defaults to latest available date
      lang=en|hi|te
      page, per_page
    """
    lang = _lang()
    crop_id = request.args.get("crop_id", type=int)
    district_id = request.args.get("district_id", type=int)
    state_id = request.args.get("state_id", type=int)
    price_date_str = request.args.get("date")
    page = request.args.get("page", default=1, type=int)
    per_page = min(request.args.get("per_page", default=50, type=int), 200)

    q = PriceRecord.query.join(Market).join(District).join(State)

    if crop_id:
        q = q.filter(PriceRecord.crop_id == crop_id)
    if district_id:
        q = q.filter(Market.district_id == district_id)
    if state_id:
        q = q.filter(District.state_id == state_id)

    if price_date_str:
        try:
            target_date = date.fromisoformat(price_date_str)
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
        q = q.filter(PriceRecord.price_date == target_date)
    else:
        # default: most recent date that actually has data for this filter
        latest = q.with_entities(db.func.max(PriceRecord.price_date)).scalar()
        if latest is None:
            return jsonify({"results": [], "page": page, "per_page": per_page, "total": 0})
        q = q.filter(PriceRecord.price_date == latest)

    total = q.count()
    records = (
        q.order_by(PriceRecord.modal_price.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify(
        {
            "results": [r.to_dict(lang=lang) for r in records],
            "page": page,
            "per_page": per_page,
            "total": total,
        }
    )


@prices_bp.route("/prices/trend", methods=["GET"])
@cache.cached(timeout=30 * 60, query_string=True)
def price_trend():
    """7/30 day trend for one crop at one market — powers a small sparkline
    on the frontend so a farmer can see if prices are rising or falling."""
    crop_id = request.args.get("crop_id", type=int)
    market_id = request.args.get("market_id", type=int)
    days = min(request.args.get("days", default=30, type=int), 90)

    if not (crop_id and market_id):
        return jsonify({"error": "crop_id and market_id are required"}), 400

    since = date.today() - timedelta(days=days)
    records = (
        PriceRecord.query.filter(
            PriceRecord.crop_id == crop_id,
            PriceRecord.market_id == market_id,
            PriceRecord.price_date >= since,
        )
        .order_by(PriceRecord.price_date.asc())
        .all()
    )
    return jsonify(
        [{"date": r.price_date.isoformat(), "modal_price": float(r.modal_price or 0)} for r in records]
    )


@prices_bp.route("/prices/anomalies", methods=["GET"])
@limiter.limit("30 per minute")
@cache.cached(timeout=15 * 60, query_string=True)
def price_anomalies():
    """Flags today's (or a given date's) prices that deviate sharply from
    each market's own trailing 7-day average — a cheap, explainable
    signal for stale/bad ingestion rows or possible middleman price
    manipulation, without needing a trained model."""
    lang = _lang()
    state_id = request.args.get("state_id", type=int)
    district_id = request.args.get("district_id", type=int)
    price_date_str = request.args.get("date")
    deviation_pct = request.args.get(
        "deviation_pct", default=current_app.config["ANOMALY_DEVIATION_PCT"], type=float
    )

    q = PriceRecord.query.join(Market).join(District).join(State)
    if district_id:
        q = q.filter(Market.district_id == district_id)
    elif state_id:
        q = q.filter(District.state_id == state_id)

    if price_date_str:
        try:
            target_date = date.fromisoformat(price_date_str)
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    else:
        target_date = q.with_entities(db.func.max(PriceRecord.price_date)).scalar()
        if target_date is None:
            return jsonify({"anomalies": [], "date": None})

    records = q.filter(PriceRecord.price_date == target_date).all()
    flagged = find_anomalies(records, deviation_pct=deviation_pct)

    return jsonify(
        {
            "date": target_date.isoformat(),
            "deviation_threshold_pct": deviation_pct,
            "anomalies": [
                {
                    **f["record"].to_dict(lang=lang),
                    "baseline_avg_price": f["baseline_avg_price"],
                    "deviation_pct": f["deviation_pct"],
                }
                for f in flagged
            ],
        }
    )


@prices_bp.route("/prices/forecast", methods=["GET"])
@limiter.limit("30 per minute")
@cache.cached(timeout=60 * 60, query_string=True)
def price_forecast():
    """Short-term linear-trend projection for one crop at one market.
    Explicitly a directional signal (see utils/forecast.py docstring),
    not a precise price prediction — the `confidence` field reflects
    that and should be surfaced in the UI, not hidden."""
    crop_id = request.args.get("crop_id", type=int)
    market_id = request.args.get("market_id", type=int)
    days_ahead = min(
        request.args.get("days_ahead", default=7, type=int),
        current_app.config["FORECAST_MAX_DAYS"],
    )
    history_days = min(request.args.get("history_days", default=30, type=int), 90)

    if not (crop_id and market_id):
        return jsonify({"error": "crop_id and market_id are required"}), 400

    since = date.today() - timedelta(days=history_days)
    records = (
        PriceRecord.query.filter(
            PriceRecord.crop_id == crop_id,
            PriceRecord.market_id == market_id,
            PriceRecord.price_date >= since,
        )
        .order_by(PriceRecord.price_date.asc())
        .all()
    )
    history = [(r.price_date, float(r.modal_price) if r.modal_price is not None else None) for r in records]
    forecast = forecast_prices(history, days_ahead=days_ahead)

    return jsonify(
        {
            "crop_id": crop_id,
            "market_id": market_id,
            "history_points_used": len(history),
            "forecast": forecast,
            "note": "Directional linear-trend estimate, not a guaranteed price. See 'confidence' per point.",
        }
    )


@prices_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
