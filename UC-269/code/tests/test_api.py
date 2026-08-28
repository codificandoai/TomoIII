"""Tests de integración de la API Flask Contract Net."""
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
    assert data["service"] == "uc269-contract-net"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data and "output_cards" in data


def test_run_contract_net(client) -> None:
    payload = {
        "title": "Clasificación de patrones",
        "description": "Extraer características con Fourier y clasificar",
        "requirements": {"domain": "signal_processing", "min_accuracy": 0.9},
    }
    resp = client.post(
        "/api/v1/contractnet/run",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] == "completed"
    assert data["winner"] is not None
    assert len(data["proposals"]) == 3
    assert "report" in data


def test_run_with_custom_workers(client) -> None:
    payload = {
        "title": "Tarea custom",
        "workers": [
            {"name": "alpha", "skill_score": 0.99, "reliability": 0.99, "cost_factor": 1.0, "latency_factor": 0.5},
            {"name": "beta", "skill_score": 0.70, "reliability": 0.80, "cost_factor": 2.0, "latency_factor": 1.5},
        ],
    }
    resp = client.post(
        "/api/v1/contractnet/run",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["winner"] == "alpha"


def test_get_outcome(client) -> None:
    payload = {"title": "Outcome test"}
    run_resp = client.post(
        "/api/v1/contractnet/run",
        data=json.dumps(payload),
        content_type="application/json",
    )
    task_id = run_resp.get_json()["data"]["task_id"]
    resp = client.get(f"/api/v1/contractnet/outcome/{task_id}")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["task_id"] == task_id


def test_metrics_endpoint(client) -> None:
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert b"# HELP" in resp.data


def test_metrics_json(client) -> None:
    resp = client.get("/api/v1/metrics/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["mode"] in ("fallback", "prometheus_client")
