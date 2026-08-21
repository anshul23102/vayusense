"""Bench-facing inference for the global Transformer forecaster. Loads the
weights trained by ml/train_transformer.py once per process and reuses the
per-series normalization stats stored at training time (not stats
recomputed from a possibly-shorter backtest-fold slice) -- see the design
spec's 'Integration into the bench' section for why."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .features import _seasonal
from .transformer_config import CONTEXT_DAYS
from .transformer_model import SequenceTransformer

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = ROOT / "ml" / "model_weights"


class UnknownSeriesError(Exception):
    """Raised when a (city, parameter) pair, a series shorter than
    CONTEXT_DAYS, or a horizon beyond what the model was trained for is
    asked of it -- e.g. a city added to the archive after the last training
    run. Callers (ml/bench.py) catch this specifically and skip the
    transformer for that series, the same way a series with no arima_plus
    match is already skipped today."""


@lru_cache(maxsize=1)
def _load():
    meta = json.loads((WEIGHTS_DIR / "transformer_forecaster.meta.json").read_text())
    model = SequenceTransformer(horizon=meta["horizon"])
    state = torch.load(WEIGHTS_DIR / "transformer_forecaster.pt", map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    return model, meta


def transformer_forecast(train: pd.DataFrame, horizon: int) -> np.ndarray:
    """Same call shape as ml/forecasters.py's LOCAL_FORECASTERS entries, but
    loads pretrained weights instead of fitting from scratch. Predicts the
    model's full trained horizon and slices down when asked for fewer
    steps (the bench's backtest folds ask for horizon=3; the served final
    forecast asks for horizon=7, the horizon the model was trained for)."""
    model, meta = _load()
    if horizon > meta["horizon"]:
        raise UnknownSeriesError(
            f"model trained for max horizon {meta['horizon']}, asked for {horizon}")

    city = train["city"].iloc[-1] if "city" in train.columns else None
    parameter = train["parameter"].iloc[-1] if "parameter" in train.columns else None
    if city not in meta["city_to_idx"] or parameter not in meta["param_to_idx"]:
        raise UnknownSeriesError(f"no trained embedding for city={city!r} parameter={parameter!r}")
    key = f"{city}|{parameter}"
    if key not in meta["norm_stats"]:
        raise UnknownSeriesError(f"no stored normalization stats for {key!r}")
    mean, std = meta["norm_stats"][key]

    if len(train) < CONTEXT_DAYS:
        raise UnknownSeriesError(
            f"series has {len(train)} rows, need at least {CONTEXT_DAYS}")

    window = train.sort_values("date").tail(CONTEXT_DAYS)
    raw = window["mean"].to_numpy(dtype=float)
    normed = (raw - mean) / std
    seas = _seasonal(pd.to_datetime(window["date"])).to_numpy(dtype=float)
    x = np.concatenate([normed.reshape(-1, 1), seas], axis=1).astype(np.float32)

    x_t = torch.from_numpy(x).unsqueeze(0)
    city_t = torch.tensor([meta["city_to_idx"][city]], dtype=torch.long)
    param_t = torch.tensor([meta["param_to_idx"][parameter]], dtype=torch.long)

    with torch.no_grad():
        pred = model(x_t, city_t, param_t).squeeze(0).numpy()
    pred = (pred * std + mean)[:horizon]
    return np.maximum(pred, 0.0)
