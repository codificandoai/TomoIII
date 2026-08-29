"""API Flask para UC-274 — Web3 Multi-Agent Blockchain.

Endpoints:
- /health
- /api/v1/schema
- /api/v1/agent/register
- /api/v1/agent/<name>
- /api/v1/agents
- /api/v1/energy/offer
- /api/v1/energy/match
- /api/v1/energy/confirm
- /api/v1/energy/offers
- /api/v1/energy/trades
- /api/v1/escrow/create
- /api/v1/escrow/release
- /api/v1/reputation/<agent_name>
- /api/v1/reputation/record
- /api/v1/reputation/endorse
- /api/v1/blockchain/mine
- /api/v1/blockchain/block/<number>
- /api/v1/blockchain/status
- /api/v1/blockchain/verify
- /api/v1/marketplace/status
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from config import get_config
from marketplace import EnergyMarketplace

app = Flask(__name__)
_config = get_config()
_marketplace = EnergyMarketplace(_config)


def _ok(data: Any, status: int = 200) -> tuple:
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}), status


def _err(msg: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": msg}), status


# ============================================================
# Health & Schema
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc274-web3-multiagent-blockchain", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


# ============================================================
# Agent Management
# ============================================================

@app.route("/api/v1/agent/register", methods=["POST"])
def register_agent():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name:
        return _err("name is required")
    initial_balance = data.get("initial_balance_wei", 1_000_000)
    metadata = data.get("metadata")
    try:
        result = _marketplace.register_agent(name, initial_balance, metadata)
        return _ok(result)
    except ValueError as exc:
        return _err(str(exc))


@app.route("/api/v1/agent/<name>", methods=["GET"])
def get_agent(name: str):
    result = _marketplace.get_agent(name)
    if not result:
        return _err(f"Agent {name} not found", 404)
    return _ok(result)


@app.route("/api/v1/agents", methods=["GET"])
def list_agents():
    return _ok(_marketplace.list_agents())


# ============================================================
# Energy Trading
# ============================================================

@app.route("/api/v1/energy/offer", methods=["POST"])
def create_offer():
    data = request.get_json(silent=True) or {}
    agent_name = data.get("agent_name")
    if not agent_name:
        return _err("agent_name is required")
    result = _marketplace.create_energy_offer(
        agent_name=agent_name,
        side=data.get("side", "sell"),
        quantity_kwh=data.get("quantity_kwh", 10.0),
        price_per_kwh_wei=data.get("price_per_kwh_wei", 1000),
        energy_source=data.get("energy_source", "solar"),
    )
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


@app.route("/api/v1/energy/match", methods=["POST"])
def match_trade():
    data = request.get_json(silent=True) or {}
    buyer = data.get("buyer_name")
    offer_id = data.get("offer_id")
    quantity = data.get("quantity_kwh", 0)
    if not buyer or not offer_id:
        return _err("buyer_name and offer_id are required")
    result = _marketplace.match_trade(buyer, offer_id, quantity)
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


@app.route("/api/v1/energy/confirm", methods=["POST"])
def confirm_delivery():
    data = request.get_json(silent=True) or {}
    trade_id = data.get("trade_id")
    if not trade_id:
        return _err("trade_id is required")
    result = _marketplace.confirm_delivery(trade_id)
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


@app.route("/api/v1/energy/offers", methods=["GET"])
def list_offers():
    status = request.args.get("status", "open")
    return _ok(_marketplace.get_offers(status))


@app.route("/api/v1/energy/trades", methods=["GET"])
def list_trades():
    return _ok(_marketplace.get_trades())


# ============================================================
# Escrow
# ============================================================

@app.route("/api/v1/escrow/create", methods=["POST"])
def create_escrow():
    data = request.get_json(silent=True) or {}
    depositor = data.get("depositor_name")
    beneficiary = data.get("beneficiary_name")
    amount = data.get("amount_wei", 0)
    condition = data.get("condition", "")
    if not depositor or not beneficiary:
        return _err("depositor_name and beneficiary_name are required")
    result = _marketplace.create_escrow(depositor, beneficiary, amount, condition)
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


@app.route("/api/v1/escrow/release", methods=["POST"])
def release_escrow():
    data = request.get_json(silent=True) or {}
    caller = data.get("caller_name")
    escrow_id = data.get("escrow_id")
    if not caller or not escrow_id:
        return _err("caller_name and escrow_id are required")
    result = _marketplace.release_escrow(caller, escrow_id)
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


# ============================================================
# Reputation
# ============================================================

@app.route("/api/v1/reputation/<agent_name>", methods=["GET"])
def get_reputation(agent_name: str):
    result = _marketplace.get_reputation(agent_name)
    if "error" in result:
        return _err(result["error"], 404)
    return _ok(result)


@app.route("/api/v1/reputation/record", methods=["POST"])
def record_reputation():
    data = request.get_json(silent=True) or {}
    trader = data.get("trader_name")
    success = data.get("success", True)
    if not trader:
        return _err("trader_name is required")
    result = _marketplace.record_trade_reputation(trader, success)
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


@app.route("/api/v1/reputation/endorse", methods=["POST"])
def endorse_agent():
    data = request.get_json(silent=True) or {}
    endorser = data.get("endorser_name")
    target = data.get("target_name")
    score = data.get("score", 1.0)
    if not endorser or not target:
        return _err("endorser_name and target_name are required")
    result = _marketplace.endorse_agent(endorser, target, score)
    if "error" in result:
        return _err(result["error"])
    return _ok(result)


# ============================================================
# Blockchain
# ============================================================

@app.route("/api/v1/blockchain/mine", methods=["POST"])
def mine_block():
    data = request.get_json(silent=True) or {}
    validator_index = data.get("validator_index", 0)
    result = _marketplace.mine_block(validator_index)
    if not result:
        return _ok({"message": "No transactions to mine"})
    return _ok(result)


@app.route("/api/v1/blockchain/block/<int:number>", methods=["GET"])
def get_block(number: int):
    result = _marketplace.get_block(number)
    if not result:
        return _err(f"Block {number} not found", 404)
    return _ok(result)


@app.route("/api/v1/blockchain/status", methods=["GET"])
def blockchain_status():
    return _ok(_marketplace.get_chain_status())


@app.route("/api/v1/blockchain/verify", methods=["GET"])
def verify_chain():
    return _ok(_marketplace.verify_chain())


# ============================================================
# Marketplace
# ============================================================

@app.route("/api/v1/marketplace/status", methods=["GET"])
def marketplace_status():
    return _ok(_marketplace.get_marketplace_status())


# ============================================================
# Card Views
# ============================================================

INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/register",
        "description": "Registra agente con wallet Ed25519, DID y nombre ENS-like.",
        "parameters": [
            {"name": "name", "type": "string", "required": True, "example": "solar_farm_alpha"},
            {"name": "initial_balance_wei", "type": "int", "required": False, "default": 1000000},
            {"name": "metadata", "type": "dict", "required": False, "example": {"role": "prosumer"}},
        ],
    },
    {
        "endpoint": "POST /api/v1/energy/offer",
        "description": "Crea oferta de compra/venta de energia P2P.",
        "parameters": [
            {"name": "agent_name", "type": "string", "required": True, "example": "solar_farm_alpha"},
            {"name": "side", "type": "string", "required": False, "default": "sell", "enum": ["buy", "sell"]},
            {"name": "quantity_kwh", "type": "float", "required": False, "default": 10.0},
            {"name": "price_per_kwh_wei", "type": "int", "required": False, "default": 1000},
            {"name": "energy_source", "type": "string", "required": False, "default": "solar",
             "enum": ["solar", "wind", "hydro", "biomass", "grid"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/energy/match",
        "description": "Compra energia matcheando una oferta existente (crea escrow automatico).",
        "parameters": [
            {"name": "buyer_name", "type": "string", "required": True},
            {"name": "offer_id", "type": "string", "required": True},
            {"name": "quantity_kwh", "type": "float", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/energy/confirm",
        "description": "Oracle confirma entrega de energia y libera escrow al vendedor.",
        "parameters": [
            {"name": "trade_id", "type": "string", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/escrow/create",
        "description": "Crea escrow de pago condicional con timeout.",
        "parameters": [
            {"name": "depositor_name", "type": "string", "required": True},
            {"name": "beneficiary_name", "type": "string", "required": True},
            {"name": "amount_wei", "type": "int", "required": True},
            {"name": "condition", "type": "string", "required": False, "default": ""},
        ],
    },
    {
        "endpoint": "POST /api/v1/escrow/release",
        "description": "Libera fondos del escrow al beneficiario.",
        "parameters": [
            {"name": "caller_name", "type": "string", "required": True},
            {"name": "escrow_id", "type": "string", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/reputation/record",
        "description": "Registra trade exitoso o disputa en reputacion on-chain.",
        "parameters": [
            {"name": "trader_name", "type": "string", "required": True},
            {"name": "success", "type": "bool", "required": False, "default": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/reputation/endorse",
        "description": "Endosa reputacion de otro agente (peso proporcional a reputacion del endorser).",
        "parameters": [
            {"name": "endorser_name", "type": "string", "required": True},
            {"name": "target_name", "type": "string", "required": True},
            {"name": "score", "type": "float", "required": False, "default": 1.0},
        ],
    },
    {
        "endpoint": "POST /api/v1/blockchain/mine",
        "description": "Mina un bloque con consenso BFT (PBFT-lite).",
        "parameters": [
            {"name": "validator_index", "type": "int", "required": False, "default": 0},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/register",
        "description": "Agente registrado con wallet, DID y balance inicial.",
        "fields": [
            {"name": "name", "type": "string"},
            {"name": "address", "type": "string", "example": "0xabcd..."},
            {"name": "did", "type": "string", "example": "did:mustiamente:0xabcd..."},
            {"name": "public_key_b64", "type": "string"},
            {"name": "balance_wei", "type": "int"},
        ],
    },
    {
        "endpoint": "POST /api/v1/energy/offer",
        "description": "Oferta de energia creada.",
        "fields": [
            {"name": "offer_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["created"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/energy/match",
        "description": "Trade creado con escrow bloqueado.",
        "fields": [
            {"name": "trade_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["escrow_locked"]},
            {"name": "total_wei", "type": "int"},
        ],
    },
    {
        "endpoint": "POST /api/v1/energy/confirm",
        "description": "Entrega confirmada, escrow liberado.",
        "fields": [
            {"name": "trade_id", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "seller_received", "type": "int"},
            {"name": "fee", "type": "int"},
        ],
    },
    {
        "endpoint": "GET /api/v1/blockchain/status",
        "description": "Estado completo de la blockchain y marketplace.",
        "fields": [
            {"name": "block_height", "type": "int"},
            {"name": "total_transactions", "type": "int"},
            {"name": "validator_count", "type": "int"},
            {"name": "chain_valid", "type": "bool"},
            {"name": "contracts_deployed", "type": "int"},
            {"name": "agents_registered", "type": "int"},
            {"name": "consensus_rounds", "type": "int"},
        ],
    },
    {
        "endpoint": "GET /api/v1/marketplace/status",
        "description": "Estado del Energy Marketplace P2P.",
        "fields": [
            {"name": "total_agents", "type": "int"},
            {"name": "active_offers", "type": "int"},
            {"name": "completed_trades", "type": "int"},
            {"name": "total_energy_kwh", "type": "float"},
            {"name": "total_volume_wei", "type": "int"},
        ],
    },
    {
        "endpoint": "GET /api/v1/reputation/<agent_name>",
        "description": "Reputacion on-chain del agente.",
        "fields": [
            {"name": "address", "type": "string"},
            {"name": "reputation", "type": "float"},
            {"name": "total_trades", "type": "int"},
            {"name": "successful_trades", "type": "int"},
            {"name": "disputes", "type": "int"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC274_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
