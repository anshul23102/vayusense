import numpy as np
import pandas as pd
import pytest

import ml.train_transformer as tt
import ml.transformer_forecaster as tf
from ml.transformer_forecaster import UnknownSeriesError, transformer_forecast


def _make_daily(n_days=100):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for city in ["Delhi", "Mumbai"]:
        base = 50.0 if city == "Delhi" else 30.0
        for i, d in enumerate(dates):
            val = base + 5 * np.sin(i / 7) + 0.05 * i
            rows.append({"city": city, "parameter": "pm25", "date": d, "mean": val})
    return pd.DataFrame(rows)


@pytest.fixture
def trained_model(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "WEIGHTS_DIR", tmp_path)
    monkeypatch.setattr(tf, "WEIGHTS_DIR", tmp_path)
    tf._load.cache_clear()
    daily = _make_daily(n_days=100)
    model, vocab, norm_stats, cutoff = tt.train(
        daily, horizon=7, test_margin_days=25, max_epochs=5)
    tt.save(model, vocab, norm_stats, cutoff, horizon=7)
    yield daily
    tf._load.cache_clear()


def _series(daily, city="Delhi"):
    return daily[(daily["city"] == city) & (daily["parameter"] == "pm25")]


def test_forecast_returns_requested_horizon(trained_model):
    out = transformer_forecast(_series(trained_model), horizon=3)
    assert out.shape == (3,)
    assert np.isfinite(out).all()
    assert (out >= 0).all()


def test_forecast_slices_down_from_trained_horizon(trained_model):
    full = transformer_forecast(_series(trained_model), horizon=7)
    short = transformer_forecast(_series(trained_model), horizon=3)
    assert full.shape == (7,)
    np.testing.assert_allclose(short, full[:3])


def test_forecast_rejects_horizon_beyond_training(trained_model):
    with pytest.raises(UnknownSeriesError):
        transformer_forecast(_series(trained_model), horizon=10)


def test_forecast_rejects_unknown_city(trained_model):
    series = _series(trained_model).copy()
    series["city"] = "Atlantis"
    with pytest.raises(UnknownSeriesError):
        transformer_forecast(series, horizon=3)


def test_forecast_rejects_short_series(trained_model):
    series = _series(trained_model).tail(10)
    with pytest.raises(UnknownSeriesError):
        transformer_forecast(series, horizon=3)
