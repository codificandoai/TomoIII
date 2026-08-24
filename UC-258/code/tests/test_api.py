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
    assert resp.get_json()["data"]["service"] == "uc258-adaptive-agent"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert any("/api/v1/travel/plan" in c["endpoint"] for c in data["input_cards"])


def test_chess_move(client):
    resp = client.post("/api/v1/chess/move", json={"move": "Qd8"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["reward"] == 100.0
    assert data["done"] is True


def test_travel_plan(client):
    payload = {
        "origin": "Madrid",
        "destination": "París",
        "departure_date": "2026-07-15",
        "return_date": "2026-07-18",
        "travelers": 2,
        "budget": 2000.0,
    }
    resp = client.post("/api/v1/travel/plan", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "itinerary" in data
    assert data["itinerary"]["total_cost"] > 0


def test_agent_run_chess(client):
    resp = client.post("/api/v1/agent/run", json={"environment": "chess", "objective": {"goal": "find_checkmate"}})
    assert resp.status_code == 200
    trace = resp.get_json()["data"]
    assert trace["selected_strategy"] == "exact_search"
    assert trace["reward"] == 100.0


def test_stock_trade(client):
    resp = client.post("/api/v1/stock/trade", json={"steps": 3, "seed": 42})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "pnl" in data
    assert len(data["history"]) == 3
