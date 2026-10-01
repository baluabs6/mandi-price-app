"""Read-only database tools the assistant LLM can call.

Every tool wraps logic the REST API already has (latest prices, trend,
anomalies, forecast) so the assistant and the UI always agree on the
numbers. The model only chooses *which* tool to call and phrases the
result — it never computes or invents prices itself.

Tools take human-readable names (crop / state / district / market, in
English, Hindi or Telugu) and resolve them against the DB with
case-insensitive and fuzzy matching, because that's what the model has
from the farmer's question.
"""
from collections import defaultdict
from datetime import date, timedelta
from difflib import get_close_matches

from extensions import db
from models import Crop, District, Market, PriceRecord, State
from utils.anomaly import find_anomalies
from utils.forecast import forecast_prices

MAX_ROWS = 25

TOOL_DEFINITIONS = [
    {
        "name": "get_best_markets",
        "description": (
            "Find where a crop currently sells for the highest (or lowest) modal price. "
            "Returns each market's most recent price within the last 14 days, ranked. "
            "Use for 'where should I sell X', 'which market pays most for X', or any "
            "comparison across markets. Optionally narrow to a state or district."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop": {"type": "string", "description": "Crop name, e.g. 'Onion'"},
                "state": {"type": "string", "description": "Optional state name"},
                "district": {"type": "string", "description": "Optional district name"},
                "top_n": {"type": "integer", "description": "How many markets to return (default 5, max 10)"},
                "lowest": {"type": "boolean", "description": "Rank cheapest first instead of highest first"},
            },
            "required": ["crop"],
        },
    },
    {
        "name": "get_latest_prices",
        "description": (
            "Get the recent price records (last 14 days) for a crop, optionally in a "
            "specific state, district or market. Use for 'what is the price of X today'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop": {"type": "string"},
                "state": {"type": "string"},
                "district": {"type": "string"},
                "market": {"type": "string", "description": "Optional mandi name"},
            },
            "required": ["crop"],
        },
    },
    {
        "name": "get_price_trend",
        "description": (
            "Daily modal price history for a crop in one district (averaged over its markets) "
            "or one market. Use for 'is X rising or falling'. Requires district or market."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop": {"type": "string"},
                "district": {"type": "string"},
                "market": {"type": "string"},
                "days": {"type": "integer", "description": "History window, default 14, max 60"},
            },
            "required": ["crop"],
        },
    },
    {
        "name": "get_anomalies",
        "description": (
            "List today's unusual prices — those deviating sharply from the market's own "
            "trailing 7-day average. Use for 'is anything priced strangely', 'am I being "
            "quoted too low'. Optionally narrow to a state or district."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string"},
                "district": {"type": "string"},
            },
        },
    },
    {
        "name": "get_forecast",
        "description": (
            "Short-term directional price projection (simple linear trend, NOT a guarantee) "
            "for a crop at one market. Always mention the confidence value to the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crop": {"type": "string"},
                "market": {"type": "string"},
                "days_ahead": {"type": "integer", "description": "Default 7, max 14"},
            },
            "required": ["crop", "market"],
        },
    },
]


# --------------------------------------------------------------------------
# Name resolution
# --------------------------------------------------------------------------
def _resolve(model, name, extra_filter=None):
    """Return the row of `model` best matching `name` (en/hi/te), or None."""
    if not name or not str(name).strip():
        return None
    needle = str(name).strip().lower()
    q = model.query
    if extra_filter is not None:
        q = q.filter(extra_filter)
    rows = q.all()
    if not rows:
        return None

    def names(row):
        return [n for n in (row.name_en, getattr(row, "name_hi", None), getattr(row, "name_te", None)) if n]

    for row in rows:  # exact
        if any(n.lower() == needle for n in names(row)):
            return row
    for row in rows:  # substring either way
        if any(needle in n.lower() or n.lower() in needle for n in names(row)):
            return row
    lookup = {n.lower(): row for row in rows for n in names(row)}
    close = get_close_matches(needle, lookup.keys(), n=1, cutoff=0.75)
    return lookup[close[0]] if close else None


def _record_summary(r):
    return {
        "crop": r.crop.name_en,
        "market": r.market.name_en,
        "district": r.market.district.name_en,
        "state": r.market.district.state.name_en,
        "modal_price": float(r.modal_price) if r.modal_price is not None else None,
        "min_price": float(r.min_price) if r.min_price is not None else None,
        "max_price": float(r.max_price) if r.max_price is not None else None,
        "unit": "Rs/quintal",
        "date": r.price_date.isoformat(),
    }


def _scoped_query(crop, state, district, market=None, since=None):
    q = PriceRecord.query.join(Market).join(District).join(State).filter(PriceRecord.crop_id == crop.id)
    if market:
        q = q.filter(PriceRecord.market_id == market.id)
    if district:
        q = q.filter(Market.district_id == district.id)
    elif state:
        q = q.filter(District.state_id == state.id)
    if since:
        q = q.filter(PriceRecord.price_date >= since)
    return q


def _resolve_scope(args):
    """Resolve crop/state/district/market args. Returns (entities, error)."""
    crop = _resolve(Crop, args.get("crop"))
    if args.get("crop") and crop is None:
        return None, f"Unknown crop '{args.get('crop')}'"
    state = _resolve(State, args.get("state"))
    if args.get("state") and state is None:
        return None, f"Unknown state '{args.get('state')}'"
    district_filter = District.state_id == state.id if state else None
    district = _resolve(District, args.get("district"), district_filter)
    if args.get("district") and district is None:
        return None, f"Unknown district '{args.get('district')}'"
    market_filter = Market.district_id == district.id if district else None
    market = _resolve(Market, args.get("market"), market_filter)
    if args.get("market") and market is None:
        return None, f"Unknown market '{args.get('market')}'"
    return {"crop": crop, "state": state, "district": district, "market": market}, None


