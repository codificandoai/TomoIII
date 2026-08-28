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
    assert data["service"] == "uc271-multiagent-k8s-security-hpa"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    assert len(data["input_cards"]) >= 4
    assert len(data["output_cards"]) >= 4


def test_run_task(client) -> None:
    payload = {"task": "Analyze test incident", "priority": 7}
    resp = client.post("/api/v1/task/run", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["winner"] in ("researcher", "coder", "reviewer")
    assert len(data["proposals"]) == 3
    assert data["scaling_decision"] is not None
    assert data["security_context"]["run_as_non_root"] is True


def test_hpa_evaluate(client) -> None:
    payload = {"agent_name": "researcher", "cpu_percent": 85.0, "memory_percent": 75.0, "queue_depth": 8, "replicas_current": 2}
    resp = client.post("/api/v1/hpa/evaluate", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["agent_name"] == "researcher"
    assert data["direction"] in ("scale_up", "scale_down", "no_change")


def test_hpa_status(client) -> None:
    resp = client.get("/api/v1/hpa/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 3


def test_security_generate(client) -> None:
    payload = {"name": "test_agent", "role": "coder", "skill": 0.8, "cost": 1.0, "latency_ms": 200}
    resp = client.post("/api/v1/security/generate", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "rbac" in data
    assert "network_policy" in data
    assert "service_account" in data
    assert "security_context" in data


def test_security_validate_good_agent(client) -> None:
    payload = {"name": "good", "role": "coder", "skill": 0.8, "cost": 1.0, "latency_ms": 200, "service_account": "good-sa"}
    resp = client.post("/api/v1/security/validate", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["valid"] is True
    assert len(data["violations"]) == 0


def test_security_validate_bad_agent(client) -> None:
    payload = {"name": "bad", "role": "coder", "skill": 0.8, "cost": 1.0, "latency_ms": 200, "service_account": ""}
    resp = client.post("/api/v1/security/validate", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["valid"] is False
    assert len(data["violations"]) >= 1


def test_manifests_generate(client) -> None:
    resp = client.post("/api/v1/manifests/generate", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 10
    kinds = {m["kind"] for m in data}
    assert "Deployment" in kinds
    assert "HorizontalPodAutoscaler" in kinds
    assert "NetworkPolicy" in kinds


def test_audit_trail(client) -> None:
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert isinstance(data, list)
