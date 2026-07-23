import app.wind as wind
from app.main import wind_grid_api


def test_get_wind_grid_caches_failure_without_hammering(monkeypatch):
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        raise RuntimeError("network down")
    monkeypatch.setattr(wind, "_fetch_grid", fake_fetch)
    wind._cache.clear()
    assert wind.get_wind_grid() is None
    assert wind.get_wind_grid() is None
    assert calls["n"] == 1


def test_wind_grid_shape(monkeypatch):
    fake = [
        {"header": {"nx": 2, "ny": 2}, "data": [1.0, 2.0, 3.0, 4.0]},
        {"header": {"nx": 2, "ny": 2}, "data": [0.1, 0.2, 0.3, 0.4]},
    ]
    monkeypatch.setattr(wind, "get_wind_grid", lambda: fake)
    out = wind_grid_api()
    assert len(out) == 2
    assert out[0]["header"]["nx"] == 2
    assert len(out[0]["data"]) == 4


def test_wind_grid_api_503_on_missing(monkeypatch):
    from starlette.responses import JSONResponse
    monkeypatch.setattr(wind, "get_wind_grid", lambda: None)
    out = wind_grid_api()
    assert isinstance(out, JSONResponse)
    assert out.status_code == 503


def test_city_coords_api():
    from app.main import city_coords_api
    out = city_coords_api()
    assert len(out) == 20
    assert out["Delhi"] == [28.6139, 77.209]
