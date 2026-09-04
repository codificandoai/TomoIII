"""Tests de integración de la API Flask de UC-307."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["service"] == "uc307-agent-evolution"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    assert len(data["input_cards"]) >= 3


def test_evaluate_endpoint(client):
    payload = {
        "agent_id": "alpha",
        "task_success_rate": 0.92,
        "quality_score": 4.2,
        "efficiency": {
            "tokens_used": 800,
            "tool_calls": 2,
            "latency_seconds": 0.5,
        },
    }
    resp = client.post(
        "/api/v1/evaluate",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["agent_id"] == "alpha"
    assert 0.0 <= data["fitness"] <= 1.0
    assert data["verdict"]
    assert len(data["actions"]) >= 1


def test_evaluate_endpoint_invalid_input(client):
    payload = {
        "agent_id": "bad",
        "task_success_rate": 1.5,  # > 1.0, inválido
        "quality_score": 3.0,
        "efficiency": {"tokens_used": 100, "tool_calls": 1, "latency_seconds": 1.0},
    }
    resp = client.post(
        "/api/v1/evaluate",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_evolve_run_persist(client):
    payload = {
        "agent_id": "persist_agent",
        "action": "persist",
        "dna": {"hyperparams": {"temperature": 0.7}},
    }
    resp = client.post(
        "/api/v1/evolve/run",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["action"] == "persist"
    assert data["eliminated"] is False


def test_evolve_run_mutate(client):
    payload = {
        "agent_id": "mutate_agent",
        "action": "mutate",
        "dna": {"hyperparams": {"temperature": 0.7, "learning_rate": 0.001}},
    }
    resp = client.post(
        "/api/v1/evolve/run",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["action"] == "mutate"
    assert data["adjusted_dna"]["version"] > 1


def test_simulate_task(client):
    payload = {
        "description": "Resumir la reunión de estrategia",
        "task_type": "summarization",
        "subjective": True,
    }
    resp = client.post(
        "/api/v1/simulate/task",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "fitness" in data
    assert data["agent_id"]


def test_metrics_endpoint(client):
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert b"# HELP" in resp.data or b"uc307_" in resp.data


def test_metrics_json_endpoint(client):
    resp = client.get("/api/v1/metrics/json")
    assert resp.status_code == 200
    mode = resp.get_json()["data"]["mode"]
    assert mode in ("prometheus_client", "fallback")
