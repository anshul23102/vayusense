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
