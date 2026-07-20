import app.live as live
from app.main import city_aqi


def test_ranking_rows_have_dominant_and_source(monkeypatch):
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    monkeypatch.setattr(live, "peek_live_city", lambda c: None)
    out = city_aqi(city="Delhi")
    assert len(out["ranking"]) >= 8
    for row in out["ranking"]:
        assert set(row) == {"city", "aqi", "category", "dominant", "source"}
        assert row["source"] in {"live", "archive"}
    assert out["ranking"] == sorted(out["ranking"], key=lambda r: -r["aqi"])


def test_ranking_source_reflects_cache_without_fetching(monkeypatch):
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    calls = {"n": 0}

    def fake_peek(c):
        calls["n"] += 1
        return {"concs": {"pm25": {"value": 50.0, "unit": "µg/m³"}},
                "last_updated": "2026-07-20T00:00:00+00:00", "stations": 1} if c == "Delhi" else None
    monkeypatch.setattr(live, "peek_live_city", fake_peek)
    out = city_aqi(city="Delhi")
    delhi_row = next(r for r in out["ranking"] if r["city"] == "Delhi")
    assert delhi_row["source"] == "live"
    other = next(r for r in out["ranking"] if r["city"] != "Delhi")
    assert other["source"] == "archive"
    assert calls["n"] >= 1        # peek was used, confirming no bypass
