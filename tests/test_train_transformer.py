import json

import numpy as np
import pandas as pd
import pytest

import ml.train_transformer as tt
from ml.transformer_config import LeakageMarginError


def _make_daily(n_days=100):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for city in ["Delhi", "Mumbai"]:
        base = 50.0 if city == "Delhi" else 30.0
        for i, d in enumerate(dates):
            val = base + 5 * np.sin(i / 7) + 0.05 * i
            rows.append({"city": city, "parameter": "pm25", "date": d, "mean": val})
    return pd.DataFrame(rows)


def test_train_produces_a_model_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "WEIGHTS_DIR", tmp_path)

    daily = _make_daily(n_days=100)
    model, vocab, norm_stats, cutoff = tt.train(
        daily, horizon=3, test_margin_days=25, max_epochs=5)

    assert vocab.city_to_idx == {"Delhi": 0, "Mumbai": 1}
    assert ("Delhi", "pm25") in norm_stats

    tt.save(model, vocab, norm_stats, cutoff, horizon=3)
    assert (tmp_path / "transformer_forecaster.pt").exists()
    meta = json.loads((tmp_path / "transformer_forecaster.meta.json").read_text())
    assert meta["horizon"] == 3
    assert meta["city_to_idx"] == {"Delhi": 0, "Mumbai": 1}
    assert "Delhi|pm25" in meta["norm_stats"]


def test_train_rejects_unsafe_margin():
    daily = _make_daily(n_days=100)
    with pytest.raises(LeakageMarginError):
        tt.train(daily, horizon=3, test_margin_days=24)
