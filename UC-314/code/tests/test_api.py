"""Tests de la API REST Flask de UC-314."""
from __future__ import annotations

import pytest

from api import app


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "input_cards" in data["data"]
    assert "output_cards" in data["data"]


def test_list_tools(client):
    resp = client.get("/api/v1/tools")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0


def test_plan_endpoint(client):
    resp = client.post("/api/v1/plan", json={"goal": "Planificar campaña de marketing"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "plan" in data
    assert "metrics" in data


def test_plan_missing_goal(client):
    resp = client.post("/api/v1/plan", json={})
    assert resp.status_code == 400


def test_evaluate_plan(client):
    plan_resp = client.post("/api/v1/plan", json={"goal": "Enviar correo electrónico a leads"})
    plan = plan_resp.get_json()["data"]["plan"]
    resp = client.post("/api/v1/plan/evaluate", json={"plan": plan})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "audit_score" in data


def test_root_cause_endpoint(client):
    resp = client.post(
        "/api/v1/causal/root-cause",
        json={
            "task_id": "T-1",
            "failed_tool": "PricingAPI",
            "error_msg": "ConnectionTimeout",
            "context": "test",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "formal_causal_trace" in data


def test_causal_graph_get(client):
    resp = client.post("/api/v1/causal/graph", json={"action": "get"})
    assert resp.status_code == 200


def test_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