# --------------------------------------------------------------------------
# Tool implementations — each returns (result_dict, source_records)
# --------------------------------------------------------------------------
def _get_best_markets(args):
    ent, err = _resolve_scope(args)
    if err:
        return {"error": err}, []
    since = date.today() - timedelta(days=14)
    records = _scoped_query(ent["crop"], ent["state"], ent["district"], since=since).order_by(
        PriceRecord.price_date.desc()
    ).all()

    latest_per_market = {}
    for r in records:  # already newest-first, so first seen per market is its latest
        if r.modal_price is not None and r.market_id not in latest_per_market:
            latest_per_market[r.market_id] = r
    if not latest_per_market:
        return {"markets": [], "note": "No recent price data for this selection."}, []

    top_n = max(1, min(int(args.get("top_n") or 5), 10))
    ranked = sorted(
        latest_per_market.values(),
        key=lambda r: float(r.modal_price),
        reverse=not args.get("lowest"),
    )[:top_n]
    return {"markets": [_record_summary(r) for r in ranked]}, ranked


def _get_latest_prices(args):
    ent, err = _resolve_scope(args)
    if err:
        return {"error": err}, []
    since = date.today() - timedelta(days=14)
    records = (
        _scoped_query(ent["crop"], ent["state"], ent["district"], ent["market"], since=since)
        .order_by(PriceRecord.price_date.desc())
        .limit(MAX_ROWS)
        .all()
    )
    if not records:
        return {"records": [], "note": "No recent price data for this selection."}, []
    return {"records": [_record_summary(r) for r in records]}, records


def _get_price_trend(args):
    ent, err = _resolve_scope(args)
    if err:
        return {"error": err}, []
    if not (ent["district"] or ent["market"]):
        return {"error": "Provide a district or a market for the trend."}, []
    days = max(2, min(int(args.get("days") or 14), 60))
    since = date.today() - timedelta(days=days)
    records = (
        _scoped_query(ent["crop"], ent["state"], ent["district"], ent["market"], since=since)
        .order_by(PriceRecord.price_date.asc())
        .all()
    )
    by_day = defaultdict(list)
    for r in records:
        if r.modal_price is not None:
            by_day[r.price_date].append(float(r.modal_price))
    series = [{"date": d.isoformat(), "avg_modal_price": round(sum(v) / len(v), 2)} for d, v in sorted(by_day.items())]
    if not series:
        return {"series": [], "note": "No price history for this selection."}, []
    first, last = series[0]["avg_modal_price"], series[-1]["avg_modal_price"]
    change_pct = round((last - first) / first * 100, 1) if first else None
    return {"series": series, "change_pct_over_period": change_pct}, records[-MAX_ROWS:]


def _get_anomalies(args):
    ent, err = _resolve_scope(args)
    if err:
        return {"error": err}, []
    q = PriceRecord.query.join(Market).join(District).join(State)
    if ent["district"]:
        q = q.filter(Market.district_id == ent["district"].id)
    elif ent["state"]:
        q = q.filter(District.state_id == ent["state"].id)
    target = q.with_entities(db.func.max(PriceRecord.price_date)).scalar()
    if target is None:
        return {"anomalies": [], "note": "No price data."}, []
    flagged = find_anomalies(q.filter(PriceRecord.price_date == target).all())[:MAX_ROWS]
    return (
        {
            "date": target.isoformat(),
            "anomalies": [
                {
                    **_record_summary(f["record"]),
                    "baseline_avg_price": f["baseline_avg_price"],
                    "deviation_pct": f["deviation_pct"],
                }
                for f in flagged
            ],
        },
        [f["record"] for f in flagged],
    )


def _get_forecast(args, max_days=14):
    ent, err = _resolve_scope(args)
    if err:
        return {"error": err}, []
    if not ent["market"]:
        return {"error": "A market name is required for a forecast."}, []
    days_ahead = max(1, min(int(args.get("days_ahead") or 7), max_days))
    since = date.today() - timedelta(days=30)
    records = (
        _scoped_query(ent["crop"], None, None, ent["market"], since=since)
        .order_by(PriceRecord.price_date.asc())
        .all()
    )
    history = [(r.price_date, float(r.modal_price) if r.modal_price is not None else None) for r in records]
    points = forecast_prices(history, days_ahead=days_ahead)
    if not points:
        return {"forecast": [], "note": "Not enough history to forecast."}, []
    return (
        {
            "forecast": points,
            "history_points_used": len(history),
            "note": "Directional linear-trend estimate, not a guaranteed price.",
        },
        records[-3:],
    )


_TOOLS = {
    "get_best_markets": _get_best_markets,
    "get_latest_prices": _get_latest_prices,
    "get_price_trend": _get_price_trend,
    "get_anomalies": _get_anomalies,
    "get_forecast": _get_forecast,
}


class ToolRunner:
    """Executes tools for one assistant request and remembers which price
    records were returned, so the API can show the farmer its sources."""

    def __init__(self):
        self.sources = {}  # record id -> summary (de-duplicated)
        self.calls = 0

    def __call__(self, name, args):
        self.calls += 1
        fn = _TOOLS.get(name)
        if fn is None:
            return {"error": f"Unknown tool '{name}'"}
        try:
            result, records = fn(args if isinstance(args, dict) else {})
        except Exception:  # noqa: BLE001 - tool failures must reach the model as data, not crash the request
            db.session.rollback()
            return {"error": "Tool failed to run."}
        for r in records:
            self.sources[r.id] = _record_summary(r)
        return result

    def source_list(self, limit=10):
        rows = sorted(self.sources.values(), key=lambda s: s["date"], reverse=True)
        return rows[:limit]
