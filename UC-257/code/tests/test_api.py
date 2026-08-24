"""Tests de integración de la API Flask."""
import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["service"] == "uc257-travel-agents"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert any("/api/v1/agent/run" in c["endpoint"] for c in data["input_cards"])


def test_agent_run(client):
    payload = {
        "origin": "Madrid",
        "destination": "París",
        "departure_date": "2026-07-15",
        "return_date": "2026-07-18",
        "travelers": 1,
        "budget": 500.0,
        "meeting_ids": ["meet-15"],
    }
    resp = client.post("/api/v1/agent/run", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "completed"
    assert data["final_state"]["selected_flight"] is not None
    assert data["summary"]


def test_assistant_chat(client):
    resp = client.post(
        "/api/v1/assistant/chat",
        json={"user_id": "u1", "message": "Busca vuelos de Madrid a París"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["mode"] == "assistant"
    assert data["action"]["success"] is True


def test_inventory_search(client):
    resp = client.get(
        "/api/v1/inventory/flights?origin=Madrid&destination=París&date=2026-07-15"
    )
    assert resp.status_code == 200
    flights = resp.get_json()["data"]
    assert len(flights) == 3


def test_simulate_flight_cancellation(client):
    # Ejecutar viaje
    payload = {
        "origin": "Madrid",
        "destination": "París",
        "departure_date": "2026-07-15",
        "return_date": "2026-07-18",
        "meeting_ids": ["meet-15"],
    }
    run_resp = client.post("/api/v1/agent/run", json=payload)
    request_id = run_resp.get_json()["data"]["request_id"]
    flight_id = run_resp.get_json()["data"]["final_state"]["selected_flight"]["flight_id"]

    sim_resp = client.post(
        "/api/v1/agent/simulate",
        json={"request_id": request_id, "event_type": "flight_cancelled", "payload": {"flight_id": flight_id}},
    )
    assert sim_resp.status_code == 200
    data = sim_resp.get_json()["data"]
    state = data["state"]
    assert state["selected_flight"]["flight_id"] != flight_id
    assert any("Rebook" in n for n in data["notifications"])
