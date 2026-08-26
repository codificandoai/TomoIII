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


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data and "output_cards" in data


def test_recommend(client) -> None:
    payload = {
        "user_id": "api-test",
        "group_type": "solo",
        "age_group": "adult",
        "season": "winter",
        "budget_level": "medium",
        "interests": ["culture"],
        "mood": "curious",
    }
    resp = client.post(
        "/api/v1/rl/recommend",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] == "done"
    from config import get_config
    assert data["last_action"] in get_config().agent.actions


def test_feedback(client) -> None:
    payload = {
        "user_id": "api-test",
        "context": {
            "group_type": "solo",
            "age_group": "adult",
            "season": "winter",
            "budget_level": "medium",
            "interests": ["culture"],
            "mood": "curious",
        },
        "action": "Museo",
        "reward": 1.0,
    }
    resp = client.post(
        "/api/v1/rl/feedback",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["data"]["updated"] is True


def test_memory(client) -> None:
    resp = client.get("/api/v1/rl/memory")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "experiences" in data
    assert "actions" in data
