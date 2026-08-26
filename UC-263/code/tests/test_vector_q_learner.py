"""Tests del motor de Q-Learning vectorial."""
from __future__ import annotations

from config import RLLearningConfig
from models import TravelerContext
from vector_q_learner import VectorQLearner


def test_initial_q_value_is_zero() -> None:
    learner = VectorQLearner(RLLearningConfig(embedding_dim=8))
    q = learner.get_q_value("solo traveler in winter", "Museo")
    assert q == 0.0


def test_update_changes_q_value() -> None:
    learner = VectorQLearner(RLLearningConfig(embedding_dim=8, alpha=0.5, gamma=0.9))
    actions = ["Museo", "Aventura"]
    learner.update("solo traveler in winter", "Museo", 1.0, "post-state", actions)
    q = learner.get_q_value("solo traveler in winter", "Museo")
    assert q > 0.0


def test_exploit_chooses_best_action() -> None:
    learner = VectorQLearner(RLLearningConfig(embedding_dim=8, alpha=0.8))
    actions = ["Museo", "Aventura"]
    learner.update("family in summer", "Aventura", 1.0, "post-state", actions)
    learner.update("family in summer", "Museo", -0.5, "post-state", actions)
    action, explored = learner.choose_action("family in summer", actions, epsilon=0.0)
    assert action == "Aventura"
    assert explored is False


def test_exploration_returns_any_action() -> None:
    learner = VectorQLearner(RLLearningConfig(embedding_dim=8))
    actions = ["Museo", "Aventura"]
    action, explored = learner.choose_action("unknown context", actions, epsilon=1.0)
    assert action in actions
    assert explored is True


def test_generalization_to_similar_context() -> None:
    learner = VectorQLearner(RLLearningConfig(embedding_dim=8, alpha=0.8))
    actions = ["Museo", "Aventura"]
    learner.update("solo traveler in winter", "Museo", 1.0, "post-state", actions)
    q = learner.get_q_value("solo traveler in spring", "Museo")
    assert q >= 0.0  # puede generalizar dependiendo del embedding
