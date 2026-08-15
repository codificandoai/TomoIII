"""Pruebas de integración del API Flask (`app.py`) de UC-129."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app import app as flask_app, service as flask_service


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_report_incident_requires_type(client):
    response = client.post("/api/v1/incidents", json={})
    assert response.status_code == 400


def test_report_incident_invalid_type(client):
    response = client.post("/api/v1/incidents", json={"incident_type": "NOT_REAL"})
    assert response.status_code == 400


def test_report_incident_success(client):
    response = client.post("/api/v1/incidents", json={
        "incident_type": "JAILBREAK", "severity": "HIGH", "source": "auto_guardrail",
        "model": "llama-3-8b", "summary": "test",
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["incident_type"] == "JAILBREAK"
    assert body["status"] == "DETECTED"


def test_get_incident_not_found(client):
    response = client.get("/api/v1/incidents/does-not-exist")
    assert response.status_code == 404


def test_full_lifecycle_via_api(client):
    create = client.post("/api/v1/incidents", json={"incident_type": "HALLUCINATION"})
    incident_id = create.get_json()["incident_id"]

    detect = client.post(f"/api/v1/incidents/{incident_id}/detect", json={"detection_method": "manual"})
    assert detect.status_code == 200
    assert detect.get_json()["mttd_seconds"] is not None

    resolve = client.post(f"/api/v1/incidents/{incident_id}/resolve", json={
        "resolution_type": "auto_remediation", "success": True, "tokens_during_incident": 50,
    })
    assert resolve.status_code == 200
    assert resolve.get_json()["status"] == "RESOLVED"

    close = client.post(f"/api/v1/incidents/{incident_id}/close", json={"root_cause": "model_drift"})
    assert close.status_code == 200
    assert close.get_json()["root_cause"] == "model_drift"


def test_close_incident_invalid_root_cause(client):
    create = client.post("/api/v1/incidents", json={"incident_type": "BIAS"})
    incident_id = create.get_json()["incident_id"]
    response = client.post(f"/api/v1/incidents/{incident_id}/close", json={"root_cause": "not_real"})
    assert response.status_code == 400


def test_false_positive_endpoint(client):
    create = client.post("/api/v1/incidents", json={"incident_type": "TOXICITY"})
    incident_id = create.get_json()["incident_id"]
    response = client.post(f"/api/v1/incidents/{incident_id}/false-positive")
    assert response.status_code == 200
    assert response.get_json()["is_false_positive"] is True


def test_escalate_endpoint(client):
    create = client.post("/api/v1/incidents", json={"incident_type": "BIAS"})
    incident_id = create.get_json()["incident_id"]
    response = client.post(f"/api/v1/incidents/{incident_id}/escalate", json={
        "reason": "ambiguous", "reviewer_role": "compliance",
    })
    assert response.status_code == 200
    assert response.get_json()["hitl_escalated"] is True


def test_list_incidents_filter_by_type(client):
    client.post("/api/v1/incidents", json={"incident_type": "LATENCY_SPIKE"})
    response = client.get("/api/v1/incidents?incident_type=LATENCY_SPIKE")
    assert response.status_code == 200
    assert all(i["incident_type"] == "LATENCY_SPIKE" for i in response.get_json())


def test_analytics_summary_endpoint(client):
    client.post("/api/v1/incidents", json={"incident_type": "TOOL_FAILURE"})
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert "total_incidents" in body
    assert "mttd_seconds_avg" in body


def test_ingest_langfuse_endpoint(client):
    response = client.post("/api/v1/telemetry/langfuse", json={
        "id": "trace-api-1", "latency": 0.5, "usage": {"input": 10, "output": 20},
        "level": "DEFAULT", "tags": [],
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["ingested"] is True
    assert body["incident_created"] is False


def test_ingest_langsmith_endpoint_creates_incident(client):
    response = client.post("/api/v1/telemetry/langsmith", json={
        "id": "run-api-1", "status": "success", "latency_ms": 500,
        "tags": ["jailbreak"],
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["incident_created"] is True
    assert body["incident"]["incident_type"] == "JAILBREAK"


def test_ingest_langgraph_endpoint(client):
    response = client.post("/api/v1/telemetry/langgraph", json={
        "graph_id": "g1", "node": "n1", "status": "error", "duration_ms": 100,
    })
    assert response.status_code == 201
    assert response.get_json()["incident_created"] is True


def test_ingest_invalid_payload_returns_400(client):
    response = client.post("/api/v1/telemetry/langfuse", json={"latency": 1.0})
    assert response.status_code == 400


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"llm_incidents_total" in response.data


def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
