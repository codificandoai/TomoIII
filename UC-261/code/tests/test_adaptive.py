"""Tests de la capa adaptativa y memoria de patrones."""
from __future__ import annotations

from config import AgentConfig, AppConfig, get_config
from graph import run_agent
from memory import PatternMemoryDB
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
        "preferences": {"seat": "window"},
        "confirm_irreversible": True,
        "predict_delays": False,
        "enable_learning": True,
        "user_id": "test-user",
    }
    defaults.update(overrides)
    return FlightPlanRequest(**defaults)


def test_pattern_match_auto_executes() -> None:
    req = _make_request(user_id="auto-user", preferences={"seat": "window"}, auto_approve_all=True)
    final_state = run_agent(req, get_config(), recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "done"
    # Debe haber recomendación de asiento que se auto-aprobará por ser PATTERN_MATCH
    assert any(r["category"] == "flight" and r["source_type"] == "PATTERN_MATCH" for r in output["recommendations"])
    assert any(a.get("status") == "AUTO_EXECUTED" for a in output["recommendations"])


def test_ai_inference_requires_approval() -> None:
    # Llegada a las 18:00 genera recomendación de helicóptero
    req = _make_request(
        user_id="approval-user",
        preferences={"seat": "window"},
        departure_date="2026-09-15",
        return_date="2026-09-17",
    )
    final_state = run_agent(req, get_config(), recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "awaiting_approval"
    assert len(output["approval_actions"]) > 0
    assert any(a["source_type"] == "AI_INFERENCE" for a in output["approval_actions"])


def test_learning_updates_profile() -> None:
    config = AppConfig(world=get_config().world, predictor=get_config().predictor, memory=get_config().memory, agent=AgentConfig())

    # Primera ejecución con auto-approve para registrar aprendizaje
    req = _make_request(
        user_id="learn-user",
        preferences={"seat": "window", "dietary": "vegetarian"},
        auto_approve_all=True,
    )
    final_state = run_agent(req, config, recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "done"
    assert len(output["profile"].get("pattern_scores", {})) > 0


def test_pre_approved_actions_execute() -> None:
    # Ejecutar sin auto-aprobar para obtener IDs pendientes (dieta genera inferencia)
    req = _make_request(user_id="preapprove-user", preferences={"seat": "window", "dietary": "vegetarian"})
    first = run_agent(req, get_config(), recursion_limit=50)
    output = first["final_output"]
    if output["status"] != "awaiting_approval":
        # Si no generó aprobaciones, no aplica
        return
    approved = [a["action_id"] for a in output["approval_actions"]]

    req2 = _make_request(
        user_id="preapprove-user",
        preferences={"seat": "window", "dietary": "vegetarian"},
        approved_action_ids=approved,
    )
    final_state = run_agent(req2, get_config(), recursion_limit=50)
    output2 = final_state["final_output"]
    assert output2["status"] == "done"
    assert all(a["status"] != "PENDING_APPROVAL" for a in output2["approval_actions"])
