"""Tests de integración de la API Flask."""
import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_schema_returns_cards(client):
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    assert any("/api/v1/query" in c["endpoint"] for c in data["input_cards"])


def test_ingest_text(client):
    resp = client.post(
        "/api/v1/ingest",
        json={
            "text": "El proceso de onboarding dura cinco días laborables.",
            "title": "Onboarding",
            "metadata": {"tenant_id": "acme"},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["num_chunks"] > 0
    assert data["doc_id"]


def test_query(client):
    client.post(
        "/api/v1/ingest",
        json={
            "text": "La política de gastos exige ticket y aprobación para montos superiores a 100 euros.",
            "title": "Gastos",
            "metadata": {"tenant_id": "acme"},
        },
    )
    resp = client.post(
        "/api/v1/query",
        json={"question": "¿Qué se exige para gastos mayores a 100 euros?", "tenant_id": "acme"},
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["answer"]
    assert data["trace_id"]
    assert data["retrieved_chunks"]


def test_evaluate(client):
    client.post(
        "/api/v1/ingest",
        json={
            "text": "París es la capital de Francia.",
            "title": "Capitales",
        },
    )
    resp = client.post(
        "/api/v1/evaluate",
        json={
            "samples": [
                {
                    "query": "¿Capital de Francia?",
                    "ground_truth": "París",
                    "reference_contexts": ["París es la capital de Francia."],
                }
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "average_metrics" in data


def test_audit(client):
    resp = client.get("/api/v1/audit")
    assert resp.status_code == 200
    assert "logs" in resp.get_json()["data"]
