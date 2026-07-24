from datetime import datetime, timedelta, timezone

import app.aqi_stations as aqi_stations
from app.main import aqi_stations_api


def _loc(id_=1, name="Test Station", locality="Delhi", country="India",
         lat=28.6, lon=77.2, sensor_id=901):
    return {
        "id": id_, "name": name, "locality": locality,
        "country": {"name": country},
        "coordinates": {"latitude": lat, "longitude": lon},
        "sensors": [{"id": sensor_id, "parameter": {"name": "pm25"}}],
    }


def _latest_payload(sensor_id=901, value=52.0, hours_ago=1):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"results": [{"sensorsId": sensor_id, "value": value, "datetime": {"utc": ts}}]}


def test_no_key_returns_none(monkeypatch):
    aqi_stations._cache.clear()
    monkeypatch.setattr(aqi_stations, "_api_key", lambda: "")
    assert aqi_stations.get_stations((0, 0, 1, 1)) is None


def test_pm25_sensor_id_finds_and_ignores_other_parameters():
    loc = {"sensors": [{"id": 1, "parameter": {"name": "no2"}},
                        {"id": 2, "parameter": {"name": "pm25"}}]}
    assert aqi_stations._pm25_sensor_id(loc) == 2


def test_pm25_sensor_id_none_when_absent():
    assert aqi_stations._pm25_sensor_id({"sensors": [{"id": 1, "parameter": {"name": "co"}}]}) is None


def test_nearest_supported_city_matches_within_radius():
    assert aqi_stations._nearest_supported_city(28.68, 77.08) == "delhi"


def test_nearest_supported_city_none_far_away():
    assert aqi_stations._nearest_supported_city(52.52, 13.405) is None  # Berlin


def test_build_station_marks_supported_city_by_proximity():
    # OpenAQ's "locality" is often a verbose station label, not a clean city
    # name ("Mundka, Delhi - DPCC") -- matching is by coordinates, not name,
    # so this deliberately uses a locality string that wouldn't string-match
    # "delhi" at all, at coordinates close to (but not exactly) Delhi's.
    loc = _loc(locality="Mundka, Delhi - DPCC", lat=28.68, lon=77.08)
    station = aqi_stations._build_station(loc, {"value": 40.0, "updated_at": "2026-01-01T00:00:00Z"})
    assert station["is_supported_city"] is True
    assert station["supported_city_slug"] == "delhi"
    assert station["aqi"] > 0
    assert station["category"]


def test_build_station_unsupported_city_has_no_slug():
    loc = _loc(locality="Berlin", country="Germany", lat=52.52, lon=13.405)
    station = aqi_stations._build_station(loc, {"value": 15.0, "updated_at": "2026-01-01T00:00:00Z"})
    assert station["is_supported_city"] is False
    assert station["supported_city_slug"] is None
    assert station["country"] == "Germany"


def test_build_station_rejects_negative_value():
    assert aqi_stations._build_station(_loc(), {"value": -5.0, "updated_at": "2026-01-01T00:00:00Z"}) is None


def test_fetch_latest_pm25_rejects_stale_reading(monkeypatch):
    monkeypatch.setattr(aqi_stations, "_get_json", lambda url, params=None: _latest_payload(hours_ago=48))
    assert aqi_stations._fetch_latest_pm25(1, 901) is None


def test_fetch_latest_pm25_returns_fresh_reading(monkeypatch):
    monkeypatch.setattr(aqi_stations, "_get_json", lambda url, params=None: _latest_payload(hours_ago=1, value=33.0))
    out = aqi_stations._fetch_latest_pm25(1, 901)
    assert out["value"] == 33.0


def test_get_stations_end_to_end(monkeypatch):
    aqi_stations._cache.clear()
    monkeypatch.setattr(aqi_stations, "_api_key", lambda: "k")
    monkeypatch.setattr(aqi_stations, "_fetch_locations", lambda bbox: [_loc()])
    monkeypatch.setattr(aqi_stations, "_fetch_latest_pm25", lambda loc_id, sensor_id: {"value": 42.0, "updated_at": "2026-01-01T00:00:00Z"})
    out = aqi_stations.get_stations((70, 20, 80, 30))
    assert len(out) == 1
    assert out[0]["city"] == "Delhi"


def test_get_stations_caches_by_rounded_bbox(monkeypatch):
    aqi_stations._cache.clear()
    monkeypatch.setattr(aqi_stations, "_api_key", lambda: "k")
    calls = {"n": 0}

    def fake_locations(bbox):
        calls["n"] += 1
        return []
    monkeypatch.setattr(aqi_stations, "_fetch_locations", fake_locations)
    aqi_stations.get_stations((70.01, 20.01, 80.01, 30.01))
    aqi_stations.get_stations((70.04, 20.04, 80.04, 30.04))
    assert calls["n"] == 1


def test_get_stations_returns_empty_list_when_no_stations(monkeypatch):
    aqi_stations._cache.clear()
    monkeypatch.setattr(aqi_stations, "_api_key", lambda: "k")
    monkeypatch.setattr(aqi_stations, "_fetch_locations", lambda bbox: [])
    assert aqi_stations.get_stations((0, 0, 1, 1)) == []


def test_get_stations_failure_returns_none_and_is_cached(monkeypatch):
    aqi_stations._cache.clear()
    monkeypatch.setattr(aqi_stations, "_api_key", lambda: "k")
    calls = {"n": 0}

    def boom(bbox):
        calls["n"] += 1
        raise RuntimeError("down")
    monkeypatch.setattr(aqi_stations, "_fetch_locations", boom)
    assert aqi_stations.get_stations((0, 0, 1, 1)) is None
    assert aqi_stations.get_stations((0, 0, 1, 1)) is None
    assert calls["n"] == 1


def test_api_400_on_missing_bbox():
    from starlette.responses import JSONResponse
    out = aqi_stations_api(None)
    assert isinstance(out, JSONResponse)
    assert out.status_code == 400


def test_api_503_on_unavailable(monkeypatch):
    from starlette.responses import JSONResponse
    monkeypatch.setattr(aqi_stations, "get_stations", lambda bbox: None)
    out = aqi_stations_api("0,0,1,1")
    assert isinstance(out, JSONResponse)
    assert out.status_code == 503


def test_api_200_with_stations(monkeypatch):
    monkeypatch.setattr(aqi_stations, "get_stations", lambda bbox: [{"city": "X"}])
    out = aqi_stations_api("0,0,1,1")
    assert out == {"stations": [{"city": "X"}]}
