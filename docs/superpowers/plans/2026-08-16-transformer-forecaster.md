# Global Transformer Forecaster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train one global, from-scratch Transformer forecaster across all (city, parameter) series in the archive, and slot it into the existing forecast bench (`ml/bench.py`) as a fifth honestly-scored competitor alongside naive, damped-trend, gradient boosting, and BigQuery ARIMA_PLUS.

**Architecture:** A small (2 layers, 4 heads, d_model=64) Transformer encoder with learned city and pollutant embeddings, trained once offline on data up to a hard leakage-safe cutoff date, then loaded read-only for inference inside the existing bench's per-series backtest loop — never refit per fold, unlike the other local methods.

**Tech Stack:** PyTorch (new dependency), pandas/numpy (already present), pytest.

## Global Constraints

- `CONTEXT_DAYS = 60` — trailing days of history fed to the model per prediction.
- `TEST_MARGIN_DAYS = 45` — days withheld from training; must always exceed `N_FOLDS * HORIZON` (`ml/backtest.py`: `8 * 3 = 24`). Enforced by `assert_leakage_margin_safe()`, not just documented.
- Training loss is MAE (`nn.L1Loss`), matching the metric `ml/backtest.py`'s `mae()` scores every method on.
- The model is trained for the max horizon it will ever be asked for (`FINAL_HORIZON = 7`, matching `ml/bench.py`); shorter horizon requests (the bench's fold horizon of 3) are served by slicing the same prediction, not by training a second model.
- Every new module lives under `ml/`, following the existing package's flat layout (`ml/features.py`, `ml/forecasters.py`, `ml/backtest.py`, `ml/bench.py` are all siblings, no subpackages).
- Reuse `ml/features.py`'s `_seasonal()` for date encoding rather than reimplementing it — keeps one seasonal-feature definition in the codebase, not two that can drift apart.
- No changes to `agents/tools.py` or any frontend template — the existing `get_forecast()` / `forecast_bench.json` consumption path already handles a method that wins a series' backtest but has no served forecast row (see `ml/bench.py`'s existing comment about `arima_plus`), and this plan reuses that exact fallback behavior for the transformer.

---

### Task 1: Leakage-margin safety guard

**Files:**
- Create: `ml/transformer_config.py`
- Test: `tests/test_transformer_config.py`

**Interfaces:**
- Produces: `CONTEXT_DAYS: int`, `TEST_MARGIN_DAYS: int`, `D_MODEL: int`, `N_HEADS: int`, `N_LAYERS: int`, `N_CITIES: int`, `N_PARAMS: int`, `class LeakageMarginError(ValueError)`, `assert_leakage_margin_safe(margin_days: int = TEST_MARGIN_DAYS) -> None`.

This is the single most important test in the whole feature — it's the one guarding against the exact failure mode (training-time data leaking into what a backtest fold treats as unseen future) named as the main risk when this lane was chosen.

- [ ] **Step 1: Write the failing test**

Create `tests/test_transformer_config.py`:

```python
import pytest

from ml.backtest import HORIZON, N_FOLDS
from ml.transformer_config import LeakageMarginError, assert_leakage_margin_safe


def test_default_margin_is_safe():
    assert_leakage_margin_safe()  # should not raise


def test_margin_equal_to_fold_span_raises():
    with pytest.raises(LeakageMarginError):
        assert_leakage_margin_safe(N_FOLDS * HORIZON)


def test_margin_below_fold_span_raises():
    with pytest.raises(LeakageMarginError):
        assert_leakage_margin_safe(N_FOLDS * HORIZON - 1)


def test_margin_above_fold_span_is_safe():
    assert_leakage_margin_safe(N_FOLDS * HORIZON + 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense" && source .venv/bin/activate && pytest tests/test_transformer_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.transformer_config'`

- [ ] **Step 3: Write minimal implementation**

Create `ml/transformer_config.py`:

