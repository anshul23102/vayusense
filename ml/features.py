"""Feature engineering for the gradient-boosted forecaster."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 7, 14]
ROLLS = [7, 14]
FEATURES = (
    [f"lag{l}" for l in LAGS]
    + [f"rmean{w}" for w in ROLLS]
    + ["dow_sin", "dow_cos", "doy_sin", "doy_cos"]
)


def _seasonal(dates: pd.Series) -> pd.DataFrame:
    dow = dates.dt.dayofweek
    doy = dates.dt.dayofyear
    return pd.DataFrame({
        "dow_sin": np.sin(2 * np.pi * dow / 7),
        "dow_cos": np.cos(2 * np.pi * dow / 7),
        "doy_sin": np.sin(2 * np.pi * doy / 365.25),
        "doy_cos": np.cos(2 * np.pi * doy / 365.25),
    })


def make_training_frame(dates: pd.Series, values: np.ndarray) -> pd.DataFrame:
    """One row per day with lag/rolling/seasonal features and target y."""
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    df = pd.DataFrame({"date": dates, "y": np.asarray(values, dtype=float)})
    for l in LAGS:
        df[f"lag{l}"] = df["y"].shift(l)
    for w in ROLLS:
        # shift(1) so the window only sees strictly-past values
        df[f"rmean{w}"] = df["y"].shift(1).rolling(w).mean()
    df = pd.concat([df, _seasonal(dates)], axis=1)
    return df.dropna().reset_index(drop=True)


def next_day_features(dates: pd.Series, values: np.ndarray) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Feature row for the day after the last observed date."""
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    values = np.asarray(values, dtype=float)
    d = dates.iloc[-1] + pd.Timedelta(days=1)
    row = {f"lag{l}": values[-l] for l in LAGS}
    for w in ROLLS:
        row[f"rmean{w}"] = float(np.mean(values[-w:]))
    seas = _seasonal(pd.Series([d]))
    for c in seas.columns:
        row[c] = float(seas[c].iloc[0])
    return pd.DataFrame([row])[FEATURES], d
