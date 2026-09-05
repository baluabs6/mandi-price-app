from datetime import date
from extensions import db


class State(db.Model):
    __tablename__ = "states"

    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(120), nullable=False, unique=True)
    name_hi = db.Column(db.String(120))
    name_te = db.Column(db.String(120))

    districts = db.relationship("District", backref="state", lazy=True)


class District(db.Model):
    __tablename__ = "districts"

    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(120), nullable=False)
    name_hi = db.Column(db.String(120))
    name_te = db.Column(db.String(120))
    state_id = db.Column(db.Integer, db.ForeignKey("states.id"), nullable=False)

    markets = db.relationship("Market", backref="district", lazy=True)

    __table_args__ = (db.UniqueConstraint("name_en", "state_id", name="uq_district_state"),)


class Market(db.Model):
    """A physical mandi (market yard)."""

    __tablename__ = "markets"

    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(160), nullable=False)
    name_hi = db.Column(db.String(160))
    name_te = db.Column(db.String(160))
    district_id = db.Column(db.Integer, db.ForeignKey("districts.id"), nullable=False)

    prices = db.relationship("PriceRecord", backref="market", lazy=True)


class Crop(db.Model):
    __tablename__ = "crops"

    id = db.Column(db.Integer, primary_key=True)
    name_en = db.Column(db.String(120), nullable=False, unique=True)
    name_hi = db.Column(db.String(120))
    name_te = db.Column(db.String(120))
    category = db.Column(db.String(80))  # cereal, pulse, vegetable, fruit, spice...

    prices = db.relationship("PriceRecord", backref="crop", lazy=True)


class PriceRecord(db.Model):
    """One row = one crop's price at one market on one day.
    This mirrors the shape of the Agmarknet / data.gov.in daily price feed."""

    __tablename__ = "price_records"

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey("markets.id"), nullable=False)
    crop_id = db.Column(db.Integer, db.ForeignKey("crops.id"), nullable=False)
    variety = db.Column(db.String(120))
    grade = db.Column(db.String(40))

    min_price = db.Column(db.Numeric(10, 2))  # Rs per quintal
    max_price = db.Column(db.Numeric(10, 2))
    modal_price = db.Column(db.Numeric(10, 2))  # the price farmers should anchor on

    price_date = db.Column(db.Date, nullable=False, default=date.today)
    source = db.Column(db.String(60), default="agmarknet")

    __table_args__ = (
        db.Index("ix_price_lookup", "crop_id", "market_id", "price_date"),
    )

    def to_dict(self, lang="en"):
        def name(obj):
            return getattr(obj, f"name_{lang}", None) or obj.name_en

        return {
            "id": self.id,
            "crop": name(self.crop),
            "variety": self.variety,
            "grade": self.grade,
            "market": name(self.market),
            "district": name(self.market.district),
            "state": name(self.market.district.state),
            "min_price": float(self.min_price) if self.min_price is not None else None,
            "max_price": float(self.max_price) if self.max_price is not None else None,
            "modal_price": float(self.modal_price) if self.modal_price is not None else None,
            "unit": "Rs/quintal",
            "date": self.price_date.isoformat(),
            "source": self.source,
        }
