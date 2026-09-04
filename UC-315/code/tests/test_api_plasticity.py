"""Tests de integración de los nuevos endpoints de plasticidad en la API."""
from __future__ import annotations

import json

import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_plasticity_evaluate(client):
    payload = {
        "agent_id": "test_agent",
        "success": True,
        "confidence": 0.9,
        "coherence": 0.85,
        "tokens_used": 500,
        "tool_calls": 2,
        "latency_seconds": 0.4,
    }
    resp = client.post(
        "/api/v1/brain/plasticity/evaluate",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "fitness" in data
    assert "decision" in data


def test_plasticity_propose_and_apply(client):
    payload = {
        "adjustment_type": "parameter",
        "target": "test_agent",
        "change": {"learning_rate": 0.001},
        "reason": "Test adjustment",
        "risk_level": "low",
    }
    resp = client.post(
        "/api/v1/brain/plasticity/propose",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    proposal_id = resp.get_json()["data"]["proposal_id"]

    resp = client.post(
        "/api/v1/brain/plasticity/apply",
        data=json.dumps({"proposal_id": proposal_id, "approved": True, "approved_by": "tester"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "applied"


def test_cnp_run(client):
    payload = {
        "description": "Ejecutar tarea de trading AAPL",
        "execution_success": True,
    }
    resp = client.post(
        "/api/v1/brain/cnp/run",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["round"]["status"] == "completed"


def test_curiosity_learn(client):
    payload = {
        "problem": "Detecta la tendencia de la serie de precios",
        "expected_answer": "alcista",
    }
    resp = client.post(
        "/api/v1/brain/curiosity/learn",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "outcome" in data
