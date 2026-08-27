"""Tests del planificador MCTS."""
from __future__ import annotations

from config import MCTSConfig, get_config
from mcts import MCTSPlanner
from models import PlanAction, TravelPlanRequest, WorldModelState
from planner import PlanGenerator
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
        user_id="mcts-test",
    )


def test_mcts_returns_plan() -> None:
    config = get_config()
    simulator_env = TravelWorldSimulator(config.world)
    world_model = TravelWorldModel(config.model, simulator_env, app_config=config)
    planner = PlanGenerator(simulator_env, config.model)
    initial_state = WorldModelState(request_id="r1", remaining_budget=2000)
    levels = planner._action_levels(
        simulator_env.search_flights("Madrid", "Barcelona", "2026-09-15"),
        simulator_env.search_hotels("Barcelona", "2026-09-16", "2026-09-17"),
        simulator_env.search_flights("Barcelona", "Madrid", "2026-09-17"),
        _request(),
        np_random(),
    )
    mcts = MCTSPlanner(world_model, config.model.mcts)
    plan = mcts.search(initial_state, levels)
    assert len(plan) > 0
    assert all(isinstance(a, PlanAction) for a in plan)


def np_random():
    import numpy as np
    return np.random.default_rng(42)
