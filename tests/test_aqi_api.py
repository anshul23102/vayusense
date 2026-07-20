import json

import agents.tools as tools
from app.main import _city_aqi


def test_city_aqi_archive_fallback(monkeypatch):
    import app.live as live
    monkeypatch.setattr(live, "get_live_city", lambda c: None)
    out = _city_aqi("Delhi", allow_fetch=True)
    assert out["source"] == "archive"
    assert out["basis"] == "EPA-method AQI from daily averages"
    assert isinstance(out["aqi"], int) and out["aqi"] > 0
    assert out["category"]["key"] in {"good", "moderate", "poor", "unhealthy", "severe", "hazardous"}
    assert out["dominant"] in out["sub_aqi"]


def test_city_aqi_live_path(monkeypatch):
    import app.live as live
    monkeypatch.setattr(live, "get_live_city",
                        lambda c: {"concs": {"pm25": {"value": 52.0, "unit": "µg/m³"}},
                                   "last_updated": "2026-07-20T04:00:00+00:00",
                                   "stations": 3})
    out = _city_aqi("Delhi", allow_fetch=True)
    assert out["source"] == "live"
    assert out["aqi"] == 142  # EPA 2024 table: pm25 52.0 ug/m3 -> 141.6 -> 142
    assert out["last_updated"] == "2026-07-20T04:00:00+00:00"


def test_snapshot_includes_aqi():
    out = json.loads(tools.get_city_snapshot("Delhi"))
    assert isinstance(out["aqi"], int)
    assert out["aqi_category"] in {"Good", "Moderate", "Poor", "Unhealthy", "Severe", "Hazardous"}
    assert out["aqi_dominant"] in out["pollutants"]
    assert out["aqi_basis"] == "EPA-method AQI from daily averages"
