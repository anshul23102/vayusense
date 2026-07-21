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


def test_ranking_row_source_matches_the_data_that_produced_its_aqi(monkeypatch):
    """Regression test: a ranking row's 'source' must always match where its
    'aqi' number actually came from. Previously the ranking loop always
    computed 'aqi' from the stale archive but labeled 'source' from a live
    cache peek, so a city could show source=live with an archive-derived
    number (e.g. Delhi hero=59 live vs ranking=318 archive, both for "now")."""
    def fake_live(c):
        return {"concs": {"pm25": {"value": 11.0, "unit": "µg/m³"}},
                "last_updated": "2026-07-21T00:00:00+00:00", "stations": 1} if c == "Delhi" else None
    monkeypatch.setattr(live, "get_live_city", fake_live)
    out = city_aqi(city="Delhi")
    delhi_row = next(r for r in out["ranking"] if r["city"] == "Delhi")
    assert delhi_row["source"] == "live"
    assert delhi_row["aqi"] == out["aqi"]        # same source path as the hero number
    other = next(r for r in out["ranking"] if r["city"] != "Delhi")
    assert other["source"] == "archive"
