import app.wind as wind
from app.main import wind_grid_api, _parse_bbox


def test_get_wind_grid_caches_failure_without_hammering(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(bbox):
        calls["n"] += 1
        raise RuntimeError("network down")
    monkeypatch.setattr(wind, "_fetch_grid", fake_fetch)
    wind._cache.clear()
    assert wind.get_wind_grid((60, 10, 70, 20)) is None
    assert wind.get_wind_grid((60, 10, 70, 20)) is None
    assert calls["n"] == 1


def test_wind_grid_shape(monkeypatch):
    fake = [
        {"header": {"nx": 2, "ny": 2}, "data": [1.0, 2.0, 3.0, 4.0]},
        {"header": {"nx": 2, "ny": 2}, "data": [0.1, 0.2, 0.3, 0.4]},
    ]
    monkeypatch.setattr(wind, "get_wind_grid", lambda bbox=None: fake)
    out = wind_grid_api(None)
    assert len(out) == 2
    assert out[0]["header"]["nx"] == 2
    assert len(out[0]["data"]) == 4


def test_wind_grid_api_503_on_missing(monkeypatch):
    from starlette.responses import JSONResponse
    monkeypatch.setattr(wind, "get_wind_grid", lambda bbox=None: None)
    out = wind_grid_api(None)
    assert isinstance(out, JSONResponse)
    assert out.status_code == 503


def test_wind_grid_api_passes_parsed_bbox(monkeypatch):
    seen = {}

    def fake_get_wind_grid(bbox):
        seen["bbox"] = bbox
        return None
    monkeypatch.setattr(wind, "get_wind_grid", fake_get_wind_grid)
    wind_grid_api("10.0,20.0,30.0,40.0")
    assert seen["bbox"] == (10.0, 20.0, 30.0, 40.0)


def test_parse_bbox_valid():
    assert _parse_bbox("1,2,3,4") == (1.0, 2.0, 3.0, 4.0)


def test_parse_bbox_missing_or_malformed():
    assert _parse_bbox(None) is None
    assert _parse_bbox("") is None
    assert _parse_bbox("1,2,3") is None
    assert _parse_bbox("a,b,c,d") is None


def test_grid_dims_stay_under_point_budget_for_world_bbox():
    lats, lons, nx, ny = wind._grid_points((-180.0, -85.0, 180.0, 85.0))
    assert nx * ny <= wind.MAX_POINTS
    assert nx >= wind.MIN_DIM and ny >= wind.MIN_DIM
    assert len(lats) == len(lons) == nx * ny


def test_grid_dims_stay_under_point_budget_for_narrow_bbox():
    # very wide, very short bbox -- shouldn't collapse either axis to <1
    lats, lons, nx, ny = wind._grid_points((-180.0, 10.0, 180.0, 11.0))
    assert nx * ny <= wind.MAX_POINTS
    assert nx >= wind.MIN_DIM and ny >= wind.MIN_DIM


def test_get_wind_grid_caches_by_rounded_bbox(monkeypatch):
    calls = {"n": 0}

    def fake_fetch(bbox):
        calls["n"] += 1
        return "grid"
    monkeypatch.setattr(wind, "_fetch_grid", fake_fetch)
    wind._cache.clear()
    wind.get_wind_grid((10.01, 20.01, 30.01, 40.01))
    wind.get_wind_grid((10.04, 20.04, 30.04, 40.04))  # rounds to the same cache key
    assert calls["n"] == 1


def test_city_coords_api():
    from app.main import city_coords_api
    out = city_coords_api()
    assert len(out) == 20
    assert out["Delhi"] == [28.6139, 77.209]
