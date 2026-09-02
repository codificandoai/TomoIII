"""Tests de integración de la API Flask."""
from __future__ import annotations

import json

import pytest

from api import app
from market_data import SyntheticMarketDataGenerator


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["service"] == "uc293-bdi-juice-trading"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    data = resp.get_json()["data"]
    assert "input_cards" in data and "output_cards" in data
    endpoints = {card["endpoint"] for card in data["input_cards"]}
    assert "POST /api/v1/trading/plan" in endpoints


def test_market_perceive(client):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=50)
    payload = {
        "symbol": "AAPL",
        "ticks": [t.to_dict() for t in ticks],
    }
    resp = client.post(
        "/api/v1/market/perceive",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]["AAPL"]
    assert "features" in data
    assert "rsi" in data["features"]


def test_market_analyze(client):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=50)
    payload = {
        "symbol": "AAPL",
        "ticks": [t.to_dict() for t in ticks],
        "news": [{"text": "AAPL strong earnings beat", "source": "bloomberg"}],
    }
    resp = client.post(
        "/api/v1/market/analyze",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "technical" in data and "sentiment" in data


def test_trading_plan_endpoint(client):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=100)
    payload = {
        "symbols": ["AAPL"],
        "ticks": [t.to_dict() for t in ticks],
        "portfolio": {"cash": 100_000.0, "positions": {}},
    }
    resp = client.post(
        "/api/v1/trading/plan",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] in ("done", "awaiting_confirmation", "blocked")


def test_mcp_tools(client):
    resp = client.get("/api/v1/mcp/tools")
    assert resp.status_code == 200
    tools = resp.get_json()["data"]["tools"]
    names = {t["name"] for t in tools}
    assert "get_market_snapshot" in names
    assert "submit_order" in names


def test_world_model_endpoint(client):
    resp = client.get("/api/v1/model/world_model")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "estimates" in data


def test_predict_next_tick_endpoint(client):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    payload = {
        "symbol": "AAPL",
        "train": True,
        "ticks": [t.to_dict() for t in ticks],
    }
    resp = client.post(
        "/api/v1/model/predict_next_tick",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "predicted_next_price" in data
    assert data["predicted_next_price"] > 0


def test_bdi_confront_endpoint(client):
    payload = {
        "beliefs": {
            "symbol": "AAPL",
            "current_price": 150.0,
            "predicted_next_price": 155.0,
            "rsi": 50.0,
            "trend_direction": 1,
            "news_sentiment": 0.2,
            "volatility": 0.01,
            "world_model_uncertainty": 0.1,
            "portfolio_cash": 100_000.0,
            "portfolio_position": 0.0,
        },
        "desires": {
            "min_signal_confidence": 0.5,
            "max_position_pct": 0.2,
            "max_uncertainty": 0.5,
        },
        "intention": {
            "planned_action": "BUY",
            "actions": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "quantity": 10,
                    "price": 150.0,
                    "confidence": 0.8,
                    "stop_loss": 145.0,
                    "take_profit": 160.0,
                }
            ],
        },
    }
    resp = client.post(
        "/api/v1/bdi/confront",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "verdict" in data
    assert "bdi_state" in data
    assert data["verdict"]["approved"] is True


def test_bdi_state_endpoint(client):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    payload = {
        "symbols": ["AAPL"],
        "ticks": [t.to_dict() for t in ticks],
        "portfolio": {"cash": 100_000.0, "positions": {}},
    }
    resp = client.post(
        "/api/v1/bdi/state",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert "beliefs" in data
    assert "desires" in data


def test_plan_with_bdi_endpoint(client):
    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=100)
    payload = {
        "symbols": ["AAPL"],
        "ticks": [t.to_dict() for t in ticks],
        "portfolio": {"cash": 100_000.0, "positions": {}},
        "mode": "paper",
        "approved": True,
    }
    resp = client.post(
        "/api/v1/trading/plan_with_bdi",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["status"] in ("done", "awaiting_confirmation", "blocked")
