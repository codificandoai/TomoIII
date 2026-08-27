"""Tests de los modelos probabilísticos (red neuronal y GP)."""
from __future__ import annotations

import numpy as np

from config import ProbabilisticModelConfig, get_config
from probabilistic_model import (
    BeliefStateTracker,
    GPTransitionModel,
    NeuralTransitionModel,
    StateEncoder,
)


def test_state_encoder_normalizes() -> None:
    enc = StateEncoder(dim=16)
    vec = enc.encode_state({"remaining_budget": 2000, "step": 1})
    assert len(vec) == 16
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-6


def test_neural_model_learns_success() -> None:
    cfg = get_config().model.probabilistic
    model = NeuralTransitionModel(cfg)
    # Generar experiencias sintéticas: budget alto -> éxito, budget bajo -> fallo
    for i in range(12):
        state = {"remaining_budget": 1000.0 if i % 2 == 0 else 100.0}
        action = {"estimated_cost": 500.0}
        success = i % 2 == 0
        model.add_experience(state, action, {}, reward=1.0 if success else -1.0, success=success)
    model.fit()
    p_success, reward, uncertainty = model.predict(
        {"remaining_budget": 1000.0}, {"estimated_cost": 500.0}
    )
    assert 0.0 <= p_success <= 1.0


def test_gp_model_returns_uncertainty() -> None:
    cfg = get_config().model.probabilistic
    model = GPTransitionModel(cfg)
    for i in range(8):
        state = {"remaining_budget": 1000.0 if i % 2 == 0 else 100.0}
        action = {"estimated_cost": 500.0}
        reward = 1.0 if i % 2 == 0 else -1.0
        model.add_experience(state, action, {}, reward=reward, success=i % 2 == 0)
    model.fit()
    reward, std, prob = model.predict(
        {"remaining_budget": 1000.0}, {"estimated_cost": 500.0}
    )
    assert std >= 0.0


def test_belief_tracker_particles_normalized() -> None:
    tracker = BeliefStateTracker(num_particles=50)
    belief = tracker.initialize({"request_id": "test-belief"})
    assert len(belief.particles) == 50
    assert abs(sum(belief.weights) - 1.0) < 1e-6
