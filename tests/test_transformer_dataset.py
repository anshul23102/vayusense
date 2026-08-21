import pandas as pd

from ml.transformer_config import CONTEXT_DAYS
from ml.transformer_dataset import build_training_examples, build_vocab


def _make_daily(n_days=90):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for city in ["Delhi", "Mumbai"]:
        base = 50.0 if city == "Delhi" else 30.0
        for i, d in enumerate(dates):
            rows.append({"city": city, "parameter": "pm25", "date": d,
                         "mean": base + i * 0.1})
    return pd.DataFrame(rows)


def test_build_vocab():
    daily = _make_daily()
    vocab = build_vocab(daily)
    assert vocab.city_to_idx == {"Delhi": 0, "Mumbai": 1}
    assert vocab.param_to_idx == {"pm25": 0}


def test_training_examples_shapes():
    daily = _make_daily(n_days=90)
    vocab = build_vocab(daily)
    cutoff = pd.Timestamp("2026-03-31")
    horizon = 3
    X, y, city_idx, param_idx, norm_stats = build_training_examples(
        daily, cutoff, horizon, vocab)
    assert X.shape[1:] == (CONTEXT_DAYS, 5)
    assert y.shape[1] == horizon
    assert X.shape[0] == y.shape[0] == city_idx.shape[0] == param_idx.shape[0]
    assert ("Delhi", "pm25") in norm_stats
    assert ("Mumbai", "pm25") in norm_stats


def test_training_examples_respect_cutoff():
    daily = _make_daily(n_days=90)
    vocab = build_vocab(daily)
    cutoff = pd.Timestamp("2026-01-01") + pd.Timedelta(days=CONTEXT_DAYS + 5)
    horizon = 3
    X, y, city_idx, param_idx, norm_stats = build_training_examples(
        daily, cutoff, horizon, vocab)
    # Rows after truncation to cutoff = CONTEXT_DAYS + 6 (day indices
    # 0..CONTEXT_DAYS+5 inclusive). Windows per series =
    # n - CONTEXT_DAYS - horizon + 1 = (CONTEXT_DAYS+6) - CONTEXT_DAYS - 3 + 1 = 4.
    # Two cities -> 8 total.
    assert X.shape[0] == 8
    assert y.shape[0] == 8
