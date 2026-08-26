"""Tests de integración de la API Flask."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

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
    data = resp.get_json()
    assert data["status"] == "ok"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    endpoints = {c["endpoint"] for c in data["input_cards"]}
    assert "POST /api/v1/agent/plan" in endpoints


def test_plan_endpoint_success(client, monkeypatch) -> None:
    # Mockear predictor para evitar llamadas de red
    def fake_predict(items):
        return {
            "success": True,
            "source": "mock",
            "predictions": [
                {"flight_index": i, "delay_probability": 0.05, "predicted_delay_minutes": 0, "confidence": 0.9}
                for i in range(len(items))
            ],
        }

    monkeypatch.setattr("api._predictor.predict", fake_predict)

    payload = {
        "origin": "Madrid",
        "destination": "Barcelona",
        "departure_date": "2026-09-15",
        "return_date": "2026-09-17",
        "travelers": 1,
        "budget": 2000,
        "confirm_irreversible": True,
        "preferences": {"meeting_time": "15:00"},
    }
    resp = client.post("/api/v1/agent/plan", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] == "done"
    assert data["total_cost"] > 0


def test_plan_endpoint_missing_origin(client) -> None:
    payload = {"origin": "", "destination": "Barcelona", "departure_date": "2026-09-15"}
    resp = client.post("/api/v1/agent/plan", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["status"] == "awaiting_input"
    assert any("origin" in mi for mi in data["missing_info"])


def test_predict_endpoint(client, monkeypatch) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = [{"delay_probability": 0.2, "predicted_delay_minutes": 10}]
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr("requests.post", lambda *args, **kwargs: mock_response)

    payload = {
        "flights": [
            {
                "OPERA": "AA",
                "TIPOVUELO": "I",
                "MES": 4,
                "DIA": 20,
                "DIANOM": "Lunes",
                "SIGLAORI": "BOG",
                "SIGLAPOS": "SCL",
                "NROVUELO": "123",
                "CLASEVUELO": "Y",
                "TIPOPLANO": "B738",
            }
        ]
    }
    resp = client.post("/api/v1/predict", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["success"] is True
    assert len(data["predictions"]) == 1


def test_last_trace_initially_404(client) -> None:
    import api

    api._last_trace = None
    resp = client.get("/api/v1/agent/last_trace")
    assert resp.status_code == 404
