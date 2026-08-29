import pytest

import api
from core import TwinRegistry


@pytest.fixture
def client():
    api.registry = TwinRegistry()
    api.app.config["TESTING"] = True
    return api.app.test_client()


def payload(sku="SKU-API"):
    return {"sku": sku, "current_price": 100, "unit_cost": 60,
            "competitor_price": 95, "current_demand": 1000, "inventory": 10000}


def test_dashboard_and_health(client):
    assert client.get("/").status_code == 200
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["data"]["ready"]


def test_schema_has_cards(client):
    data = client.get("/api/v1/schema").get_json()["data"]
    assert len(data["input_cards"]) >= 5
    assert len(data["output_cards"]) >= 3


def test_full_twin_pipeline(client):
    created = client.post("/api/v1/twins", json=payload())
    assert created.status_code == 201
    assert client.get("/api/v1/twins/SKU-API").status_code == 200
    ingested = client.post("/api/v1/twins/SKU-API/observations", json={
        "price": 101, "demand": 980, "competitor_price": 96, "expected_version": 1})
    assert ingested.status_code == 200
    optimized = client.post("/api/v1/twins/SKU-API/optimize", json={"scenario": "baseline"})
    data = optimized.get_json()["data"]
    assert optimized.status_code == 200
    assert len(data["signals"]) == 6
    assert len(data["audit_hash"]) == 64
    assert data["recommendation"]["recommended_price"] > 0
    projected = client.post("/api/v1/twins/SKU-API/forecast", json={"days": 5})
    assert len(projected.get_json()["data"]["forecast"]) == 5
    assert client.get("/api/v1/twins/SKU-API/cycles").status_code == 200


def test_simulation_endpoint(client):
    client.post("/api/v1/twins", json=payload("SIM"))
    response = client.post("/api/v1/twins/SIM/simulate", json={"steps": 2, "auto_execute": False})
    assert response.status_code == 200
    assert len(response.get_json()["data"]["cycles"]) == 2


def test_validation_errors(client):
    assert client.post("/api/v1/twins", json={}).status_code == 400
    assert client.get("/api/v1/twins/missing").status_code == 404
    client.post("/api/v1/twins", json=payload())
    assert client.post("/api/v1/twins/SKU-API/observations", json={}).status_code == 400
    assert client.post("/api/v1/twins/SKU-API/forecast", json={"days": 0}).status_code == 400
    assert client.post("/api/v1/twins/SKU-API/optimize", json={"objective": "bad"}).status_code == 400


def test_duplicate_and_version_conflict(client):
    client.post("/api/v1/twins", json=payload())
    assert client.post("/api/v1/twins", json=payload()).status_code == 400
    response = client.post("/api/v1/twins/SKU-API/observations", json={
        "price": 101, "demand": 900, "competitor_price": 95, "expected_version": 88})
    assert response.status_code == 400
