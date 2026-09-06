from datetime import date


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_states_empty(client):
    resp = client.get("/api/states")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_states_and_lang(client, seeded):
    resp = client.get("/api/states?lang=hi")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["name"] == "तेलंगाना"


def test_districts_filtered_by_state(client, seeded):
    resp = client.get(f"/api/districts?state_id={seeded['state_id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["name"] == "Hyderabad"


def test_crops_filtered_by_category(client, seeded):
    resp = client.get("/api/crops?category=vegetable")
    data = resp.get_json()
    assert len(data) == 2
    names = {c["name"] for c in data}
    assert names == {"Tomato", "Onion"}


def test_prices_default_latest_date(client, seeded):
    resp = client.get(f"/api/prices?crop_id={seeded['tomato_id']}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    assert data["results"][0]["date"] == date.today().isoformat()
    assert data["results"][0]["modal_price"] == 2800.0


def test_prices_bad_date_returns_400(client, seeded):
    resp = client.get("/api/prices?date=not-a-date")
    assert resp.status_code == 400


def test_prices_no_data_for_filter(client, seeded):
    resp = client.get("/api/prices?state_id=999999")
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 0


def test_price_trend(client, seeded):
    resp = client.get(
        f"/api/prices/trend?crop_id={seeded['tomato_id']}&market_id={seeded['market_id']}&days=30"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 7  # 6 stable days + today's spike


def test_price_trend_requires_params(client, seeded):
    resp = client.get("/api/prices/trend")
    assert resp.status_code == 400
