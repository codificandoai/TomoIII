"""Tests del grafo LangGraph integrado."""
from __future__ import annotations

from config import AppConfig, get_config
from graph import build_agent, run_agent
from models import TravelPlanRequest


def _request(confirm: bool = False) -> TravelPlanRequest:
    return TravelPlanRequest(
        origin="Madrid",
        destination="Barcelona",
        departure_date="2026-09-15",
        return_date="2026-09-17",
        travelers=1,
        budget=2000,
        user_id="graph-test",
        preferences={"airline": "Delta"},
        confirm_irreversible=confirm,
    )


def test_build_agent_runs_without_errors() -> None:
    config = get_config()
    agent = build_agent(config)
    assert agent is not None


def test_run_agent_returns_plan_ready_for_confirmation() -> None:
    config = get_config()
    final_state = run_agent(_request(confirm=False), config, recursion_limit=50)
    output = final_state.get("final_output", {})
    assert output["status"] in ("awaiting_confirmation", "done")
    assert output["selected_plan"] is not None
    assert len(output["candidates"]) > 0
    assert len(output["evaluations"]) > 0


def test_run_agent_executes_with_confirmation() -> None:
    config = get_config()
    final_state = run_agent(_request(confirm=True), config, recursion_limit=50)
    output = final_state.get("final_output", {})
    assert output["status"] == "done"
    assert output["execution_result"] is not None
    assert output["execution_result"]["total_cost"] > 0
