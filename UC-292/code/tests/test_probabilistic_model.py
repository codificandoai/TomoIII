"""Tests del modelo probabilístico."""
from __future__ import annotations

import numpy as np

from config import get_config
from probabilistic_model import NeuralTransitionModel, StateEncoder


def test_state_encoder_shape():
    encoder = StateEncoder(dim=16)
    state = {
        "features": {"latest_price": 150.0, "rsi": 55.0, "trend_direction": 1, "volatility": 0.01},
        "price": 150.0,
        "cash": 10_000.0,
        "position": 10.0,
    }
    action = {"side": "BUY", "quantity": 5.0, "price": 150.0}
    x = encoder.encode_transition(state, action)
    assert x.shape == (16 * 2 + 6,)
    assert np.linalg.norm(x) > 0


def test_neural_model_predicts_after_fit():
    config = get_config().model.probabilistic
    model = NeuralTransitionModel(config)
    state = {"features": {"latest_price": 100.0}, "price": 100.0, "cash": 10_000.0, "position": 0.0}
    action = {"side": "BUY", "quantity": 1.0, "price": 100.0}
    for _ in range(10):
        model.add_experience(state, action, {}, 0.1, True)
    model.fit()
    p, r, u = model.predict(state, action)
    assert 0 <= p <= 1
    assert u >= 0
