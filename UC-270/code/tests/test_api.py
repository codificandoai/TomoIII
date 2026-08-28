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
    data = resp.get_json()["data"]
    assert data["service"] == "uc270-conflict-resolution"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data


def test_detect_conflict(client) -> None:
    payload = {
        "claims": [
            {"agent_name": "planner", "resource_id": "GPU_1", "need": 0.9, "priority": 8, "flexibility": 0.7, "willingness": 0.8},
            {"agent_name": "optimizer", "resource_id": "GPU_1", "need": 0.8, "priority": 8, "flexibility": 0.4, "willingness": 0.6},
        ]
    }
    resp = client.post("/api/v1/conflict/detect", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    assert data[0]["resource_id"] == "GPU_1"


def test_resolve_conflict(client) -> None:
    payload = {
        "claims": [
            {"agent_name": "planner", "resource_id": "GPU_1", "need": 0.9, "priority": 8, "flexibility": 0.7, "willingness": 0.8},
            {"agent_name": "optimizer", "resource_id": "GPU_1", "need": 0.8, "priority": 8, "flexibility": 0.4, "willingness": 0.6},
        ],
        "profiles": [
            {"name": "planner", "priority": 8, "flexibility": 0.7, "negotiation_skill": 0.8, "reputation": 0.9},
            {"name": "optimizer", "priority": 8, "flexibility": 0.4, "negotiation_skill": 0.6, "reputation": 0.7},
        ],
    }
    resp = client.post("/api/v1/conflict/resolve", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert len(data) == 1
    outcome = data[0]
    assert outcome["winner"] is not None
    assert outcome["strategy"] in ("prioritization", "negotiation", "escalation")
    assert len(outcome["audit_trail"]) > 0


def test_resolve_with_different_priorities(client) -> None:
    payload = {
        "claims": [
            {"agent_name": "a", "resource_id": "MEM", "need": 0.5, "priority": 9, "flexibility": 0.5, "willingness": 0.5},
            {"agent_name": "b", "resource_id": "MEM", "need": 0.9, "priority": 3, "flexibility": 0.9, "willingness": 0.9},
        ],
    }
    resp = client.post("/api/v1/conflict/resolve", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data[0]["winner"] == "a"
    assert data[0]["strategy"] == "prioritization"


def test_propose_state(client) -> None:
    payload = {"agent_name": "test", "resource_id": "R99", "proposed_value": "test_value", "priority_level": 0}
    resp = client.post("/api/v1/state/propose", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["committed_value"] == "test_value"


def test_view_state(client) -> None:
    resp = client.get("/api/v1/state/view?resource=nonexistent")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["value"] is None


def test_audit_trail(client) -> None:
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert isinstance(data, list)
