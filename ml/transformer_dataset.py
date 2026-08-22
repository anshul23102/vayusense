"""Builds sliding-window training examples for the global Transformer
forecaster from data/processed/daily_city.parquet-shaped data, with the
leakage-safety cutoff and per-series normalization the design spec requires.
See docs/superpowers/specs/2026-08-16-transformer-forecaster-design.md."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import MIN_HISTORY, make_folds
from .features import _seasonal
from .transformer_config import CONTEXT_DAYS


@dataclass
class Vocab:
    city_to_idx: dict[str, int]
    param_to_idx: dict[str, int]


def build_vocab(daily: pd.DataFrame) -> Vocab:
    cities = sorted(daily["city"].unique())
    params = sorted(daily["parameter"].unique())
    return Vocab(
        city_to_idx={c: i for i, c in enumerate(cities)},
        param_to_idx={p: i for i, p in enumerate(params)},
    )


def _series_windows(dates: pd.Series, normed_values: np.ndarray, horizon: int):
    """Yields (input_window[CONTEXT_DAYS, 5], target[horizon]) for every
    valid sliding position. `normed_values` must already be normalized by
    the caller."""
    seas = _seasonal(pd.to_datetime(dates)).to_numpy(dtype=float)
    n = len(normed_values)
    for start in range(0, n - CONTEXT_DAYS - horizon + 1):
        end = start + CONTEXT_DAYS
        window_vals = normed_values[start:end]
        window_seas = seas[start:end]
        x = np.concatenate([window_vals.reshape(-1, 1), window_seas], axis=1)
        y = normed_values[end:end + horizon]
        yield x.astype(np.float32), y.astype(np.float32)


def build_training_examples(daily: pd.DataFrame, cutoff: pd.Timestamp,
                             horizon: int, vocab: Vocab):
    """Returns (X, y, city_idx, param_idx, norm_stats). norm_stats is
    {(city, parameter): (mean, std)} computed ONLY from the training-safe
    history -- ml/transformer_forecaster.py must reuse these exact stats at
    inference time rather than recomputing from a shorter backtest-fold
    slice.

    Two independent guards decide how much of each series' history is safe
    to train on, and the more restrictive one wins:

    1. The calendar `cutoff` (date-based).
    2. A row-position guard: ml.backtest.make_folds picks fold boundaries by
       ROW COUNT, not by date, so a series with a big date gap right before
       its final N_FOLDS*HORIZON rows can have those rows still fall inside
       a generous calendar cutoff -- a purely date-based guard would call
       that safe when it isn't. This is computed against each series' FULL
       history (before any date truncation), matching exactly what
       ml/bench.py's backtest_series() will later run folds against."""
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])

    xs, ys, city_idxs, param_idxs = [], [], [], []
    norm_stats: dict[tuple[str, str], tuple[float, float]] = {}

    for (city, parameter), full_grp in daily.groupby(["city", "parameter"]):
        full_grp = full_grp.sort_values("date").reset_index(drop=True)
        if len(full_grp) >= MIN_HISTORY:
            row_safe_end = make_folds(len(full_grp))[0][0]
            grp = full_grp.iloc[:row_safe_end]
        else:
            # Shorter than MIN_HISTORY means ml/bench.py's run_bench() never
            # backtests this series at all (see its own MIN_HISTORY gate),
            # so no real fold will ever run against it -- nothing to guard.
            grp = full_grp
        grp = grp[grp["date"] <= cutoff]

        raw = grp["mean"].to_numpy(dtype=float)
        if len(raw) < CONTEXT_DAYS + horizon:
            continue
        mean, std = float(raw.mean()), float(raw.std())
        std = std if std > 1e-6 else 1.0
        norm_stats[(city, parameter)] = (mean, std)
        normed = (raw - mean) / std
        for x, y in _series_windows(grp["date"], normed, horizon):
            xs.append(x)
            ys.append(y)
            city_idxs.append(vocab.city_to_idx[city])
            param_idxs.append(vocab.param_to_idx[parameter])

    return (
        np.stack(xs), np.stack(ys),
        np.array(city_idxs, dtype=np.int64), np.array(param_idxs, dtype=np.int64),
        norm_stats,
    )
