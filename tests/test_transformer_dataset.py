import pandas as pd

from ml.backtest import HORIZON as BENCH_HORIZON
from ml.backtest import MIN_HISTORY, N_FOLDS, make_folds
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


def test_training_examples_never_touch_a_real_fold_window_on_sparse_series():
    """A calendar-day margin alone isn't enough: ml.backtest.make_folds picks
    fold boundaries by ROW POSITION, not by date. A series with a big date
    gap right before its final N_FOLDS*HORIZON rows can have those rows
    still fall within a generous calendar cutoff, silently leaking real
    fold-tested rows into training. This reproduces that exact scenario and
    pins down the row-safe truncation that has to prevent it."""
    fold_rows = N_FOLDS * BENCH_HORIZON  # 24
    dense_rows = MIN_HISTORY + 10 - fold_rows  # 106, comfortably > MIN_HISTORY alone
    dates = list(pd.date_range("2020-01-01", periods=dense_rows, freq="D"))
    last_date = dates[-1]
    for _ in range(fold_rows):
        last_date = last_date + pd.Timedelta(days=200)  # huge gap per row
        dates.append(last_date)
    n_rows = len(dates)
    assert n_rows == MIN_HISTORY + 10

    daily = pd.DataFrame({
        "city": "Sparsetown", "parameter": "pm25",
        "date": dates, "mean": [50.0 + i * 0.01 for i in range(n_rows)],
    })
    vocab = build_vocab(daily)

    # Generous by calendar-day standards, but the sparse tail's rows are all
    # still within it -- a purely date-based guard would wrongly call this
    # safe.
    cutoff = daily["date"].max() - pd.Timedelta(days=45)

    full_sorted = daily.sort_values("date").reset_index(drop=True)
    row_safe_end = make_folds(len(full_sorted))[0][0]
    assert row_safe_end == dense_rows  # sanity: matches this test's construction

    X, y, city_idx, param_idx, norm_stats = build_training_examples(
        daily, cutoff, BENCH_HORIZON, vocab)

    expected_windows = row_safe_end - CONTEXT_DAYS - BENCH_HORIZON + 1
    assert expected_windows > 0
    assert X.shape[0] == expected_windows
