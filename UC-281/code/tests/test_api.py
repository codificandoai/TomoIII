import pytest

import api
from store import RunStore


@pytest.fixture
def client():
    api.pipelines = {}
    api.store = RunStore()
    api.app.config["TESTING"] = True
    return api.app.test_client()


def payload():
    return {"sku": "API-SKU", "current_price": 100, "unit_cost": 60,
            "competitor_price": 95, "demand": 1000, "inventory": 5000,
            "mode": "simulation", "headlines": ["Demand growth"]}


def test_health_and_cards(client):
    assert client.get("/health").status_code == 200
    cards = client.get("/api/v1/schema").get_json()["data"]
    assert len(cards["input_cards"]) == 2
    assert len(cards["output_cards"]) == 2


def test_full_pipeline_api(client):
    assert client.post("/api/v1/pipelines", json=payload()).status_code == 201
    assert client.get("/api/v1/pipelines/API-SKU").status_code == 200
    response = client.post("/api/v1/pipelines/API-SKU/run", json={"execute": False, "idempotency_key": "api-run"})
    data = response.get_json()["data"]
    assert response.status_code == 200
    assert len(data["responses"]) == 5
    assert len(data["audit_hash"]) == 64
    run_id = data["run_id"]
    assert client.get(f"/api/v1/pipelines/API-SKU/events?run_id={run_id}").status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 200


def test_list_endpoints(client):
    client.post("/api/v1/pipelines", json=payload())
    client.post("/api/v1/pipelines/API-SKU/run")
    assert len(client.get("/api/v1/pipelines").get_json()["data"]) == 1
    assert len(client.get("/api/v1/runs").get_json()["data"]) == 1


def test_validation(client):
    assert client.post("/api/v1/pipelines", json={}).status_code == 400
    client.post("/api/v1/pipelines", json=payload())
    assert client.post("/api/v1/pipelines", json=payload()).status_code == 400
    assert client.get("/api/v1/pipelines/missing").status_code == 404
