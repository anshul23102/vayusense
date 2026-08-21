import numpy as np
import pandas as pd

import ml.bench as bench_mod
import ml.train_transformer as tt
import ml.transformer_forecaster as tf


def _make_daily(n_days=150):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for city in ["Delhi", "Mumbai"]:
        base = 50.0 if city == "Delhi" else 30.0
        for i, d in enumerate(dates):
            val = base + 5 * np.sin(i / 7) + 0.02 * i
            rows.append({"city": city, "parameter": "pm25", "date": d,
                         "mean": val, "roll7": val})
    return pd.DataFrame(rows)


def test_transformer_appears_in_bench_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "WEIGHTS_DIR", tmp_path)
    monkeypatch.setattr(tf, "WEIGHTS_DIR", tmp_path)
    tf._load.cache_clear()

    daily = _make_daily()
    model, vocab, norm_stats, cutoff = tt.train(
        daily, horizon=7, test_margin_days=25, max_epochs=5)
    tt.save(model, vocab, norm_stats, cutoff, horizon=7)

    bench, forecasts = bench_mod.run_bench(daily, bq=None)

    assert "transformer" in bench["methods"]
    scored = [s for s in bench["series"] if "transformer" in s["mae"]]
    assert len(scored) > 0
    assert "transformer" in forecasts["method"].unique()

    tf._load.cache_clear()


def test_bench_survives_missing_transformer_weights(tmp_path, monkeypatch):
    # No training run happened -- WEIGHTS_DIR is empty. The bench must still
    # complete and just omit "transformer" from every series' scores.
    monkeypatch.setattr(tf, "WEIGHTS_DIR", tmp_path)
    tf._load.cache_clear()

    daily = _make_daily()
    bench, forecasts = bench_mod.run_bench(daily, bq=None)

    assert all("transformer" not in s["mae"] for s in bench["series"])

    tf._load.cache_clear()
