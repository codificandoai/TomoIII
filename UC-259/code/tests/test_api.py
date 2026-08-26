"""Tests de integración de la API Flask."""
from __future__ import annotations

import json

import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    endpoints = {c["endpoint"] for c in data["input_cards"]}
    assert "POST /api/v1/plan" in endpoints


def test_plan_endpoint_success(client) -> None:
    payload = {
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
        "return_date": "2026-09-17",
        "travelers": 1,
        "budget": 2000,
        "confirm_irreversible": True,
        "preferences": {"meeting_time": "15:00"},
    }
    resp = client.post("/api/v1/plan", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] == "done"
    assert data["total_cost"] > 0
    assert len(data["itinerary"]) >= 2


def test_plan_endpoint_missing_origin(client) -> None:
    payload = {
        "origin": "",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
    }
    resp = client.post("/api/v1/plan", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "awaiting_input"
    assert any("origin" in mi for mi in data["missing_info"])


def test_simulate_event_endpoint(client) -> None:
    payload = {
        "item_id": "FL-TEST-999",
        "event_type": "DELAYED",
        "delay_minutes": 120,
        "reason": "Test delay",
    }
    resp = client.post("/api/v1/simulate/event", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["injected"] is True


def test_last_trace_initially_404(client) -> None:
    import api
    api._last_trace = None
    resp = client.get("/api/v1/agent/last_trace")
    assert resp.status_code == 404
