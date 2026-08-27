"""Tests del World Model."""
from __future__ import annotations

from config import AppConfig, get_config
from models import PlanAction, TravelPlanRequest, WorldModelObservation, WorldModelState
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def _config() -> AppConfig:
    return get_config()


def test_predict_transition_returns_next_state() -> None:
    wm = TravelWorldModel(_config().model, TravelWorldSimulator(_config().world))
    state = WorldModelState(request_id="r1", remaining_budget=1000)
    action = PlanAction(
        step=1,
        action_type="flight",
        item_id="FL-TEST",
        estimated_cost=200.0,
    )
    transition = wm.predict_transition(state, action)
    assert transition.next_state["step"] == 1
    assert "probability" in transition.to_dict()


def test_rollout_ends_with_final_state() -> None:
    wm = TravelWorldModel(_config().model, TravelWorldSimulator(_config().world))
    state = WorldModelState(request_id="r1", remaining_budget=2000)
    actions = [
        PlanAction(action_type="flight", item_id="FL-1", estimated_cost=200),
        PlanAction(action_type="hotel", item_id="HT-1", estimated_cost=300),
    ]
    final, reward, success, violations = wm.rollout(state, actions)
    assert final.step == len(actions)
    assert isinstance(reward, float)
    assert isinstance(success, bool)


def test_update_from_observation_changes_estimate() -> None:
    wm = TravelWorldModel(_config().model, TravelWorldSimulator(_config().world))
    obs = WorldModelObservation(
        action_type="flight",
        item_id="FL-UPDATE",
        predicted_success_prob=0.9,
        actual_success=False,
        actual_cost=100.0,
        reward=-3.0,
    )
    wm.update_from_observation(obs)
    est = wm._get_estimate("flight", "FL-UPDATE")
    assert est.attempts == 1
    assert est.successes == 0
