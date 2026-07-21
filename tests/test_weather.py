import app.weather as weather
from app.main import weather_api


def test_get_weather_returns_none_for_unknown_city():
    assert weather.get_weather("Atlantis") is None


def test_get_weather_uses_cache(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(city):
        calls["n"] += 1
        return {"temp_c": 30, "humidity_pct": 60, "wind_kmh": 10, "uv_index": 5, "observed_at": "x"}
    monkeypatch.setattr(weather, "_fetch", fake_fetch)
    weather._cache.clear()
    first = weather.get_weather("Delhi")
    second = weather.get_weather("Delhi")
    assert first == second
    assert calls["n"] == 1


def test_get_weather_caches_failure_without_hammering(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(city):
        calls["n"] += 1
        raise RuntimeError("network down")
    monkeypatch.setattr(weather, "_fetch", fake_fetch)
    weather._cache.clear()
    assert weather.get_weather("Delhi") is None
    assert weather.get_weather("Delhi") is None
    assert calls["n"] == 1


def test_weather_api_shape(monkeypatch):
    monkeypatch.setattr(weather, "get_weather",
                        lambda c: {"temp_c": 28.6, "humidity_pct": 91, "wind_kmh": 9.6,
                                   "uv_index": 0.0, "observed_at": "2026-07-22T00:15"})
    out = weather_api(city="Delhi")
    assert out["temp_c"] == 28.6
    assert out["humidity_pct"] == 91


def test_weather_api_404_on_missing(monkeypatch):
    from starlette.responses import JSONResponse
    monkeypatch.setattr(weather, "get_weather", lambda c: None)
    out = weather_api(city="Atlantis")
    assert isinstance(out, JSONResponse)
    assert out.status_code == 404
