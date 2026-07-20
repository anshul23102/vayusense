"""The three locally-trained forecasters. Common signature:
forecast(train, horizon) -> np.ndarray of `horizon` values, where train is a
DataFrame with columns date/mean/roll7 sorted ascending by date."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import FEATURES, make_training_frame, next_day_features


def naive_forecast(train: pd.DataFrame, horizon: int) -> np.ndarray:
    return np.repeat(float(train["mean"].iloc[-1]), horizon)


def damped_trend_forecast(train: pd.DataFrame, horizon: int, phi: float = 0.85) -> np.ndarray:
    """Same math as the in-app fallback in agents/tools.py."""
    roll7 = train["roll7"].to_numpy(dtype=float)
    last = float(roll7[-1])
    slope = float(roll7[-1] - roll7[-8]) / 7.0
    hi = float(train["mean"].max()) * 1.1
    lo = max(0.0, float(train["mean"].min()) * 0.5)
    out, cum = [], 0.0
    for t in range(1, horizon + 1):
        cum += phi ** t
        out.append(min(max(last + slope * cum, lo), hi))
    return np.array(out)


def gbt_forecast(train: pd.DataFrame, horizon: int, random_state: int = 0) -> np.ndarray:
    """Gradient boosting on lag/rolling/seasonal features; recursive multi-step."""
    frame = make_training_frame(train["date"], train["mean"].to_numpy(dtype=float))
    model = HistGradientBoostingRegressor(max_iter=200, random_state=random_state)
    model.fit(frame[FEATURES], frame["y"])
    dates = pd.to_datetime(train["date"]).reset_index(drop=True)
    values = train["mean"].to_numpy(dtype=float).copy()
    preds = []
    for _ in range(horizon):
        X, d = next_day_features(dates, values)
        p = max(0.0, float(model.predict(X)[0]))
        preds.append(p)
        values = np.append(values, p)
        dates = pd.concat([dates, pd.Series([d])], ignore_index=True)
    return np.array(preds)


LOCAL_FORECASTERS = {
    "naive": naive_forecast,
    "damped_trend": damped_trend_forecast,
    "gbt": gbt_forecast,
}
