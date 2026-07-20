import json

import agents.tools as tools


def _clear_caches():
    for fn in (tools._forecasts, tools._bench):
        fn.cache_clear()


def test_get_forecast_serves_winner_with_citation():
    _clear_caches()
    out = json.loads(tools.get_forecast("Delhi", "pm25", 3))
    assert "error" not in out
    assert out["method"] in {"naive", "damped_trend", "gbt", "arima_plus"}
    assert out["method_label"]
    assert out["methods_compared"] >= 3
    assert isinstance(out["backtest_mae"], float)
    assert len(out["forecast"]) == 3
    assert "fallback" not in out


def test_get_forecast_falls_back_when_artifacts_missing(monkeypatch):
    _clear_caches()
    monkeypatch.setattr(tools, "_forecasts", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    out = json.loads(tools.get_forecast("Delhi", "pm25", 3))
    assert out["method"] == "damped_trend"
    assert out["fallback"] is True
    assert len(out["forecast"]) == 3


def test_get_forecast_bench_shape():
    _clear_caches()
    out = json.loads(tools.get_forecast_bench("Delhi", "pm25"))
    assert out["series"]["winner"] in out["series"]["mae"]
    assert set(out["methods"]) >= {"naive", "damped_trend", "gbt"}
    assert out["fold_scheme"]["n_folds"] == 8


def test_get_forecast_bench_unknown_city():
    _clear_caches()
    out = json.loads(tools.get_forecast_bench("Atlantis", "pm25"))
    assert "error" in out
