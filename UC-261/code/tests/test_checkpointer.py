"""Tests de memoria persistente vía LangGraph checkpointer."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from config import AppConfig, get_config
from graph import build_agent, resume_agent_threaded, run_agent_threaded
from models import FlightPlanRequest


def _make_request(**overrides) -> FlightPlanRequest:
    defaults = {
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
        "return_date": "2026-09-17",
        "travelers": 1,
        "budget": 2000.0,
        "currency": "USD",
        "preferences": {"seat": "window", "dietary": "vegetarian"},
        "confirm_irreversible": True,
        "predict_delays": False,
        "enable_learning": True,
        "user_id": "checkpoint-user",
    }
    defaults.update(overrides)
    return FlightPlanRequest(**defaults)


def _agent():
    config = AppConfig(
        world=get_config().world,
        predictor=get_config().predictor,
        memory=get_config().memory,
        checkpoint=get_config().checkpoint,
        agent=get_config().agent,
    )
    return build_agent(config, checkpointer=MemorySaver())


def test_threaded_plan_pauses_for_approval() -> None:
    agent = _agent()
    req = _make_request()
    final_state = run_agent_threaded(agent, req, "thread-1", recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "awaiting_approval"
    assert output["thread_id"] == "thread-1"
    assert len(output["approval_actions"]) > 0


def test_threaded_resume_continues_execution() -> None:
    agent = _agent()
    req = _make_request()
    first = run_agent_threaded(agent, req, "thread-2", recursion_limit=50)
    output1 = first["final_output"]
    assert output1["status"] == "awaiting_approval"

    approved = [a["action_id"] for a in output1["approval_actions"]]
    final_state = resume_agent_threaded(agent, "thread-2", approved_action_ids=approved)
    output2 = final_state["final_output"]
    assert output2["status"] == "done"
    assert all(a["status"] != "PENDING_APPROVAL" for a in output2["approval_actions"])


def test_threaded_resume_rejected_finishes() -> None:
    agent = _agent()
    req = _make_request()
    first = run_agent_threaded(agent, req, "thread-3", recursion_limit=50)
    output1 = first["final_output"]
    assert output1["status"] == "awaiting_approval"

    rejected = [a["action_id"] for a in output1["approval_actions"]]
    final_state = resume_agent_threaded(agent, "thread-3", rejected_action_ids=rejected)
    output2 = final_state["final_output"]
    assert output2["status"] == "done"
    assert all(a["status"] == "REJECTED" for a in output2["approval_actions"])
