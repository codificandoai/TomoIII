"""Pruebas de integración del API Flask (`app.py`)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def test_monitor_endpoint_requires_prompt_and_response(client):
    response = client.post("/api/v1/monitor", json={"prompt": "hola"})
    assert response.status_code == 400


def test_monitor_endpoint_happy_path(client):
    response = client.post("/api/v1/monitor", json={
        "prompt": "¿Cuál es la capital de Francia?",
        "response": "La capital de Francia es París.",
        "context": "Francia es un país europeo. Su capital es París.",
        "tokens_generated": 8,
        "ttft_ms": 100.0,
        "generation_latency_ms": 500.0,
    })
    assert response.status_code == 200
    body = response.get_json()
    assert "overall_risk_level" in body
    assert "request_id" in body


def test_monitor_endpoint_detects_pii_end_to_end(client):
    response = client.post("/api/v1/monitor", json={
        "prompt": "dame el correo del cliente",
        "response": "su correo es alice@example.com",
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["security"]["pii_detected"] is True
    assert body["overall_risk_level"] in ("HIGH", "CRITICAL")


def test_report_can_be_retrieved_after_monitor_call(client):
    monitor_response = client.post("/api/v1/monitor", json={
        "prompt": "hola", "response": "hola, ¿cómo estás?",
    })
    request_id = monitor_response.get_json()["request_id"]

    get_response = client.get(f"/api/v1/reports/{request_id}")
    assert get_response.status_code == 200
    assert get_response.get_json()["request_id"] == request_id


def test_report_not_found_returns_404(client):
    response = client.get("/api/v1/reports/does-not-exist")
    assert response.status_code == 404


def test_metrics_endpoint_exposes_prometheus_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"llm_" in response.data


def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
