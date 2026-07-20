import numpy as np
import pandas as pd

from ml.forecasters import LOCAL_FORECASTERS, damped_trend_forecast, gbt_forecast, naive_forecast


def _train(n=150, slope=0.5):
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    mean = 60 + slope * np.arange(n) + np.random.default_rng(0).normal(0, 2, n)
    df = pd.DataFrame({"date": dates, "mean": mean})
    df["roll7"] = df["mean"].rolling(7, min_periods=1).mean()
    return df


def test_naive_repeats_last_value():
    train = _train()
    out = naive_forecast(train, 3)
    assert out.shape == (3,)
    assert np.allclose(out, train["mean"].iloc[-1])


def test_damped_follows_trend_direction_and_clamps():
    train = _train(slope=0.5)
    out = damped_trend_forecast(train, 5)
    assert out.shape == (5,)
    # rising series: forecast should not fall below the last rolling value minus noise
    assert out[0] >= train["roll7"].iloc[-1] - 1
    # clamped: never exceeds 1.1x historical max
    assert out.max() <= train["mean"].max() * 1.1 + 1e-9


def test_gbt_is_deterministic_and_finite():
    train = _train()
    a = gbt_forecast(train, 4)
    b = gbt_forecast(train, 4)
    assert a.shape == (4,)
    assert np.allclose(a, b)
    assert np.all(np.isfinite(a)) and np.all(a >= 0)


def test_registry_names():
    assert set(LOCAL_FORECASTERS) == {"naive", "damped_trend", "gbt"}
