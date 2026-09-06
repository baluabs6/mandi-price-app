"""Lightweight linear-trend forecasting.

Deliberately plain least-squares over the last N days rather than a
real time-series model (ARIMA/Prophet/etc.) — mandi price series here
are short (a few weeks of daily points at best) and noisy, so a fitted
linear trend is honest about what it is (a short-term directional
signal, not a precise prediction) and needs no extra ML dependency.
Callers must treat the output as directional, not authoritative — the
API response includes a `confidence` field that drops with fewer points
and higher scatter, on purpose, so the frontend can show a caveat.
"""
from datetime import timedelta


def _least_squares(xs, ys):
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0, mean_y
    slope = num / den
    intercept = mean_y - slope * mean_x
    return slope, intercept


def forecast_prices(history, days_ahead: int):
    """`history` is a list of (date, modal_price) tuples, ascending by
    date. Returns a list of {date, predicted_price, confidence} dicts,
    or [] if there isn't enough history to say anything useful."""
    points = [(d, p) for d, p in history if p is not None]
    if len(points) < 3:
        return []

    base_date = points[0][0]
    xs = [(d - base_date).days for d, _ in points]
    ys = [p for _, p in points]

    slope, intercept = _least_squares(xs, ys)

    mean_y = sum(ys) / len(ys)
    variance = sum((y - mean_y) ** 2 for y in ys) / len(ys)
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    residual_variance = sum(r ** 2 for r in residuals) / len(residuals)
    fit_quality = 1 - (residual_variance / variance) if variance > 0 else 0
    fit_quality = max(0.0, min(1.0, fit_quality))

    last_date = points[-1][0]
    last_x = xs[-1]
    results = []
    for i in range(1, days_ahead + 1):
        x = last_x + i
        predicted = max(0.0, slope * x + intercept)
        # confidence decays the further out we project, scaled by fit quality
        confidence = round(fit_quality * max(0.0, 1 - (i / (days_ahead * 2))), 2)
        results.append(
            {
                "date": (last_date + timedelta(days=i)).isoformat(),
                "predicted_modal_price": round(predicted, 2),
                "confidence": confidence,
            }
        )
    return results
