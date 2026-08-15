"""Pruebas de integración del API Flask (`app.py`) de UC-127."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("UC127_INTEGRATIONS_DRY_RUN", "true")

import pytest

from app import app as flask_app


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert "unsafe_generation" in body["playbooks_loaded"]


def test_create_incident_requires_signal(client):
    response = client.post("/api/v1/incidents", json={"model": "m"})
    assert response.status_code == 400


def test_create_incident_from_metrics_low_severity_auto_remediates(client):
    response = client.post("/api/v1/incidents", json={
        "model": "llama-3-8b",
        "hallucination_rate": 0.05,
        "quality_score": 0.55,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] in ("REMEDIATED", "PENDING_APPROVAL")
    assert body["incident_id"]


def test_create_incident_with_explicit_type_pending_approval(client):
    response = client.post("/api/v1/incidents", json={
        "incident_type": "DATA_LEAK",
        "severity": "CRITICAL",
        "model": "llama-3-8b",
        "summary": "PII leaked",
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "PENDING_APPROVAL"


def test_get_incident_not_found(client):
    response = client.get("/api/v1/incidents/does-not-exist")
    assert response.status_code == 404


def test_full_incident_lifecycle_approve_and_close(client):
    create_resp = client.post("/api/v1/incidents", json={
        "incident_type": "UNSAFE_GENERATION",
        "severity": "CRITICAL",
        "model": "llama-3-8b",
    })
    incident_id = create_resp.get_json()["incident_id"]
    assert create_resp.get_json()["status"] == "PENDING_APPROVAL"

    approve_resp = client.post(f"/api/v1/incidents/{incident_id}/approve", json={
        "approved": True, "approver": "alice",
    })
    assert approve_resp.status_code == 200
    assert approve_resp.get_json()["status"] == "REMEDIATED"

    close_resp = client.post(f"/api/v1/incidents/{incident_id}/close", json={
        "root_cause": "prompt_regression", "playbook_effective": True,
    })
    assert close_resp.status_code == 200
    assert close_resp.get_json()["status"] == "CLOSED"


def test_close_incident_invalid_root_cause_returns_400(client):
    create_resp = client.post("/api/v1/incidents", json={
        "incident_type": "TOOL_FAILURE", "severity": "LOW", "model": "m",
    })
    incident_id = create_resp.get_json()["incident_id"]
    response = client.post(f"/api/v1/incidents/{incident_id}/close", json={"root_cause": "not_a_real_cause"})
    assert response.status_code == 400


def test_rollback_incident(client):
    create_resp = client.post("/api/v1/incidents", json={
        "incident_type": "COST_ANOMALY", "severity": "LOW", "model": "m",
    })
    incident_id = create_resp.get_json()["incident_id"]
    response = client.post(f"/api/v1/incidents/{incident_id}/rollback", json={"reason": "test"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "ROLLED_BACK"


def test_alertmanager_webhook_recognized_alert(client):
    payload = {
        "alerts": [{
            "labels": {"alertname": "PIILeakDetected", "severity": "critical", "model": "llama-3-8b"},
            "annotations": {"summary": "PII detectada"},
        }]
    }
    response = client.post("/api/v1/alertmanager/webhook", json=payload)
    assert response.status_code == 201
    assert response.get_json()["alert"]["incident_type"] == "DATA_LEAK"


def test_alertmanager_webhook_unrecognized_alert_ignored(client):
    payload = {"alerts": [{"labels": {"alertname": "SomethingElse"}, "annotations": {}}]}
    response = client.post("/api/v1/alertmanager/webhook", json=payload)
    assert response.status_code == 202


def test_list_playbooks(client):
    response = client.get("/api/v1/playbooks")
    assert response.status_code == 200
    names = [p["name"] for p in response.get_json()]
    assert "data_leak" in names
    assert "hallucination" in names


def test_list_sops(client):
    response = client.get("/api/v1/sops")
    assert response.status_code == 200
    assert len(response.get_json()) > 0


def test_chaos_scenarios_listed(client):
    response = client.get("/api/v1/chaos/scenarios")
    assert response.status_code == 200
    assert "pii_leak" in response.get_json()


def test_run_single_chaos_scenario(client):
    response = client.post("/api/v1/chaos/run", json={"scenario": "tool_outage"})
    assert response.status_code == 200
    results = response.get_json()
    assert len(results) == 1
    assert results[0]["scenario"] == "tool_outage"


def test_run_unknown_chaos_scenario_returns_400(client):
    response = client.post("/api/v1/chaos/run", json={"scenario": "does_not_exist"})
    assert response.status_code == 400


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"llm_incident_total" in response.data


def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
