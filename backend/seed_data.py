"""Populate the DB with a small, realistic sample so the frontend has
something to show without needing a data.gov.in API key. Run:
    python seed_data.py

NOTE: this calls db.drop_all()/create_all() directly and is only meant
for local/demo use. For any real deployment, manage the schema with
Flask-Migrate instead (`flask db upgrade`) so you get versioned,
reversible migrations instead of a full table drop:
    flask db upgrade        # apply migrations/versions/*
"""
from datetime import date, timedelta
import random

from app import create_app
from extensions import db
from models import Crop, District, Market, PriceRecord, State

app = create_app()

SAMPLE = {
    "Telangana": {
        "hi": "तेलंगाना", "te": "తెలంగాణ",
        "districts": {
            "Hyderabad": {"hi": "हैदराबाद", "te": "హైదరాబాద్", "markets": ["Bowenpally", "Malakpet"]},
            "Warangal": {"hi": "वारंगल", "te": "వరంగల్", "markets": ["Warangal Market Yard"]},
        },
    },
    "Maharashtra": {
        "hi": "महाराष्ट्र", "te": "మహారాష్ట్ర",
        "districts": {
            "Pune": {"hi": "पुणे", "te": "పూణే", "markets": ["Pune APMC"]},
            "Nashik": {"hi": "नासिक", "te": "నాసిక్", "markets": ["Nashik APMC"]},
        },
    },
}

CROPS = [
    {"en": "Tomato", "hi": "टमाटर", "te": "టమాటా", "category": "vegetable", "base": 1400},
    {"en": "Onion", "hi": "प्याज", "te": "ఉల్లిపాయ", "category": "vegetable", "base": 1800},
    {"en": "Rice", "hi": "चावल", "te": "బియ్యం", "category": "cereal", "base": 2200},
    {"en": "Cotton", "hi": "कपास", "te": "పత్తి", "category": "cash_crop", "base": 6500},
    {"en": "Chilli", "hi": "मिर्च", "te": "మిర్చి", "category": "spice", "base": 9500},
]


def run():
    with app.app_context():
        db.drop_all()
        db.create_all()

        crops = {}
        for c in CROPS:
            crop = Crop(name_en=c["en"], name_hi=c["hi"], name_te=c["te"], category=c["category"])
            db.session.add(crop)
            db.session.flush()
            crops[c["en"]] = (crop, c["base"])

        for state_name, sdata in SAMPLE.items():
            state = State(name_en=state_name, name_hi=sdata["hi"], name_te=sdata["te"])
            db.session.add(state)
            db.session.flush()

            for dist_name, ddata in sdata["districts"].items():
                district = District(
                    name_en=dist_name, name_hi=ddata["hi"], name_te=ddata["te"], state_id=state.id
                )
                db.session.add(district)
                db.session.flush()

                for market_name in ddata["markets"]:
                    market = Market(name_en=market_name, district_id=district.id)
                    db.session.add(market)
                    db.session.flush()

                    # last 14 days of prices per crop, with a little random walk
                    for crop_name, (crop, base) in crops.items():
                        price = base
                        for days_ago in range(13, -1, -1):
                            price += random.randint(-80, 80)
                            price = max(price, 100)
                            modal = price
                            record = PriceRecord(
                                market_id=market.id,
                                crop_id=crop.id,
                                variety="Local",
                                grade="FAQ",
                                min_price=modal - random.randint(20, 100),
                                max_price=modal + random.randint(20, 100),
                                modal_price=modal,
                                price_date=date.today() - timedelta(days=days_ago),
                                source="seed-demo",
                            )
                            db.session.add(record)

        db.session.commit()
        print("Seed data inserted.")


if __name__ == "__main__":
    run()
