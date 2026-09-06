import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app  # noqa: E402
from extensions import db as _db  # noqa: E402
from models import Crop, District, Market, PriceRecord, State  # noqa: E402


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seeded(app):
    """A small, deterministic dataset — enough to exercise filters,
    trends, anomalies and forecasting without depending on seed_data.py's
    randomness."""
    with app.app_context():
        state = State(name_en="Telangana", name_hi="तेलंगाना", name_te="తెలంగాణ")
        _db.session.add(state)
        _db.session.flush()

        district = District(name_en="Hyderabad", name_hi="हैदराबाद", state_id=state.id)
        _db.session.add(district)
        _db.session.flush()

        market = Market(name_en="Bowenpally", district_id=district.id)
        _db.session.add(market)
        _db.session.flush()

        tomato = Crop(name_en="Tomato", name_hi="टमाटर", category="vegetable")
        onion = Crop(name_en="Onion", name_hi="प्याज", category="vegetable")
        _db.session.add_all([tomato, onion])
        _db.session.flush()

        today = date.today()
        # Stable tomato prices for 6 days, then a spike today -> anomaly candidate
        for i, price in enumerate([1400, 1410, 1395, 1420, 1405, 1415]):
            _db.session.add(
                PriceRecord(
                    market_id=market.id,
                    crop_id=tomato.id,
                    modal_price=price,
                    min_price=price - 50,
                    max_price=price + 50,
                    price_date=today - timedelta(days=6 - i),
                    source="test",
                )
            )
        _db.session.add(
            PriceRecord(
                market_id=market.id,
                crop_id=tomato.id,
                modal_price=2800,  # ~100% spike vs ~1408 baseline
                min_price=2700,
                max_price=2900,
                price_date=today,
                source="test",
            )
        )
        # Onion: flat, no anomaly
        for i in range(5):
            _db.session.add(
                PriceRecord(
                    market_id=market.id,
                    crop_id=onion.id,
                    modal_price=1800,
                    min_price=1750,
                    max_price=1850,
                    price_date=today - timedelta(days=4 - i),
                    source="test",
                )
            )
        _db.session.commit()

        return {
            "state_id": state.id,
            "district_id": district.id,
            "market_id": market.id,
            "tomato_id": tomato.id,
            "onion_id": onion.id,
        }
