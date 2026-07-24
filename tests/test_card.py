from fastapi.testclient import TestClient

from app import card
from app.main import app

client = TestClient(app)


def test_render_card_produces_valid_png():
    png = card.render_card(
        city="Delhi", aqi=137, category_key="poor", category_label="Poor",
        dominant="pm25", source="live", updated="2026-07-24T05:00:00+00:00",
        cigarettes_per_day=3.9, years_lost=7.84,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 5000


def test_card_route():
    r = client.get("/city/delhi/card.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_card_route_unknown_city():
    r = client.get("/city/atlantis/card.png")
    assert r.status_code == 404


def test_city_page_has_og_meta():
    r = client.get("/city/mumbai")
    assert r.status_code == 200
    assert 'property="og:image" content="/city/mumbai/card.png"' in r.text
    assert 'property="og:title"' in r.text
    assert "Mumbai" in r.text
