from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_city_page_sets_correct_city():
    r = client.get("/city/delhi")
    assert r.status_code == 200
    assert "let CITY='Delhi';" in r.text


def test_city_page_case_insensitive():
    r = client.get("/city/DELHI")
    assert r.status_code == 200
    assert "let CITY='Delhi';" in r.text


def test_city_page_different_city():
    r = client.get("/city/mumbai")
    assert r.status_code == 200
    assert "let CITY='Mumbai';" in r.text


def test_city_page_unknown_slug_404s():
    r = client.get("/city/atlantis")
    assert r.status_code == 404
    assert "error" in r.json()


def test_dashboard_route_unchanged():
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "let CITY='Delhi';" in r.text
