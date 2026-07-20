import numpy as np
import pandas as pd

from ml.backtest import HORIZON, MIN_HISTORY, N_FOLDS, backtest_series, mae, make_folds


def test_folds_are_contiguous_nonoverlapping_and_cover_the_tail():
    folds = make_folds(200)
    assert len(folds) == N_FOLDS
    # oldest first, each window exactly HORIZON long, back-to-back, ending at n
    for i, (s, e) in enumerate(folds):
        assert e - s == HORIZON
        if i > 0:
            assert s == folds[i - 1][1]
    assert folds[-1][1] == 200
    assert folds[0][0] == 200 - N_FOLDS * HORIZON


def test_mae_exact():
    assert mae([1, 2, 3], [2, 2, 5]) == 1.0


def test_backtest_scores_every_method_on_identical_folds():
    n = MIN_HISTORY + 40
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    vals = 50 + 0.2 * np.arange(n)
    series = pd.DataFrame({"date": dates, "mean": vals})
    series["roll7"] = series["mean"].rolling(7, min_periods=1).mean()

    perfect = lambda train, h: np.array(
        [50 + 0.2 * (len(train) + t) for t in range(h)]
    )
    awful = lambda train, h: np.zeros(h)
    scores = backtest_series(series, {"perfect": perfect, "awful": awful})
    assert scores["perfect"] < 0.01
    assert scores["awful"] > 50
