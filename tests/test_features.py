import numpy as np
import pandas as pd

from ml.features import FEATURES, make_training_frame, next_day_features


def _series(n=60):
    dates = pd.Series(pd.date_range("2025-01-01", periods=n, freq="D"))
    values = np.linspace(50, 80, n) + np.sin(np.arange(n)) * 3
    return dates, values


def test_training_frame_has_features_and_no_nans():
    dates, values = _series()
    frame = make_training_frame(dates, values)
    assert set(FEATURES) <= set(frame.columns)
    assert not frame[FEATURES + ["y"]].isna().any().any()
    # longest lag is 14, so exactly 14 rows are dropped
    assert len(frame) == 60 - 14


def test_lag_values_are_correct():
    dates, values = _series()
    frame = make_training_frame(dates, values)
    # for any row, lag1 must equal the previous day's y
    row = frame.iloc[5]
    prev = frame.iloc[4]
    assert row["lag1"] == prev["y"]


def test_next_day_features_shape_and_date():
    dates, values = _series()
    X, d = next_day_features(dates, values)
    assert list(X.columns) == FEATURES
    assert len(X) == 1
    assert d == dates.iloc[-1] + pd.Timedelta(days=1)
    assert float(X["lag1"].iloc[0]) == values[-1]
