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


def test_dashboard_route_serves_summary_not_full_depth():
    """/dashboard is the generic, summary-only entry point (Phase 6G) — full
    depth (pollutants, health guidance, solutions, calendar, trend/forecast,
    chat) only exists on a specific /city/<slug> page."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert 'id="cities"' in r.text
    assert 'id="pollutants"' not in r.text
    assert 'id="health"' not in r.text
    assert 'id="ask"' not in r.text


def test_city_page_still_serves_full_depth():
    r = client.get("/city/delhi")
    assert r.status_code == 200
    assert 'id="pollutants"' in r.text
    assert 'id="health"' in r.text
    assert 'id="ask"' in r.text
