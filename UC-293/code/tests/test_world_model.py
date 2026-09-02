"""Tests del World Model de trading."""
from __future__ import annotations

from config import AppConfig, get_config
from models import AgentAction, TradingRequest, WorldModelObservation, WorldModelState
from world_model import TradingWorldModel


def _config() -> AppConfig:
    return get_config()


def test_predict_transition_returns_next_state():
    wm = TradingWorldModel(_config().model)
    state = WorldModelState(request_id="r1", symbol="AAPL", price=100.0, cash=10_000.0, position=0.0, portfolio_value=10_000.0)
    action = AgentAction(symbol="AAPL", side="BUY", quantity=10.0, price=100.0)
    transition = wm.predict_transition(state, action)
    assert transition.next_state["step"] == 1
    assert "probability" in transition.to_dict()


def test_rollout_ends_with_final_state():
    wm = TradingWorldModel(_config().model)
    state = WorldModelState(request_id="r1", symbol="AAPL", price=100.0, cash=10_000.0, position=0.0, portfolio_value=10_000.0)
    actions = [
        AgentAction(symbol="AAPL", side="BUY", quantity=5.0, price=100.0),
        AgentAction(symbol="AAPL", side="HOLD", quantity=0.0, price=100.0),
    ]
    final, reward, success, violations = wm.rollout(state, actions)
    assert final.step == len(actions)
    assert isinstance(reward, float)
    assert isinstance(success, bool)


def test_update_from_observation_changes_estimate():
    wm = TradingWorldModel(_config().model)
    obs = WorldModelObservation(
        action_type="BUY",
        item_id="AAPL",
        symbol="AAPL",
        predicted_success_prob=0.9,
        actual_success=False,
        actual_cost=100.0,
        reward=-1.0,
    )
    wm.update_from_observation(obs)
    est = wm._get_estimate("AAPL", "BUY")
    assert est.attempts == 1
    assert est.successes == 0
