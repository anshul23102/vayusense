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
