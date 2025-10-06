import json
from app import app

def test_route():
    client = app.test_client()
    response = client.post("/route", json={
        "origin": [-36.8485, 174.7633],
        "destination": [-36.8510, 174.7740],
        "hour": 9,
        "day": 1
    })
    data = json.loads(response.data)
    assert "eta_min" in data
    assert data["distance_km"] > 0
