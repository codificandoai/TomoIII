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
    assert resp.get_json()["data"]["service"] == "uc265-probabilistic-model-based-planner"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data and "output_cards" in data


def test_plan_endpoint(client) -> None:
    payload = {
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
        "return_date": "2026-09-17",
        "travelers": 1,
        "budget": 2000,
        "user_id": "api-model-test",
        "preferences": {"airline": "Delta"},
    }
    resp = client.post(
        "/api/v1/model/plan",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] == "awaiting_confirmation"
    assert data["selected_plan"] is not None


def test_world_model_endpoint(client) -> None:
    resp = client.get("/api/v1/model/world_model")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "estimates" in data


def test_feedback_endpoint(client) -> None:
    payload = {
        "action_type": "flight",
        "item_id": "FL-TEST-API",
        "predicted_success_prob": 0.95,
        "actual_success": False,
        "actual_cost": 150.0,
        "reward": -3.0,
    }
    resp = client.post(
        "/api/v1/model/feedback",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["data"]["updated"] is True
