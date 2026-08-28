"""Tests del motor de resiliencia y detección de cambios para UC-266."""
from __future__ import annotations

import numpy as np

from config import get_config
from models import PlanAction, TravelPlanRequest, WorldModelState
from planner import PlanGenerator
from resilience import ResilienceEngine
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def _engine():
    cfg = get_config()
    simulator = TravelWorldSimulator(cfg.world)
    wm = TravelWorldModel(cfg.model, simulator, app_config=cfg)
    planner = PlanGenerator(simulator, cfg.model)
    return ResilienceEngine(wm, planner, cfg)


def test_detect_change_cancellation() -> None:
    engine = _engine()
    action = PlanAction(action_type="flight", item_id="FL-1", estimated_cost=300)
    event = engine.detect_change(
        action,
        predicted_success_prob=0.95,
        observed_success=False,
        predicted_cost=300,
        actual_cost=0,
    )
    assert event is not None
    assert event.event_type == "cancellation"
    assert event.severity > 0.0


def test_detect_change_within_threshold_returns_none() -> None:
    engine = _engine()
    action = PlanAction(action_type="flight", item_id="FL-2", estimated_cost=300)
    event = engine.detect_change(
        action,
        predicted_success_prob=0.95,
        observed_success=True,
        predicted_cost=300,
        actual_cost=305,
        observed_delay=5,
    )
    assert event is None


def test_generate_backup_plans_returns_candidates() -> None:
    engine = _engine()
    request = TravelPlanRequest(
        origin="Madrid",
        destination="Barcelona",
        departure_date="2026-09-15",
        return_date="2026-09-17",
        travelers=1,
        budget=2000,
        preferences={"airline": "Delta"},
    )
    state = WorldModelState(
        request_id=request.request_id,
        remaining_budget=2000,
        preferences=request.preferences,
    )
    backups, meta = engine.generate_backup_plans(request, state)
    assert isinstance(backups, list)
    assert meta.get("generated") is not None or "strategies" in meta


def test_detect_planning_paralysis() -> None:
    engine = _engine()
    event = engine.detect_planning_paralysis(candidates=[{}] * 150, elapsed_seconds=35.0)
    assert event is not None
    assert event.event_type == "planning_paralysis"


def test_recovery_loop_succeeds() -> None:
    cfg = get_config()
    simulator = TravelWorldSimulator(cfg.world)
    wm = TravelWorldModel(cfg.model, simulator, app_config=cfg)
    planner = PlanGenerator(simulator, cfg.model)
    engine = ResilienceEngine(wm, planner, cfg)

    actions = [
        PlanAction(action_type="flight", item_id="FL-MADBAR-100", estimated_cost=200, estimated_success_prob=1.0),
    ]
    final_state, results, success, events = engine.execute_recovery_loop(
        TravelPlanRequest(
            origin="Madrid",
            destination="Barcelona",
            departure_date="2026-09-15",
            return_date="2026-09-17",
            budget=2000,
        ),
        WorldModelState(remaining_budget=2000, preferences={}),
        actions,
        simulator,
    )
    assert len(results) >= 1
    assert final_state is not None
