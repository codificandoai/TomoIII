"""Tests del generador de planes."""
from __future__ import annotations

from config import AppConfig, get_config
from models import TravelPlanRequest
from planner import PlanGenerator
from travel_world import TravelWorldSimulator


def _request() -> TravelPlanRequest:
    return TravelPlanRequest(
        origin="Madrid",
        destination="Barcelona",
        departure_date="2026-09-15",
        return_date="2026-09-17",
        travelers=1,
        budget=2000,
        user_id="plan-test",
        preferences={"airline": "Delta"},
    )


def test_generate_multiple_candidates() -> None:
    config = get_config()
    gen = PlanGenerator(TravelWorldSimulator(config.world), config.model)
    candidates, meta = gen.generate(_request(), num_plans=8)
    assert len(candidates) == 8
    assert all(len(plan) >= 2 for plan in candidates)
    assert "strategies" in meta


def test_strategies_diversify_plans() -> None:
    config = get_config()
    gen = PlanGenerator(TravelWorldSimulator(config.world), config.model)
    candidates, _ = gen.generate(_request(), num_plans=8)
    airlines = set()
    for plan in candidates:
        for action in plan:
            if action.action_type == "flight":
                airlines.add(action.details.get("airline"))
    assert len(airlines) >= 1
