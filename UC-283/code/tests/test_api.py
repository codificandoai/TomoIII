import pytest

import api
from memory import LessonMemory


@pytest.fixture
def client():
    api.memory = LessonMemory()
    api.idempotency_cache = {}
    api.app.config["TESTING"] = True
    return api.app.test_client()


def payload(): return {"product_id": "API-SKU", "current_price": 249.99, "cost": 150,
                       "competitor_price": 245, "historical_volatility": 5.5}


def test_health_schema_and_tools(client):
    assert client.get("/health").status_code == 200
    schema = client.get("/api/v1/schema").get_json()["data"]
    assert len(schema["input_cards"]) == len(schema["output_cards"]) == 1
    assert len(client.get("/api/v1/tools").get_json()["data"]) == 3


def test_full_correction_api(client):
    response = client.post("/api/v1/correct", json=payload())
    data = response.get_json()["data"]
    assert response.status_code == 200
    assert data["status"] == "approved"
    assert len(data["attempts"]) >= 2
    assert len(data["audit_hash"]) == 64
    memory = client.get("/api/v1/memory/API-SKU").get_json()["data"]
    assert memory["stats"]["total"] > 0


def test_approval_gate_api(client):
    data = payload(); data["apply"] = True
    assert client.post("/api/v1/correct", json=data).get_json()["data"]["status"] == "approval_required"
    data["approved"] = True
    assert client.post("/api/v1/correct", json=data).get_json()["data"]["status"] == "applied"


def test_idempotency(client):
    data = payload(); data["idempotency_key"] = "same"
    first = client.post("/api/v1/correct", json=data).get_json()["data"]
    second = client.post("/api/v1/correct", json=data).get_json()["data"]
    assert first["run_id"] == second["run_id"]


def test_validation(client):
    assert client.post("/api/v1/correct", json={}).status_code == 400
    bad = payload(); bad["current_price"] = -1
    assert client.post("/api/v1/correct", json=bad).status_code == 400
