"""Rule-based anomaly detection for mandi prices.

Deliberately not a trained ML model: with ~14 days of history per
market/crop pair, a statistical outlier rule (deviation from a trailing
average) is more robust, explainable to a farmer, and needs zero
training data compared to something like an isolation forest. This is
exactly the kind of "flag a suspicious price" feature the README's
roadmap calls out for catching middleman manipulation or stale/bad
ingestion data.
"""
from datetime import date, timedelta

from models import PriceRecord


def _rolling_average(crop_id: int, market_id: int, before_date: date, window_days: int = 7):
    since = before_date - timedelta(days=window_days)
    rows = (
        PriceRecord.query.filter(
            PriceRecord.crop_id == crop_id,
            PriceRecord.market_id == market_id,
            PriceRecord.price_date >= since,
            PriceRecord.price_date < before_date,
        )
        .all()
    )
    prices = [float(r.modal_price) for r in rows if r.modal_price is not None]
    if not prices:
        return None
    return sum(prices) / len(prices)


def find_anomalies(records, deviation_pct: float = 25.0):
    """Given a list of PriceRecord (already loaded, e.g. for the latest
    date), return the subset that deviate from their own market's
    trailing 7-day average by more than `deviation_pct`, along with the
    computed baseline and % deviation for transparency."""
    flagged = []
    for r in records:
        if r.modal_price is None:
            continue
        baseline = _rolling_average(r.crop_id, r.market_id, r.price_date)
        if baseline is None or baseline == 0:
            continue
        current = float(r.modal_price)
        deviation = (current - baseline) / baseline * 100
        if abs(deviation) >= deviation_pct:
            flagged.append(
                {
                    "record": r,
                    "baseline_avg_price": round(baseline, 2),
                    "deviation_pct": round(deviation, 1),
                }
            )
    return flagged
