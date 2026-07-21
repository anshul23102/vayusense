import app.live as live
from app.main import snapshot


def test_snapshot_overlays_live_concentration(monkeypatch):
    """Regression test (Phase D audit): /api/snapshot must not show an
    archive-only pollutant value that contradicts a live hero AQI for the
    same city -- the same live/archive self-consistency bug fixed earlier
    for the ranking table also existed here, undetected until this audit."""
    monkeypatch.setattr(live, "get_live_city",
                        lambda c: {"concs": {"pm25": {"value": 11.0, "unit": "µg/m³"}},
                                   "last_updated": "2026-07-21T14:15:00+00:00",
                                   "stations": 2})
    out = snapshot(city="Delhi")
    pm25 = out["pollutants"]["pm25"]
    assert pm25["source"] == "live"
    assert pm25["daily_mean"] == 11.0
    assert pm25["times_who_limit"] == round(11.0 / 15.0, 1)
    # A pollutant with no live reading falls back to archive, honestly labeled.
    other = next(v for k, v in out["pollutants"].items() if k != "pm25")
    assert other["source"] == "archive"
    # The overall AQI must be recomputed from these same (overlaid)
    # concentrations, never left over from a stale, all-archive computation.
    assert isinstance(out["aqi"], int) and out["aqi"] > 0
    assert "live" in out["aqi_basis"]


def test_snapshot_all_archive_when_live_unavailable(monkeypatch):
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    out = snapshot(city="Delhi")
    assert all(v["source"] == "archive" for v in out["pollutants"].values())
