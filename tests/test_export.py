from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_export_csv_default():
    r = client.get("/api/export?city=Delhi")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    body = r.text
    header = body.splitlines()[0]
    assert "date" in header and "parameter" in header and "daily_mean" in header
    assert len(body.splitlines()) > 100


def test_export_json():
    r = client.get("/api/export?city=Mumbai&format=json")
    assert r.status_code == 200
    data = r.json()
    assert data["city"] == "Mumbai"
    assert data["rows"] > 0
    assert data["data"][0]["parameter"] in {"pm25", "pm10", "no2", "o3", "so2", "co"}


def test_export_unknown_city():
    r = client.get("/api/export?city=Atlantis")
    assert r.status_code == 404
    assert "error" in r.json()
