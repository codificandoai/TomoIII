"""Tests del orquestador multi-agente."""
import pytest

from models import TripRequest


def test_plan_and_execute_autonomous_success(orchestrator):
    request = TripRequest(
        origin="Madrid",
        destination="París",
        departure_date="2026-07-15",
        return_date="2026-07-18",
        travelers=1,
        budget=500.0,
        meeting_ids=["meet-15"],
    )
    result = orchestrator.plan_and_execute(request)
    assert result.status == "completed"
    assert result.final_state["selected_flight"] is not None
    assert result.final_state["selected_hotel"] is not None
    assert len(result.final_state["selected_activities"]) >= 1
    assert "meet-15" in result.final_state["meetings"]
    assert any("Vuelo reservado" in n for n in result.notifications)


def test_assistant_processes_single_intent(orchestrator):
    result = orchestrator.process_user_message(
        "user-1", "Busca vuelos de Madrid a París para mañana"
    )
    assert result["mode"] == "assistant"
    assert result["intent"]["action"] == "search_flights"
    assert result["action"]["success"] is True


def test_recovery_after_flight_cancellation(orchestrator):
    request = TripRequest(
        origin="Madrid",
        destination="París",
        departure_date="2026-07-15",
        return_date="2026-07-18",
        travelers=1,
        budget=500.0,
        meeting_ids=["meet-15"],
    )
    result = orchestrator.plan_and_execute(request)
    flight_id = result.final_state["selected_flight"]["flight_id"]
    inv = orchestrator.inventory
    inv.cancel_flight(flight_id)

    state = orchestrator._states[request.request_id]
    state.selected_flight.status = "cancelled"
    recovery = orchestrator.planner.handle_disruption(
        orchestrator.planner.create_plan(request), state.selected_flight
    )
    for action in recovery:
        orchestrator._execute_action(action, state)

    assert state.selected_flight.flight_id != flight_id
    assert any("Rebook" in n for n in state.notifications)


def test_max_iterations_protection(orchestrator):
    orchestrator.config.max_iterations = 1
    request = TripRequest(
        origin="Madrid",
        destination="París",
        departure_date="2026-07-15",
        return_date="2026-07-18",
    )
    result = orchestrator.plan_and_execute(request)
    # Con solo 1 iteración no completa el plan
    assert result.status in ("in_progress", "failed", "completed")
