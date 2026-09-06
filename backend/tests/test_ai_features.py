from datetime import date


def test_anomalies_flags_the_tomato_spike(client, seeded):
    resp = client.get("/api/prices/anomalies")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["date"] == date.today().isoformat()
    crops_flagged = {a["crop"] for a in data["anomalies"]}
    assert "Tomato" in crops_flagged
    assert "Onion" not in crops_flagged  # onion was flat, shouldn't be flagged

    tomato_anomaly = next(a for a in data["anomalies"] if a["crop"] == "Tomato")
    assert tomato_anomaly["deviation_pct"] > 0
    assert tomato_anomaly["baseline_avg_price"] < tomato_anomaly["modal_price"]


def test_anomalies_respects_custom_threshold(client, seeded):
    # With an extremely high threshold nothing should be flagged
    resp = client.get("/api/prices/anomalies?deviation_pct=500")
    assert resp.get_json()["anomalies"] == []


def test_forecast_requires_crop_and_market(client, seeded):
    resp = client.get("/api/prices/forecast")
    assert resp.status_code == 400


def test_forecast_returns_points_with_confidence(client, seeded):
    resp = client.get(
        f"/api/prices/forecast?crop_id={seeded['tomato_id']}&market_id={seeded['market_id']}&days_ahead=5"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["history_points_used"] == 7
    assert len(data["forecast"]) == 5
    for point in data["forecast"]:
        assert "predicted_modal_price" in point
        assert 0.0 <= point["confidence"] <= 1.0


def test_forecast_insufficient_history_returns_empty(client, seeded, app):
    # A crop/market pair with no data at all
    resp = client.get(
        f"/api/prices/forecast?crop_id={seeded['onion_id']}&market_id=999999&days_ahead=5"
    )
    assert resp.status_code == 200
    assert resp.get_json()["forecast"] == []


def test_ask_without_api_key_falls_back_gracefully(client, seeded):
    """With no ANTHROPIC_API_KEY configured (the default in tests), the
    endpoint must still respond usefully instead of erroring."""
    resp = client.post("/api/ask", json={"question": "What is the tomato price?", "lang": "en"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["assistant_enabled"] is False
    assert "Tomato" in data["answer"] or "tomato" in data["answer"].lower()
    assert data["records_used"] > 0


def test_ask_requires_question(client, seeded):
    resp = client.post("/api/ask", json={})
    assert resp.status_code == 400


def test_ask_rejects_overly_long_question(client, seeded):
    resp = client.post("/api/ask", json={"question": "x" * 501})
    assert resp.status_code == 400


def test_ask_matches_crop_entity(client, seeded):
    resp = client.post("/api/ask", json={"question": "onion price in Hyderabad", "lang": "en"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["matched"]["crop"] == "Onion"
    assert data["matched"]["district"] == "Hyderabad"
