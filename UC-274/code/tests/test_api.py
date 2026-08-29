"""Tests de integración de la API Flask."""
from __future__ import annotations

import json

import pytest

from api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["service"] == "uc274-web3-multiagent-blockchain"


def test_schema(client):
    resp = client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "input_cards" in data
    assert "output_cards" in data
    assert len(data["input_cards"]) >= 9
    assert len(data["output_cards"]) >= 6


def test_register_agent(client):
    resp = client.post("/api/v1/agent/register",
                       data=json.dumps({"name": "test_solar", "initial_balance_wei": 500000}),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"] == "test_solar"
    assert data["address"].startswith("0x")
    assert data["did"].startswith("did:mustiamente:")


def test_register_duplicate(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "dup_agent"}),
                content_type="application/json")
    resp = client.post("/api/v1/agent/register",
                       data=json.dumps({"name": "dup_agent"}),
                       content_type="application/json")
    assert resp.status_code == 400


def test_get_agent(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "get_me", "initial_balance_wei": 100}),
                content_type="application/json")
    resp = client.get("/api/v1/agent/get_me")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["balance_wei"] == 100


def test_get_agent_not_found(client):
    resp = client.get("/api/v1/agent/nonexistent")
    assert resp.status_code == 404


def test_list_agents(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "list_a1"}),
                content_type="application/json")
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    agents = resp.get_json()["data"]
    assert isinstance(agents, list)


def test_create_offer(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "offer_seller", "initial_balance_wei": 1000000}),
                content_type="application/json")
    resp = client.post("/api/v1/energy/offer",
                       data=json.dumps({"agent_name": "offer_seller", "side": "sell",
                                       "quantity_kwh": 25.0, "price_per_kwh_wei": 800}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "created"


def test_match_trade(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "match_seller", "initial_balance_wei": 1000000}),
                content_type="application/json")
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "match_buyer", "initial_balance_wei": 1000000}),
                content_type="application/json")

    offer_resp = client.post("/api/v1/energy/offer",
                             data=json.dumps({"agent_name": "match_seller", "side": "sell",
                                             "quantity_kwh": 50.0, "price_per_kwh_wei": 1000}),
                             content_type="application/json")
    offer_id = offer_resp.get_json()["data"]["offer_id"]

    resp = client.post("/api/v1/energy/match",
                       data=json.dumps({"buyer_name": "match_buyer", "offer_id": offer_id,
                                       "quantity_kwh": 10.0}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "escrow_locked"


def test_list_offers(client):
    resp = client.get("/api/v1/energy/offers")
    assert resp.status_code == 200


def test_list_trades(client):
    resp = client.get("/api/v1/energy/trades")
    assert resp.status_code == 200


def test_escrow_create(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "esc_dep", "initial_balance_wei": 1000000}),
                content_type="application/json")
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "esc_ben", "initial_balance_wei": 100}),
                content_type="application/json")

    resp = client.post("/api/v1/escrow/create",
                       data=json.dumps({"depositor_name": "esc_dep", "beneficiary_name": "esc_ben",
                                       "amount_wei": 50000, "condition": "deliver goods"}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "locked"


def test_reputation(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "rep_agent", "initial_balance_wei": 100}),
                content_type="application/json")

    resp = client.post("/api/v1/reputation/record",
                       data=json.dumps({"trader_name": "rep_agent", "success": True}),
                       content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["reputation"] > 0.5


def test_get_reputation(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "rep_get_agent"}),
                content_type="application/json")
    resp = client.get("/api/v1/reputation/rep_get_agent")
    assert resp.status_code == 200


def test_endorse(client):
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "endorse_from"}),
                content_type="application/json")
    client.post("/api/v1/agent/register",
                data=json.dumps({"name": "endorse_to"}),
                content_type="application/json")

    resp = client.post("/api/v1/reputation/endorse",
                       data=json.dumps({"endorser_name": "endorse_from",
                                       "target_name": "endorse_to", "score": 0.9}),
                       content_type="application/json")
    assert resp.status_code == 200


def test_blockchain_status(client):
    resp = client.get("/api/v1/blockchain/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "block_height" in data
    assert "validator_count" in data


def test_blockchain_verify(client):
    resp = client.get("/api/v1/blockchain/verify")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["valid"] is True


def test_get_genesis_block(client):
    resp = client.get("/api/v1/blockchain/block/0")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["block_number"] == 0


def test_get_block_not_found(client):
    resp = client.get("/api/v1/blockchain/block/99999")
    assert resp.status_code == 404


def test_mine_block(client):
    resp = client.post("/api/v1/blockchain/mine",
                       data=json.dumps({}),
                       content_type="application/json")
    assert resp.status_code == 200


def test_marketplace_status(client):
    resp = client.get("/api/v1/marketplace/status")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert "total_agents" in data
    assert "active_offers" in data