```python
"""Shared constants and the leakage-margin safety check for the global
Transformer forecaster. Kept separate from the training script so both
ml/train_transformer.py and its tests import the same guard function
instead of the assertion being duplicated (and able to silently drift)
between them. See docs/superpowers/specs/2026-08-16-transformer-forecaster-design.md,
'The leakage trap this design has to avoid'."""
from __future__ import annotations

from .backtest import HORIZON, N_FOLDS

CONTEXT_DAYS = 60          # trailing days of history fed to the model
TEST_MARGIN_DAYS = 45      # days withheld from training entirely
D_MODEL = 64
N_HEADS = 4
N_LAYERS = 2
N_CITIES = 36
N_PARAMS = 6


class LeakageMarginError(ValueError):
    """Raised when a training margin no longer safely exceeds the bench's
    fold span."""


def assert_leakage_margin_safe(margin_days: int = TEST_MARGIN_DAYS) -> None:
    fold_span = N_FOLDS * HORIZON
    if margin_days <= fold_span:
        raise LeakageMarginError(
            f"margin_days ({margin_days}) must exceed the bench's fold "
            f"span ({N_FOLDS} folds * {HORIZON} days = {fold_span} days), or "
            f"the model's one-time training pass could see data that a "
            f"backtest fold treats as unseen future."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transformer_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add ml/transformer_config.py tests/test_transformer_config.py
git commit -m "Add leakage-margin safety guard for the Transformer forecaster"
```

---

### Task 2: Model architecture

**Files:**
- Create: `ml/transformer_model.py`
- Test: `tests/test_transformer_model.py`

**Interfaces:**
- Consumes: `CONTEXT_DAYS, D_MODEL, N_HEADS, N_LAYERS, N_CITIES, N_PARAMS` from `ml.transformer_config` (Task 1).
- Produces: `class SequenceTransformer(nn.Module)` with `__init__(self, horizon, n_value_features=5, d_model=D_MODEL, n_heads=N_HEADS, n_layers=N_LAYERS, n_cities=N_CITIES, n_params=N_PARAMS)` and `forward(self, x, city_idx, param_idx) -> torch.Tensor` where `x` is `(batch, CONTEXT_DAYS, n_value_features)`, `city_idx`/`param_idx` are `(batch,)` long tensors, and the return is `(batch, horizon)`.

`n_value_features=5` is the normalized pollutant value plus the four seasonal features from `ml/features.py`'s `_seasonal()` (`dow_sin`, `dow_cos`, `doy_sin`, `doy_cos`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_transformer_model.py`:

```python
import torch

from ml.transformer_config import CONTEXT_DAYS
from ml.transformer_model import SequenceTransformer


def test_forward_pass_shape():
    model = SequenceTransformer(horizon=3)
    batch = 4
    x = torch.randn(batch, CONTEXT_DAYS, 5)
    city_idx = torch.randint(0, 36, (batch,))
    param_idx = torch.randint(0, 6, (batch,))
    out = model(x, city_idx, param_idx)
    assert out.shape == (batch, 3)


def test_forward_pass_is_finite():
    model = SequenceTransformer(horizon=3)
    x = torch.randn(2, CONTEXT_DAYS, 5)
    city_idx = torch.zeros(2, dtype=torch.long)
    param_idx = torch.zeros(2, dtype=torch.long)
    out = model(x, city_idx, param_idx)
    assert torch.isfinite(out).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transformer_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.transformer_model'`

- [ ] **Step 3: Write minimal implementation**

Create `ml/transformer_model.py`:

