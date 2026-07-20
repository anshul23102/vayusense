import json
from datetime import datetime, timedelta, timezone

import app.live as live


def _payload(param="pm25", value=52.0, unit="µg/m³", hours_ago=1, sensor_id="901"):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"results": [{"sensorsId": int(sensor_id), "value": value,
                         "datetime": {"utc": ts}}]}


def _fake_locations():
    return {"Testville": [{"location_id": 7,
                           "sensors": {"901": {"parameter": "pm25", "unit": "µg/m³"}}}]}


def test_fetch_aggregates_and_caches(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_locations", _fake_locations)
    monkeypatch.setattr(live, "_api_key", lambda: "k")
    calls = {"n": 0}

    def fake_get(url):
        calls["n"] += 1
        return _payload()
    monkeypatch.setattr(live, "_get_json", fake_get)

    out = live.get_live_city("Testville")
    assert out["concs"]["pm25"]["value"] == 52.0
    assert out["concs"]["pm25"]["unit"] == "µg/m³"
    assert out["stations"] == 1
    live.get_live_city("Testville")           # second call
    assert calls["n"] == 1                     # served from cache


def test_stale_measurements_mean_no_live(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_locations", _fake_locations)
    monkeypatch.setattr(live, "_api_key", lambda: "k")
    monkeypatch.setattr(live, "_get_json", lambda url: _payload(hours_ago=48))
    assert live.get_live_city("Testville") is None


def test_http_failure_returns_none_and_is_cached(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_locations", _fake_locations)
    monkeypatch.setattr(live, "_api_key", lambda: "k")
    calls = {"n": 0}

    def boom(url):
        calls["n"] += 1
        raise RuntimeError("down")
    monkeypatch.setattr(live, "_get_json", boom)
    assert live.get_live_city("Testville") is None
    assert live.get_live_city("Testville") is None
    assert calls["n"] == 1                     # failure cached, no hammering


def test_no_key_returns_none(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_api_key", lambda: "")
    assert live.get_live_city("Testville") is None


def test_peek_never_fetches(monkeypatch):
    live._cache.clear()
    monkeypatch.setattr(live, "_get_json",
                        lambda url: (_ for _ in ()).throw(AssertionError("fetched")))
    assert live.peek_live_city("Testville") is None
