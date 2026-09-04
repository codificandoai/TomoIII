"""Tests de la interfaz de plasticidad del cerebro prefrontal UC-313."""
from __future__ import annotations

import pytest

from brain_plasticity_interface import PrefrontalController
from central_brain import CentralBrain
from config import get_config


@pytest.fixture
def controller():
    return PrefrontalController(CentralBrain(get_config()))


def test_get_current_params(controller):
    params = controller.get_current_params()
    assert "model.learning_rate" in params
    assert "model.probabilistic.retrain_after" in params


def test_update_param_requires_plastic_list(controller):
    result = controller.update_param("market.seed", 999, "test")
    assert result["status"] == "rejected"


def test_update_learning_rate(controller):
    prev = controller.get_current_params()["model.learning_rate"]
    result = controller.update_param(
        "model.learning_rate", 0.42, "test lr", approved_by="t"
    )
    assert result["status"] == "applied"
    assert controller.get_current_params()["model.learning_rate"] == 0.42
    assert result["change"]["previous_value"] == prev


def test_retrain_world_model(controller):
    # Alimentar suficientes experiencias
    for i in range(12):
        controller.brain.learn_from_tick("AAPL", 150.0 + i, 150.0 + i + 1)
    result = controller.retrain_world_model("test", approved_by="t")
    assert result["status"] == "applied"
    assert isinstance(result["trained"], bool)


def test_gwt_weights(controller):
    w1 = controller.update_gwt_weight("strategy_x", True, 0.9)
    w2 = controller.update_gwt_weight("strategy_x", False, 0.9)
    assert w1 > 1.0
    assert w2 < w1


def test_freeze_thaw_module(controller):
    assert controller.freeze_module("long_term_vector")["status"] == "frozen"
    assert controller.is_module_frozen("long_term_vector") is True
    assert controller.thaw_module("long_term_vector")["status"] == "thawed"


def test_rollback_restores_baseline(controller):
    original = controller.get_current_params()["model.learning_rate"]
    controller.update_param("model.learning_rate", 0.99, "test", approved_by="t")
    result = controller.rollback()
    assert result["status"] == "rolled_back"
    assert controller.get_current_params()["model.learning_rate"] == original