```python
"""Architecture for the global Transformer forecaster. Kept separate from
ml/train_transformer.py so ml/transformer_forecaster.py's inference-only
loader can import just the class definition without pulling in
training-only dependencies (optimizer, training loop, etc.)."""
from __future__ import annotations

import math

import torch
from torch import nn

from .transformer_config import CONTEXT_DAYS, D_MODEL, N_CITIES, N_HEADS, N_LAYERS, N_PARAMS


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = CONTEXT_DAYS):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class SequenceTransformer(nn.Module):
    """Predicts `horizon` future daily values from a CONTEXT_DAYS window of
    (normalized value, seasonal features), conditioned on which city and
    pollutant the series belongs to via learned embeddings -- this is the
    mechanism that makes it one global model instead of 36 independent
    per-city models."""

    def __init__(self, horizon: int, n_value_features: int = 5,
                 d_model: int = D_MODEL, n_heads: int = N_HEADS,
                 n_layers: int = N_LAYERS, n_cities: int = N_CITIES,
                 n_params: int = N_PARAMS):
        super().__init__()
        self.horizon = horizon
        self.city_embed = nn.Embedding(n_cities, d_model)
        self.param_embed = nn.Embedding(n_params, d_model)
        self.input_proj = nn.Linear(n_value_features, d_model)
        self.pos_encoding = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=d_model * 4,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.output_head = nn.Linear(d_model, horizon)

    def forward(self, x: torch.Tensor, city_idx: torch.Tensor,
                param_idx: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(x)
        h = h + self.city_embed(city_idx).unsqueeze(1) + self.param_embed(param_idx).unsqueeze(1)
        h = self.pos_encoding(h)
        h = self.encoder(h)
        pooled = h[:, -1, :]  # final timestep's hidden state summarizes the window
        return self.output_head(pooled)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transformer_model.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ml/transformer_model.py tests/test_transformer_model.py
git commit -m "Add global Transformer forecaster architecture"
```

---

### Task 3: Sliding-window dataset builder

**Files:**
- Create: `ml/transformer_dataset.py`
- Test: `tests/test_transformer_dataset.py`

**Interfaces:**
- Consumes: `CONTEXT_DAYS` from `ml.transformer_config` (Task 1), `_seasonal` from `ml.features` (existing).
- Produces: `@dataclass class Vocab(city_to_idx: dict[str, int], param_to_idx: dict[str, int])`, `build_vocab(daily: pd.DataFrame) -> Vocab`, `build_training_examples(daily: pd.DataFrame, cutoff: pd.Timestamp, horizon: int, vocab: Vocab) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[tuple[str,str], tuple[float,float]]]` returning `(X, y, city_idx, param_idx, norm_stats)` where `X.shape == (n, CONTEXT_DAYS, 5)`, `y.shape == (n, horizon)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_transformer_dataset.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transformer_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.transformer_dataset'`

- [ ] **Step 3: Write minimal implementation**

Create `ml/transformer_dataset.py`:

```python
"""Builds sliding-window training examples for the global Transformer
forecaster from data/processed/daily_city.parquet-shaped data, with the
leakage-safety cutoff and per-series normalization the design spec requires.
See docs/superpowers/specs/2026-08-16-transformer-forecaster-design.md."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

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
    {(city, parameter): (mean, std)} computed ONLY from the cutoff-truncated
    history -- ml/transformer_forecaster.py must reuse these exact stats at
    inference time rather than recomputing from a shorter backtest-fold
    slice."""
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily[daily["date"] <= cutoff]

    xs, ys, city_idxs, param_idxs = [], [], [], []
    norm_stats: dict[tuple[str, str], tuple[float, float]] = {}

    for (city, parameter), grp in daily.groupby(["city", "parameter"]):
        grp = grp.sort_values("date")
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transformer_dataset.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add ml/transformer_dataset.py tests/test_transformer_dataset.py
git commit -m "Add sliding-window dataset builder for the Transformer forecaster"
```

---

### Task 4: Training loop with early stopping

**Files:**
- Create: `ml/train_transformer.py`
- Test: `tests/test_train_transformer.py`

