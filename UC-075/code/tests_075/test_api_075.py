"""Tests de integración para la API REST UC-075 (card views + endpoints)."""
from __future__ import annotations

import pytest

from api_075 import app, _orchestrator


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.get_json()["service"].startswith("UC-075")


def test_cards_input_output(client):
    r = client.get("/api/v1/cards")
    body = r.get_json()
    assert "input_cards" in body and "output_cards" in body
    assert "POST /api/v1/ct/event" in body["input_cards"]
    assert "run" in body["output_cards"]
    # Card view documents all strategies
    strategies = body["output_cards"]["run"]["strategy_used"]
    assert "incremental" in strategies


def test_on_demand_endpoint_promotes(client):
    r = client.post("/api/v1/ct/on-demand", json={
        "agent_id": "api-agent-1",
        "change_type": "policy_change",
        "detail": "new compliance rule",
        "new_data": [{"f": i} for i in range(5)],
    })
    assert r.status_code == 200
    run = r.get_json()
    assert run["strategy_used"] == "on_demand"
    assert run["status"] in ("promoted", "pending_hitl", "rejected")
    assert run["freeze"]["n_records"] == 5
    assert run["mlflow_run_id"]


def test_event_endpoint_threshold(client):
    r = client.post("/api/v1/ct/event", json={
        "agent_id": "api-agent-2",
        "metrics": {"drift_score": 0.9},
    })
    run = r.get_json()
    assert run["strategy_used"] in ("event_driven",)
    r2 = client.post("/api/v1/ct/event", json={
        "agent_id": "api-agent-2",
        "metrics": {"drift_score": 0.001},
    })
    assert r2.get_json()["status"] == "no_trigger"


def test_incremental_endpoint(client):
    r = client.post("/api/v1/ct/incremental", json={
        "agent_id": "api-agent-3",
        "batch": [{"f": 1}],
        "replay_buffer": [{"f": 0}],
    })
    assert r.get_json()["strategy_used"] == "incremental"


def test_runs_and_detail(client):
    r = client.post("/api/v1/ct/on-demand", json={
        "agent_id": "api-agent-4",
        "change_type": "incident",
        "detail": "regression",
    })
    run_id = r.get_json()["run_id"]
    r2 = client.get(f"/api/v1/ct/runs/{run_id}")
    assert r2.get_json()["run_id"] == run_id
    r3 = client.get("/api/v1/ct/runs?status=promoted")
    assert isinstance(r3.get_json()["runs"], list)


def test_metrics_endpoint(client):
    r = client.get("/api/v1/ct/metrics")
    assert r.status_code == 200
    assert b"uc075_" in r.data


def test_audit_chain_endpoint(client):
    client.post("/api/v1/ct/on-demand", json={
        "agent_id": "api-agent-5",
        "change_type": "data_source_change",
        "detail": "new source v2",
    })
    r = client.get("/api/v1/ct/audit")
    body = r.get_json()
    assert body["chain_valid"] is True
    assert len(body["records"]) >= 1


def test_dashboard_and_loki(client):
    assert client.get("/api/v1/ct/dashboard").status_code == 200
    assert isinstance(client.get("/api/v1/ct/loki").get_json()["lines"], list)


def test_on_demand_validation(client):
    r = client.post("/api/v1/ct/on-demand", json={"agent_id": "x"})
    assert r.status_code == 400


def test_resolve_hitl_not_found(client):
    r = client.post("/api/v1/ct/runs/nope/resolve-hitl",
                    json={"approved": True, "approver": "ops@utron.ai"})
    assert r.status_code == 404
