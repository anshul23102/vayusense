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
# Full-batch gradient descent doesn't scale here: the real archive produces
# tens of thousands of (city, parameter) sliding windows, and a single
# forward pass of a Transformer encoder over that many at once (self-
# attention is O(batch * seq_len^2)) exhausts memory well before it exhausts
# patience. Mini-batching keeps memory bounded regardless of archive size.
BATCH_SIZE = 256


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

    generator = torch.Generator().manual_seed(seed)
    best_val, best_state, bad_epochs = float("inf"), None, 0
    for epoch in range(max_epochs):
        model.train()
        shuffled = train_idx[torch.randperm(len(train_idx), generator=generator).numpy()]
        for start in range(0, len(shuffled), BATCH_SIZE):
            batch = shuffled[start:start + BATCH_SIZE]
            optimizer.zero_grad()
            pred = model(X_t[batch], city_t[batch], param_t[batch])
            loss = loss_fn(pred, y_t[batch])
            loss.backward()
            optimizer.step()

        model.eval()
        val_loss_sum, val_count = 0.0, 0
        with torch.no_grad():
            for start in range(0, len(val_idx), BATCH_SIZE):
                batch = val_idx[start:start + BATCH_SIZE]
                val_pred = model(X_t[batch], city_t[batch], param_t[batch])
                val_loss_sum += loss_fn(val_pred, y_t[batch]).item() * len(batch)
                val_count += len(batch)
        val_loss = val_loss_sum / val_count

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
