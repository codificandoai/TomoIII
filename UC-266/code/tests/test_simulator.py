"""Tests del motor Monte Carlo."""
from __future__ import annotations

from config import AppConfig, get_config
from critic import PlanCritic
from models import TravelPlanRequest, WorldModelState
from planner import PlanGenerator
from simulator import MonteCarloSimulator
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def _request() -> TravelPlanRequest:
    return TravelPlanRequest(
        origin="Madrid",
        destination="Barcelona",
        departure_date="2026-09-15",
        return_date="2026-09-17",
        travelers=1,
        budget=2000,
        user_id="sim-test",
        preferences={"airline": "Delta"},
    )


def test_simulate_candidates_produces_evaluations() -> None:
    config = get_config()
    simulator_env = TravelWorldSimulator(config.world)
    world_model = TravelWorldModel(config.model, simulator_env)
    mc = MonteCarloSimulator(world_model, config.model)
    planner = PlanGenerator(simulator_env, config.model)
    actions_seq, _ = planner.generate(_request(), num_plans=4)
    initial = WorldModelState(request_id="r1", remaining_budget=2000)
    evaluated = mc.simulate_candidates(actions_seq, initial, _request())
    assert len(evaluated) == 4
    for c in evaluated:
        assert c.estimated_success_prob >= 0.0
        assert c.expected_utility is not None


def test_critic_selects_best_plan() -> None:
    config = get_config()
    simulator_env = TravelWorldSimulator(config.world)
    world_model = TravelWorldModel(config.model, simulator_env)
    mc = MonteCarloSimulator(world_model, config.model)
    planner = PlanGenerator(simulator_env, config.model)
    actions_seq, _ = planner.generate(_request(), num_plans=4)
    initial = WorldModelState(request_id="r1", remaining_budget=2000)
    evaluated = mc.simulate_candidates(actions_seq, initial, _request())
    critic = PlanCritic(config.model)
    best = critic.select_best(evaluated)
    assert best is not None
    assert best.final_score == max(e.final_score for e in evaluated)
