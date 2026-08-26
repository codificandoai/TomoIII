"""Tests de la capa BDI base de UC-261."""
from __future__ import annotations

from typing import Any, Dict, List

from config import AgentConfig, AppConfig, get_config
from external_api import FlightDelayPredictor
from graph import run_agent
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
        "preferences": {"meeting_time": "15:00"},
        "confirm_irreversible": True,
        "predict_delays": True,
        "enable_learning": True,
    }
    defaults.update(overrides)
    return FlightPlanRequest(**defaults)


def _mock_predictor(low: bool = True) -> FlightDelayPredictor:
    class MockPredictor(FlightDelayPredictor):
        def predict(self, flight_items: List[Dict[str, Any]]) -> Dict[str, Any]:
            if low:
                predictions = [
                    {"flight_index": i, "delay_probability": 0.05, "predicted_delay_minutes": 0, "confidence": 0.9}
                    for i in range(len(flight_items))
                ]
            else:
                predictions = [
                    {"flight_index": i, "delay_probability": 0.9, "predicted_delay_minutes": 180, "confidence": 0.9}
                    for i in range(len(flight_items))
                ]
            return {"success": True, "source": "mock", "predictions": predictions}

    return MockPredictor(get_config().predictor)


def _run_config(predictor: FlightDelayPredictor) -> AppConfig:
    return AppConfig(
        world=get_config().world,
        predictor=get_config().predictor,
        memory=get_config().memory,
        agent=AgentConfig(require_confirmation_irreversible=True),
    )


def test_planning_no_delays() -> None:
    req = _make_request(predict_delays=True, user_id="bdi-no-delay", auto_approve_all=True)
    config = _run_config(_mock_predictor(low=True))
    final_state = run_agent(req, config, recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "done"
    assert len(output["itinerary"]) >= 2
    assert all(d["satisfied"] for d in output["desires"])


def test_high_delay_triggers_rebook(monkeypatch) -> None:
    # Simula predictor de retrasos alto para este test
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"delay_probability": 0.9, "predicted_delay_minutes": 180, "confidence": 0.9}
    ]
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: mock_response)

    req = _make_request(predict_delays=True, user_id="bdi-delay", preferences={"meeting_time": "15:00"}, auto_approve_all=True)
    config = _run_config(_mock_predictor(low=False))
    final_state = run_agent(req, config, recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "done"
    actions = [i["action"] for i in output["intentions"]]
    assert "rebook_flight" in actions


def test_confirmation_gate() -> None:
    req = _make_request(confirm_irreversible=False, predict_delays=False, user_id="bdi-confirm")
    config = AppConfig(
        world=get_config().world,
        predictor=get_config().predictor,
        memory=get_config().memory,
        agent=AgentConfig(require_confirmation_irreversible=True),
    )
    final_state = run_agent(req, config, recursion_limit=50)
    output = final_state["final_output"]
    assert output["status"] == "awaiting_confirmation"
    assert output["requires_confirmation"] is True
