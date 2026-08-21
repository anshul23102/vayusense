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
