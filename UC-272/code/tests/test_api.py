"""Tests de integración de la API Flask."""
from __future__ import annotations

import json
from uuid import uuid4

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
    assert resp.get_json()["data"]["service"] == "uc272-negotiation-knowledge-sharing"


def test_schema(client) -> None:
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data


def test_negotiate_nash(client) -> None:
    payload = {
        "topic": "flight_MAD_CUN",
        "criterion": "nash",
        "profiles": [
            {"agent_id": "user", "option_utilities": {"A": 8.5, "B": 5.0, "C": 7.5}, "disagreement_point": 3.0},
            {"agent_id": "budget", "option_utilities": {"A": 4.0, "B": 9.0, "C": 7.0}, "disagreement_point": 2.0},
            {"agent_id": "sustain", "option_utilities": {"A": 6.0, "B": 4.0, "C": 9.0}, "disagreement_point": 2.0},
        ],
    }
    resp = client.post("/api/v1/negotiate/nash", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["negotiation"]["winner"] == "C"
    assert data["equilibrium"]["pareto_frontier"] is not None


def test_negotiate_contract_net(client) -> None:
    cid = str(uuid4())
    payload = {
        "topic": "book_flight",
        "announcement": {
            "contract_id": cid, "announcer": "planner", "task_description": "Book MAD-CUN",
            "evaluation_criteria": {"cost": 0.5, "confidence": 0.3, "duration": 0.2},
        },
        "bids": [
            {"contract_id": cid, "bidder": "aa", "cost": 500.0, "estimated_duration_min": 30, "confidence": 0.9},
            {"contract_id": cid, "bidder": "ib", "cost": 800.0, "estimated_duration_min": 60, "confidence": 0.7},
        ],
    }
    resp = client.post("/api/v1/negotiate/contract-net", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["negotiation"]["winner"] == "aa"


def test_negotiate_vickrey(client) -> None:
    aid = str(uuid4())
    payload = {
        "topic": "gpu_auction",
        "resource_id": "GPU_1",
        "reserve_price": 0.0,
        "bids": [
            {"auction_id": aid, "bidder": "a", "bid_value": 100.0, "resource_id": "GPU_1"},
            {"auction_id": aid, "bidder": "b", "bid_value": 80.0, "resource_id": "GPU_1"},
        ],
    }
    resp = client.post("/api/v1/negotiate/vickrey", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["negotiation"]["winner"] == "a"
    assert data["negotiation"]["final_terms"]["price_paid"] == 80.0


def test_negotiate_argumentation(client) -> None:
    payload = {
        "topic": "price_debate",
        "arguments": [
            {"agent_name": "budget", "claim": "Too expensive", "justification": "Market avg $500", "strength": 0.8},
            {"agent_name": "user", "claim": "Quality", "justification": "Premium", "strength": 0.6},
        ],
    }
    resp = client.post("/api/v1/negotiate/argumentation", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["winner_agent"] == "budget"


def test_blackboard_write_and_read(client) -> None:
    entry = {"key": "test_key", "category": "flight_facts", "value": {"info": "test"}, "author": "tester", "confidence": 0.9}
    resp = client.post("/api/v1/blackboard/write", data=json.dumps(entry), content_type="application/json")
    assert resp.status_code == 200

    resp = client.get("/api/v1/blackboard/read?key=test_key")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["value"]["info"] == "test"


def test_blackboard_read_category(client) -> None:
    resp = client.get("/api/v1/blackboard/read?category=negotiation_state")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert isinstance(data, list)
