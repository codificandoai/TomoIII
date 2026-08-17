"""Pruebas de integración del API Flask (`app.py`) de UC-179."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import app as app_module
from pipeline_service import ContinuousLearningPipeline


@pytest.fixture()
def client(tmp_path):
    app_module.pipeline = ContinuousLearningPipeline(
        db_path=tmp_path / "kb.db",
        model_versions_dir=tmp_path / "models" / "versions",
        production_dir=tmp_path / "models" / "production",
    )
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


def _ingest_payload(n_per_class: int = 15):
    support = [{"query": f"pregunta de soporte tecnico numero {i}",
                "response": "respuesta_soporte", "rating": 5} for i in range(n_per_class)]
    billing = [{"query": f"pregunta de facturacion mensual numero {i}",
                "response": "respuesta_facturacion", "rating": 5} for i in range(n_per_class)]
    return {"sources": [{"type": "user_feedback", "data": support + billing}]}


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_ingest_requires_sources(client):
    response = client.post("/api/v1/data/ingest", json={})
    assert response.status_code == 400


def test_ingest_invalid_source_type(client):
    response = client.post("/api/v1/data/ingest", json={"sources": [{"type": "bogus", "data": []}]})
    assert response.status_code == 400


def test_ingest_success(client):
    response = client.post("/api/v1/data/ingest", json=_ingest_payload())
    assert response.status_code == 201
    body = response.get_json()
    assert body["stored"] > 0


def test_status_endpoint(client):
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert "next_trigger" in response.get_json()


def test_training_run_skipped_without_data(client):
    response = client.post("/api/v1/training/run", json={"training_type": "full_retraining"})
    assert response.status_code == 201
    assert response.get_json()["status"] == "skipped"


def test_training_run_invalid_type(client):
    response = client.post("/api/v1/training/run", json={"training_type": "bogus"})
    assert response.status_code == 400


def _train_and_get_version(client):
    client.post("/api/v1/data/ingest", json=_ingest_payload())
    client.post("/api/v1/data/validate", json={})
    training_response = client.post("/api/v1/training/run", json={"training_type": "full_retraining"})
    return training_response.get_json()


def test_validate_data_endpoint_approves_pending_samples(client):
    client.post("/api/v1/data/ingest", json=_ingest_payload())
    response = client.post("/api/v1/data/validate", json={})
    assert response.status_code == 200
    body = response.get_json()
    assert body["validated_count"] > 0


def test_full_lifecycle_via_api(client):
    training = _train_and_get_version(client)
    assert training["status"] == "trained"
    model_version = training["model_version"]

    validate_response = client.post("/api/v1/models/validate", json={"model_version": model_version})
    assert validate_response.status_code == 200
    assert "should_deploy" in validate_response.get_json()

    deploy_response = client.post("/api/v1/models/deploy", json={"model_version": model_version})
    assert deploy_response.status_code == 201
    assert deploy_response.get_json()["status"] == "deployed"

    predict_response = client.post("/api/v1/predict", json={"text": "necesito facturar un pedido"})
    assert predict_response.status_code == 200
    assert "prediction" in predict_response.get_json()

    history_response = client.get("/api/v1/models/history")
    assert history_response.status_code == 200
    assert len(history_response.get_json()) >= 1


def test_validate_unknown_model_returns_404(client):
    response = client.post("/api/v1/models/validate", json={"model_version": "does-not-exist"})
    assert response.status_code == 404


def test_deploy_requires_model_version(client):
    response = client.post("/api/v1/models/deploy", json={})
    assert response.status_code == 400


def test_deploy_unknown_model_returns_404(client):
    response = client.post("/api/v1/models/deploy", json={"model_version": "does-not-exist", "force": True})
    assert response.status_code == 404


def test_predict_requires_text(client):
    response = client.post("/api/v1/predict", json={})
    assert response.status_code == 400


def test_predict_without_deployment_returns_409(client):
    response = client.post("/api/v1/predict", json={"text": "hola"})
    assert response.status_code == 409


def test_rollback_without_backup_returns_404(client):
    response = client.post("/api/v1/models/rollback", json={})
    assert response.status_code == 404


def test_rollback_after_two_deployments(client):
    training_1 = _train_and_get_version(client)
    client.post("/api/v1/models/deploy", json={"model_version": training_1["model_version"]})

    training_2 = _train_and_get_version(client)
    client.post("/api/v1/models/deploy", json={"model_version": training_2["model_version"], "force": True})

    rollback_response = client.post("/api/v1/models/rollback", json={})
    assert rollback_response.status_code == 200
    assert rollback_response.get_json()["metadata"]["version"] == training_1["model_version"]


def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
