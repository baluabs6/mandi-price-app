"""
Daily ingestion job: pulls the latest mandi price records from the
data.gov.in open dataset that mirrors Agmarknet ("Variety-wise Daily Market
Prices Data of Commodity") and upserts them into PostgreSQL.

Run this on a schedule (Azure Function timer trigger / cron container / GH
Actions scheduled workflow) — see .github/workflows/ingest.yml.

Get a free API key at https://data.gov.in/user/register and set it as
DATA_GOV_IN_API_KEY.
"""
import logging
import os
import sys
from datetime import date

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from extensions import cache, db  # noqa: E402
from models import Crop, District, Market, PriceRecord, State  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest")

API_URL = "https://api.data.gov.in/resource/{resource_id}"


def fetch_page(resource_id, api_key, offset=0, limit=1000):
    resp = requests.get(
        API_URL.format(resource_id=resource_id),
        params={
            "api-key": api_key,
            "format": "json",
            "offset": offset,
            "limit": limit,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_or_create_state(name_en):
    state = State.query.filter_by(name_en=name_en).first()
    if not state:
        state = State(name_en=name_en)
        db.session.add(state)
        db.session.flush()
    return state


def get_or_create_district(name_en, state):
    district = District.query.filter_by(name_en=name_en, state_id=state.id).first()
    if not district:
        district = District(name_en=name_en, state_id=state.id)
        db.session.add(district)
        db.session.flush()
    return district


def get_or_create_market(name_en, district):
    market = Market.query.filter_by(name_en=name_en, district_id=district.id).first()
    if not market:
        market = Market(name_en=name_en, district_id=district.id)
        db.session.add(market)
        db.session.flush()
    return market


def get_or_create_crop(name_en):
    crop = Crop.query.filter_by(name_en=name_en).first()
    if not crop:
        crop = Crop(name_en=name_en)
        db.session.add(crop)
        db.session.flush()
    return crop


def parse_price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_ingestion(app):
    api_key = app.config["DATA_GOV_IN_API_KEY"]
    resource_id = app.config["DATA_GOV_IN_RESOURCE_ID"]
    if not api_key:
        logger.warning("DATA_GOV_IN_API_KEY not set — skipping live ingestion.")
        return

    offset, limit, total_ingested = 0, 1000, 0
    with app.app_context():
        while True:
            payload = fetch_page(resource_id, api_key, offset=offset, limit=limit)
            records = payload.get("records", [])
            if not records:
                break

            for rec in records:
                try:
                    state = get_or_create_state(rec["state"])
                    district = get_or_create_district(rec["district"], state)
                    market = get_or_create_market(rec["market"], district)
                    crop = get_or_create_crop(rec["commodity"])

                    price_date = date.fromisoformat(
                        "-".join(reversed(rec["arrival_date"].split("/")))
                    )  # dd/mm/yyyy -> yyyy-mm-dd

                    price = PriceRecord(
                        market_id=market.id,
                        crop_id=crop.id,
                        variety=rec.get("variety"),
                        grade=rec.get("grade"),
                        min_price=parse_price(rec.get("min_price")),
                        max_price=parse_price(rec.get("max_price")),
                        modal_price=parse_price(rec.get("modal_price")),
                        price_date=price_date,
                        source="agmarknet",
                    )
                    db.session.add(price)
                    total_ingested += 1
                except Exception:
                    logger.exception("Skipping malformed record: %s", rec)

            db.session.commit()
            offset += limit
            if offset >= int(payload.get("total", 0)):
                break

        cache.clear()  # invalidate stale price API responses after ingest
    logger.info("Ingested %d price records.", total_ingested)


if __name__ == "__main__":
    flask_app = create_app(os.environ.get("FLASK_ENV", "production"))
    run_ingestion(flask_app)
