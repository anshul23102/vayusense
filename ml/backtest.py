"""Rolling-origin backtest: identical held-out folds for every method."""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_HISTORY = 120   # series shorter than this are skipped by the bench
N_FOLDS = 8
HORIZON = 3         # days per fold


def make_folds(n_rows: int, n_folds: int = N_FOLDS, horizon: int = HORIZON) -> list[tuple[int, int]]:
    """Positional [start, end) test windows over the final n_folds*horizon rows,
    oldest fold first. Train set for a fold is rows [:start]."""
    folds = []
    for k in range(n_folds, 0, -1):
        end = n_rows - (k - 1) * horizon
        folds.append((end - horizon, end))
    return folds


def mae(pred, actual) -> float:
    return float(np.mean(np.abs(np.asarray(pred, dtype=float) - np.asarray(actual, dtype=float))))


def backtest_series(series: pd.DataFrame, forecasters: dict) -> dict[str, float]:
    """Mean MAE per forecaster over identical rolling-origin folds.
    `series`: columns date/mean/roll7, one city+parameter, any order."""
    series = series.sort_values("date").reset_index(drop=True)
    scores: dict[str, list[float]] = {name: [] for name in forecasters}
    for start, end in make_folds(len(series)):
        train = series.iloc[:start]
        actual = series.iloc[start:end]["mean"].to_numpy(dtype=float)
        for name, fn in forecasters.items():
            scores[name].append(mae(fn(train, end - start), actual))
    return {name: float(np.mean(v)) for name, v in scores.items()}