**Interfaces:**
- Consumes: `assert_leakage_margin_safe, TEST_MARGIN_DAYS, CONTEXT_DAYS` from `ml.transformer_config` (Task 1); `Vocab, build_vocab, build_training_examples` from `ml.transformer_dataset` (Task 3); `SequenceTransformer` from `ml.transformer_model` (Task 2).
- Produces: `WEIGHTS_DIR: Path`, `train(daily, horizon=7, test_margin_days=TEST_MARGIN_DAYS, max_epochs=200, patience=10, seed=0) -> tuple[SequenceTransformer, Vocab, dict, pd.Timestamp]`, `save(model, vocab, norm_stats, cutoff, horizon=7) -> None` (writes `WEIGHTS_DIR/transformer_forecaster.pt` and `WEIGHTS_DIR/transformer_forecaster.meta.json`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_train_transformer.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_train_transformer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.train_transformer'`

- [ ] **Step 3: Write minimal implementation**

Create `ml/train_transformer.py`:

```python
"""One-time offline training for the global Transformer forecaster. Not
called from the request path -- run by hand (or later, on a schedule, once
a retraining-automation lane exists). Produces
ml/model_weights/transformer_forecaster.pt and a JSON sidecar recording
everything ml/transformer_forecaster.py needs to run inference consistently
with how the model was trained."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from .transformer_config import CONTEXT_DAYS, TEST_MARGIN_DAYS, assert_leakage_margin_safe
from .transformer_dataset import Vocab, build_training_examples, build_vocab
from .transformer_model import SequenceTransformer

ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_DIR = ROOT / "ml" / "model_weights"
HORIZON = 7          # matches FINAL_HORIZON in ml/bench.py
MAX_EPOCHS = 200
PATIENCE = 10
VAL_FRACTION = 0.15
LEARNING_RATE = 1e-3


def train(daily: pd.DataFrame, horizon: int = HORIZON,
          test_margin_days: int = TEST_MARGIN_DAYS,
          max_epochs: int = MAX_EPOCHS, patience: int = PATIENCE,
          seed: int = 0):
    assert_leakage_margin_safe(test_margin_days)
    torch.manual_seed(seed)

    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    latest = daily["date"].max()
    cutoff = latest - pd.Timedelta(days=test_margin_days)

    vocab = build_vocab(daily)
    X, y, city_idx, param_idx, norm_stats = build_training_examples(
        daily, cutoff, horizon, vocab)
    if len(X) == 0:
        raise ValueError(
            "no training windows produced -- check CONTEXT_DAYS/horizon "
            "against the available history before cutoff")

    n = len(X)
    n_val = max(1, int(n * VAL_FRACTION))
    # Rolling-origin split for the internal train/val carve-out too: the
    # validation examples are whichever windows target the latest dates, not
    # a random shuffle, so early stopping is judged the same way the real
    # bench judges every other method -- on the most recent data.
    order = np.argsort(y[:, 0])
    train_idx, val_idx = order[:-n_val], order[-n_val:]

    model = SequenceTransformer(horizon=horizon)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = nn.L1Loss()  # MAE, matching ml/backtest.py's scoring metric

    X_t, y_t = torch.from_numpy(X), torch.from_numpy(y)
    city_t, param_t = torch.from_numpy(city_idx), torch.from_numpy(param_idx)

    best_val, best_state, bad_epochs = float("inf"), None, 0
    for epoch in range(max_epochs):
        model.train()
        optimizer.zero_grad()
        pred = model(X_t[train_idx], city_t[train_idx], param_t[train_idx])
        loss = loss_fn(pred, y_t[train_idx])
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_t[val_idx], city_t[val_idx], param_t[val_idx])
            val_loss = loss_fn(val_pred, y_t[val_idx]).item()

        if val_loss < best_val - 1e-4:
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                break

    model.load_state_dict(best_state)
    return model, vocab, norm_stats, cutoff


def save(model: SequenceTransformer, vocab: Vocab, norm_stats: dict,
         cutoff: pd.Timestamp, horizon: int = HORIZON) -> None:
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), WEIGHTS_DIR / "transformer_forecaster.pt")
    meta = {
        "horizon": horizon,
        "context_days": CONTEXT_DAYS,
        "cutoff": cutoff.isoformat(),
        "city_to_idx": vocab.city_to_idx,
        "param_to_idx": vocab.param_to_idx,
        "norm_stats": {f"{c}|{p}": [mean, std]
                       for (c, p), (mean, std) in norm_stats.items()},
    }
    (WEIGHTS_DIR / "transformer_forecaster.meta.json").write_text(json.dumps(meta, indent=1))


def main() -> None:
    daily = pd.read_parquet(ROOT / "data" / "processed" / "daily_city.parquet")
    model, vocab, norm_stats, cutoff = train(daily)
    save(model, vocab, norm_stats, cutoff)
    print(f"trained on data through {cutoff.date()}, "
          f"{len(vocab.city_to_idx)} cities, {len(vocab.param_to_idx)} parameters")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_train_transformer.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add ml/train_transformer.py tests/test_train_transformer.py
git commit -m "Add offline training loop for the Transformer forecaster"
```

---

### Task 5: Bench-facing inference function

**Files:**
- Create: `ml/transformer_forecaster.py`
- Test: `tests/test_transformer_forecaster.py`

**Interfaces:**
- Consumes: `SequenceTransformer` from `ml.transformer_model` (Task 2); `CONTEXT_DAYS` from `ml.transformer_config` (Task 1); `_seasonal` from `ml.features` (existing); the on-disk artifacts written by Task 4's `save()`.
- Produces: `WEIGHTS_DIR: Path`, `class UnknownSeriesError(Exception)`, `transformer_forecast(train: pd.DataFrame, horizon: int) -> np.ndarray` — same call shape as every entry in `ml/forecasters.py`'s `LOCAL_FORECASTERS`, returning `horizon` non-negative finite values.

Critically: the model is always trained for `FINAL_HORIZON=7` (Task 4's default), but the bench's backtest folds ask for `horizon=3` (`ml/backtest.py`'s `HORIZON`). This function must serve both by predicting the full trained horizon and slicing, not by requiring an exact match.

- [ ] **Step 1: Write the failing test**

Create `tests/test_transformer_forecaster.py`:

```python
import numpy as np
import pandas as pd
import pytest

import ml.train_transformer as tt
import ml.transformer_forecaster as tf
from ml.transformer_forecaster import UnknownSeriesError, transformer_forecast


def _make_daily(n_days=100):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for city in ["Delhi", "Mumbai"]:
        base = 50.0 if city == "Delhi" else 30.0
        for i, d in enumerate(dates):
            val = base + 5 * np.sin(i / 7) + 0.05 * i
            rows.append({"city": city, "parameter": "pm25", "date": d, "mean": val})
    return pd.DataFrame(rows)


@pytest.fixture
def trained_model(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "WEIGHTS_DIR", tmp_path)
    monkeypatch.setattr(tf, "WEIGHTS_DIR", tmp_path)
    tf._load.cache_clear()
    daily = _make_daily(n_days=100)
    model, vocab, norm_stats, cutoff = tt.train(
        daily, horizon=7, test_margin_days=25, max_epochs=5)
    tt.save(model, vocab, norm_stats, cutoff, horizon=7)
    yield daily
    tf._load.cache_clear()


def _series(daily, city="Delhi"):
    return daily[(daily["city"] == city) & (daily["parameter"] == "pm25")]


def test_forecast_returns_requested_horizon(trained_model):
    out = transformer_forecast(_series(trained_model), horizon=3)
    assert out.shape == (3,)
    assert np.isfinite(out).all()
    assert (out >= 0).all()


def test_forecast_slices_down_from_trained_horizon(trained_model):
    full = transformer_forecast(_series(trained_model), horizon=7)
    short = transformer_forecast(_series(trained_model), horizon=3)
    assert full.shape == (7,)
    np.testing.assert_allclose(short, full[:3])


def test_forecast_rejects_horizon_beyond_training(trained_model):
    with pytest.raises(UnknownSeriesError):
        transformer_forecast(_series(trained_model), horizon=10)


def test_forecast_rejects_unknown_city(trained_model):
    series = _series(trained_model).copy()
    series["city"] = "Atlantis"
    with pytest.raises(UnknownSeriesError):
        transformer_forecast(series, horizon=3)


def test_forecast_rejects_short_series(trained_model):
    series = _series(trained_model).tail(10)
    with pytest.raises(UnknownSeriesError):
        transformer_forecast(series, horizon=3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_transformer_forecaster.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml.transformer_forecaster'`

- [ ] **Step 3: Write minimal implementation**

Create `ml/transformer_forecaster.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_transformer_forecaster.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ml/transformer_forecaster.py tests/test_transformer_forecaster.py
git commit -m "Add bench-facing inference for the Transformer forecaster"
```

---

### Task 6: Integrate into the forecast bench

**Files:**
- Modify: `ml/bench.py:1-22` (imports and `METHOD_LABELS`)
- Modify: `ml/bench.py:45-56` (`_final_forecast_rows`)
- Modify: `ml/bench.py:75-86` (`run_bench`)
- Test: `tests/test_bench_transformer.py`

**Interfaces:**
- Consumes: `transformer_forecast, UnknownSeriesError` from `ml.transformer_forecaster` (Task 5); `train, save` from `ml.train_transformer` (Task 4, for the test only).
- Produces: `ml/bench.py`'s `run_bench()` includes `"transformer"` in a series' `mae` dict when the model is trained and compatible with that series; `_final_forecast_rows()` includes `"transformer"` rows under the same condition; `METHOD_LABELS["transformer"]` exists.

- [ ] **Step 1: Write the failing test**

Create `tests/test_bench_transformer.py`:

```python
import numpy as np
import pandas as pd

import ml.bench as bench_mod
import ml.train_transformer as tt
import ml.transformer_forecaster as tf


def _make_daily(n_days=150):
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for city in ["Delhi", "Mumbai"]:
        base = 50.0 if city == "Delhi" else 30.0
        for i, d in enumerate(dates):
            val = base + 5 * np.sin(i / 7) + 0.02 * i
            rows.append({"city": city, "parameter": "pm25", "date": d,
                         "mean": val, "roll7": val})
    return pd.DataFrame(rows)


def test_transformer_appears_in_bench_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(tt, "WEIGHTS_DIR", tmp_path)
    monkeypatch.setattr(tf, "WEIGHTS_DIR", tmp_path)
    tf._load.cache_clear()

    daily = _make_daily()
    model, vocab, norm_stats, cutoff = tt.train(
        daily, horizon=7, test_margin_days=25, max_epochs=5)
    tt.save(model, vocab, norm_stats, cutoff, horizon=7)

    bench, forecasts = bench_mod.run_bench(daily, bq=None)

    assert "transformer" in bench["methods"]
    scored = [s for s in bench["series"] if "transformer" in s["mae"]]
    assert len(scored) > 0
    assert "transformer" in forecasts["method"].unique()

    tf._load.cache_clear()


def test_bench_survives_missing_transformer_weights(tmp_path, monkeypatch):
    # No training run happened -- WEIGHTS_DIR is empty. The bench must still
    # complete and just omit "transformer" from every series' scores.
    monkeypatch.setattr(tf, "WEIGHTS_DIR", tmp_path)
    tf._load.cache_clear()

    daily = _make_daily()
    bench, forecasts = bench_mod.run_bench(daily, bq=None)

    assert all("transformer" not in s["mae"] for s in bench["series"])

    tf._load.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bench_transformer.py -v`
Expected: FAIL — `test_transformer_appears_in_bench_scores` fails its `assert "transformer" in bench["methods"]`, since `ml/bench.py` doesn't reference the transformer yet.

- [ ] **Step 3: Modify `ml/bench.py`**

In `ml/bench.py`, change the imports and `METHOD_LABELS` at the top of the file:

```python
from .backtest import HORIZON, MIN_HISTORY, N_FOLDS, backtest_series
from .forecasters import LOCAL_FORECASTERS
from .transformer_forecaster import UnknownSeriesError, transformer_forecast

ROOT = Path(__file__).resolve().parent.parent
FINAL_HORIZON = 7
METHOD_LABELS = {
    "naive": "Naive persistence",
    "damped_trend": "Damped trend",
    "gbt": "Gradient boosting",
    "arima_plus": "BigQuery ML ARIMA_PLUS",
    "transformer": "Transformer (global, multi-city)",
}
```

In `_final_forecast_rows`, replace:

```python
    rows = []
    for name, fn in LOCAL_FORECASTERS.items():
        for t, v in enumerate(fn(series, FINAL_HORIZON), start=1):
            band = residual_std * (1 + 0.25 * t)
            rows.append({
                "city": city, "parameter": parameter, "method": name,
                "date": str((last_date + pd.Timedelta(days=t)).date()),
                "value": round(float(v), 1),
                "low": round(max(0.0, float(v) - band), 1),
                "high": round(float(v) + band, 1),
            })
    return rows
```

with:

```python
    rows = []
    forecasters = {**LOCAL_FORECASTERS, "transformer": transformer_forecast}
    for name, fn in forecasters.items():
        try:
            values = fn(series, FINAL_HORIZON)
        except (UnknownSeriesError, FileNotFoundError):
            # Series outside the trained model's vocabulary/history, or no
            # trained model artifact present in this environment yet -- skip
            # this method for this series, the same way arima_plus is
            # already skipped when it has no current forecast row (see the
            # comment on bq["forecasts"] below).
            continue
        for t, v in enumerate(values, start=1):
            band = residual_std * (1 + 0.25 * t)
            rows.append({
                "city": city, "parameter": parameter, "method": name,
                "date": str((last_date + pd.Timedelta(days=t)).date()),
                "value": round(float(v), 1),
                "low": round(max(0.0, float(v) - band), 1),
                "high": round(float(v) + band, 1),
            })
    return rows
```

In `run_bench`, replace:

```python
        scores = backtest_series(grp, LOCAL_FORECASTERS)
        if bq:
            match = next((s for s in bq["series"]
                          if s["city"] == city and s["parameter"] == parameter), None)
            if match:
                scores["arima_plus"] = float(match["mae"])
        series_out.append({
```

with:

```python
        scores = backtest_series(grp, LOCAL_FORECASTERS)
        if bq:
            match = next((s for s in bq["series"]
                          if s["city"] == city and s["parameter"] == parameter), None)
            if match:
                scores["arima_plus"] = float(match["mae"])
        try:
            transformer_scores = backtest_series(grp, {"transformer": transformer_forecast})
            scores["transformer"] = transformer_scores["transformer"]
        except (UnknownSeriesError, FileNotFoundError):
            # Series outside the trained model's vocabulary/history, or no
            # trained model artifact present in this environment yet -- the
            # transformer is simply absent from this series' comparison,
            # the same way arima_plus is absent without a bq_results.json
            # match.
            pass
        series_out.append({
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bench_transformer.py -v`
Expected: 2 passed

Then run the full suite to confirm nothing else broke:

Run: `pytest -q`
Expected: all tests pass (112 existing + 4 + 2 + 3 + 2 + 5 + 2 new = 130)

- [ ] **Step 5: Commit**

```bash
git add ml/bench.py tests/test_bench_transformer.py
git commit -m "Score the Transformer forecaster in the forecast bench"
```

---

### Task 7: Train for real, commit the artifact, wire up the dependency

**Files:**
- Modify: `requirements.txt`
- Create (generated, not hand-written): `ml/model_weights/transformer_forecaster.pt`, `ml/model_weights/transformer_forecaster.meta.json`

**Interfaces:**
- Consumes: `ml.train_transformer.main()` (Task 4), the real `data/processed/daily_city.parquet`.
- Produces: committed model weights so the bench is reproducible by anyone who clones the repo, without needing a GPU or to retrain first — the same reproducibility property `benchmark/benchmark_results.json` already has for the GPU speedup number.

- [ ] **Step 1: Add the new dependency**

Append to `requirements.txt`:

```
torch
```

- [ ] **Step 2: Install it**

Run: `cd "/Users/aj.ts1758/Downloads/Gen AI Academy/vayusense" && source .venv/bin/activate && pip install torch`
Expected: successful install (CPU build is fine — this model is small enough to train on CPU in a few minutes; no GPU requirement for training or inference).

- [ ] **Step 3: Run the real training**

Run: `python -m ml.train_transformer`
Expected: prints `trained on data through <date>, 36 cities, 6 parameters` and creates `ml/model_weights/transformer_forecaster.pt` and `ml/model_weights/transformer_forecaster.meta.json`.

- [ ] **Step 4: Run the real bench and confirm the transformer is scored**

Run: `python -m ml.bench`
Expected: prints a summary line; then verify:

```bash
python3 -c "
import json
b = json.load(open('benchmark/forecast_bench.json'))
assert 'transformer' in b['methods']
scored = [s for s in b['series'] if 'transformer' in s['mae']]
print(f'{len(scored)} / {len(b[\"series\"])} series scored the transformer')
wins = [s for s in scored if s['winner'] == 'transformer']
print(f'transformer won {len(wins)} series')
"
```

Expected: prints two lines; `scored` should be greater than 0 (most/all series that pass `MIN_HISTORY` should have enough history for `CONTEXT_DAYS + N_FOLDS*HORIZON`, but zero wins is fine and expected to be plausible — a from-scratch model competing honestly against four established baselines for the first time may lose most or all series, and that's real data for the interview story, not a bug to fix.

- [ ] **Step 5: Empirically verify no real fold overlaps the training cutoff**

This is the belt-and-suspenders check the design spec calls for beyond the date-math assertion in Task 1 — confirms, against the real archive and the real `make_folds()` output, that the stored cutoff is never later than any fold's earliest test-window date:

```bash
python3 -c "
import json
import pandas as pd
from ml.backtest import make_folds, MIN_HISTORY

meta = json.loads(open('ml/model_weights/transformer_forecaster.meta.json').read())
cutoff = pd.Timestamp(meta['cutoff'])
daily = pd.read_parquet('data/processed/daily_city.parquet')
daily['date'] = pd.to_datetime(daily['date'])

violations = 0
for (city, parameter), grp in daily.groupby(['city', 'parameter']):
    grp = grp.sort_values('date').reset_index(drop=True)
    if len(grp) < MIN_HISTORY:
        continue
    for start, end in make_folds(len(grp)):
        fold_start_date = grp['date'].iloc[start]
        if fold_start_date <= cutoff:
            violations += 1
            print(f'LEAKAGE RISK: {city}/{parameter} fold starting '
                  f'{fold_start_date.date()} <= cutoff {cutoff.date()}')
assert violations == 0, f'{violations} fold(s) overlap the training cutoff'
print('no fold overlaps the training cutoff -- leakage guard holds empirically')
"
```

Expected: `no fold overlaps the training cutoff -- leakage guard holds empirically`, zero violation lines printed. If this ever fails, the fix is increasing `TEST_MARGIN_DAYS` in `ml/transformer_config.py` and retraining (Steps 3-4) — never silencing the check.

- [ ] **Step 6: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass (130, per Task 6's count).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt ml/model_weights/transformer_forecaster.pt ml/model_weights/transformer_forecaster.meta.json benchmark/forecast_bench.json data/processed/forecasts.parquet
git commit -m "Train the global Transformer forecaster and commit the artifact"
```

- [ ] **Step 8: Push**

Run: `git push origin main`

---

## After this plan

The forecast bench now has an honest fifth competitor with a real training loop, a real leakage guard, and real win/loss data. The next natural pieces of work — not part of this plan — are: an attention-weight visualization for at least one real prediction (the concrete, demoable artifact the design spec calls out as the definition of "done" for the interview story), and Lane B (MLOps: retraining triggers, drift monitoring) once this model exists to actually operate.
