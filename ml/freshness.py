"""Reports whether the Transformer weights and the precomputed forecast cache
have fallen behind the archive they are served next to. Nothing retrains or
regenerates automatically after the archive changes (the nightly refresh only
moves the archive forward), so this is the check that makes drift visible.

    python -m ml.freshness     # exits 1 when anything is stale
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from .transformer_config import TEST_MARGIN_DAYS

ROOT = Path(__file__).resolve().parent.parent
HORIZON = 7
MODEL_LAG_DAYS = 14  # tolerated gap between the model's cutoff and a fresh retrain's


def check(root: Path = ROOT) -> dict:
    daily = pd.read_parquet(root / "data" / "processed" / "daily_city.parquet", columns=["date"])
    latest = pd.to_datetime(daily["date"]).max()

    meta_path = root / "ml" / "model_weights" / "transformer_forecaster.meta.json"
    model_cutoff = pd.Timestamp(json.loads(meta_path.read_text())["cutoff"])
    expected_cutoff = latest - pd.Timedelta(days=TEST_MARGIN_DAYS)
    model_lag = (expected_cutoff - model_cutoff).days

    forecasts = pd.read_parquet(root / "data" / "processed" / "forecasts.parquet", columns=["date"])
    forecast_end = pd.to_datetime(forecasts["date"]).max()
    needed_end = latest + pd.Timedelta(days=HORIZON)

    return {
        "archive_latest": latest.date().isoformat(),
        "model_cutoff": model_cutoff.date().isoformat(),
        "model_lag_days": model_lag,
        "model_stale": model_lag > MODEL_LAG_DAYS,
        "forecast_end": forecast_end.date().isoformat(),
        "forecast_needed_through": needed_end.date().isoformat(),
        "forecast_stale": forecast_end < needed_end,
    }


def main() -> int:
    r = check()
    print(f"archive latest day     : {r['archive_latest']}")
    print(f"model training cutoff  : {r['model_cutoff']} "
          f"({r['model_lag_days']} days behind a retrain today) "
          f"-> {'STALE, run python -m ml.train_transformer' if r['model_stale'] else 'ok'}")
    print(f"forecasts reach        : {r['forecast_end']} (need {r['forecast_needed_through']}) "
          f"-> {'STALE, run python -m ml.bench' if r['forecast_stale'] else 'ok'}")
    return 1 if (r["model_stale"] or r["forecast_stale"]) else 0


if __name__ == "__main__":
    sys.exit(main())
