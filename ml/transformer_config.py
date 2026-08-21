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
