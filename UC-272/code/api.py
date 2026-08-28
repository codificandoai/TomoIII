"""API Flask para UC-272 — Negociación y Compartición de Conocimiento.

Endpoints:
- /health
- /api/v1/schema (card views)
- /api/v1/negotiate/nash (Nash Bargaining + Pareto + KS)
- /api/v1/negotiate/contract-net
- /api/v1/negotiate/vickrey
- /api/v1/negotiate/argumentation
- /api/v1/blackboard/write
- /api/v1/blackboard/read
- /api/v1/gossip/broadcast
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4

from flask import Flask, jsonify, request

from config import get_config
from models import (
    AgentUtilityProfile,
    Argument,
    ContractAnnouncement,
    ContractBid,
    BlackboardEntry,
    EquilibriumCriterion,
    KnowledgeCategory,
    VickreyBid,
)
from negotiation import ArgumentationEngine, VickreyAuctionEngine
from orchestrator import NegotiationOrchestrator

app = Flask(__name__)
_config = get_config()
_orch = NegotiationOrchestrator(_config)


def _ok(data: Any, status: int = 200) -> tuple:
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}), status


def _err(msg: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": msg}), status


@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc272-negotiation-knowledge-sharing", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/negotiate/nash", methods=["POST"])
def negotiate_nash():
    """Nash Bargaining + Pareto + Kalai-Smorodinsky."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "negotiation")
    profiles_data = data.get("profiles", [])
    criterion = data.get("criterion", "nash")

    if len(profiles_data) < 2:
        return _err("At least 2 agent profiles required", 400)
    try:
        profiles = [AgentUtilityProfile.model_validate(p) for p in profiles_data]
        crit = EquilibriumCriterion(criterion)
    except Exception as exc:
        return _err(f"Invalid input: {exc}", 400)

    outcome = _orch.resolve_with_nash(topic, profiles, crit)
    return _ok(outcome.model_dump(mode="json"))


@app.route("/api/v1/negotiate/contract-net", methods=["POST"])
def negotiate_contract_net():
    """Contract Net Protocol."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "contract")
    try:
        announcement = ContractAnnouncement.model_validate(data.get("announcement", {}))
        bids = [ContractBid.model_validate(b) for b in data.get("bids", [])]
    except Exception as exc:
        return _err(f"Invalid input: {exc}", 400)

    outcome = _orch.resolve_with_contract_net(topic, announcement, bids)
    return _ok(outcome.model_dump(mode="json"))


@app.route("/api/v1/negotiate/vickrey", methods=["POST"])
def negotiate_vickrey():
    """Vickrey Auction (second-price sealed-bid)."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "auction")
    resource_id = data.get("resource_id", "resource")
    reserve_price = data.get("reserve_price", 0.0)
    try:
        bids = [VickreyBid.model_validate(b) for b in data.get("bids", [])]
    except Exception as exc:
        return _err(f"Invalid input: {exc}", 400)
    if not bids:
        return _err("At least 1 bid required", 400)

    outcome = _orch.resolve_with_vickrey(topic, resource_id, bids, reserve_price)
    return _ok(outcome.model_dump(mode="json"))


@app.route("/api/v1/negotiate/argumentation", methods=["POST"])
def negotiate_argumentation():
    """Argumentation protocol."""
    data = request.get_json(silent=True) or {}
    topic = data.get("topic", "debate")
    try:
        arguments = [Argument.model_validate(a) for a in data.get("arguments", [])]
    except Exception as exc:
        return _err(f"Invalid input: {exc}", 400)

    engine = ArgumentationEngine()
    result = engine.debate(topic, arguments)
    return _ok(result.model_dump(mode="json"))


@app.route("/api/v1/blackboard/write", methods=["POST"])
def bb_write():
    """Escribir en la pizarra compartida."""
    data = request.get_json(silent=True) or {}
    try:
        entry = BlackboardEntry.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid entry: {exc}", 400)
    written = _orch.blackboard.write(entry)
    return _ok(written.model_dump(mode="json"))


@app.route("/api/v1/blackboard/read", methods=["GET"])
def bb_read():
    """Leer de la pizarra compartida."""
    key = request.args.get("key")
    category = request.args.get("category")
    if key:
        entry = _orch.blackboard.read(key)
        if entry:
            return _ok(entry.model_dump(mode="json"))
        return _ok(None)
    if category:
        try:
            cat = KnowledgeCategory(category)
        except ValueError:
            return _err(f"Invalid category: {category}", 400)
        entries = _orch.blackboard.read_category(cat)
        return _ok([e.model_dump(mode="json") for e in entries])
    return _ok({"message": "Use ?key=<key> or ?category=<cat>"})


# ============================================================
# Card Views
# ============================================================

INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/negotiate/nash",
        "description": "Negociación multi-agente con Nash Bargaining, Pareto, Kalai-Smorodinsky o Weighted Utilitarian.",
        "parameters": [
            {"name": "topic", "type": "string", "required": False, "default": "negotiation"},
            {"name": "criterion", "type": "string", "required": False, "default": "nash",
             "enum": ["nash", "pareto", "kalai_smorodinsky", "weighted_utilitarian"]},
            {"name": "profiles", "type": "list[AgentUtilityProfile]", "required": True,
             "example": [
                 {"agent_id": "user_proxy", "option_utilities": {"AA1234": 8.5, "UX9012": 7.5}, "disagreement_point": 3.0, "weight": 1.0},
                 {"agent_id": "budget_agent", "option_utilities": {"AA1234": 4.0, "UX9012": 7.0}, "disagreement_point": 2.0, "weight": 1.0},
             ]},
        ],
    },
    {
        "endpoint": "POST /api/v1/negotiate/contract-net",
        "description": "Contract Net Protocol: announce + bid + adjudicate.",
        "parameters": [
            {"name": "topic", "type": "string", "required": False},
            {"name": "announcement", "type": "ContractAnnouncement", "required": True,
             "example": {"announcer": "planner", "task_description": "Book flight MAD-CUN", "evaluation_criteria": {"cost": 0.5, "confidence": 0.3, "duration": 0.2}}},
            {"name": "bids", "type": "list[ContractBid]", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/negotiate/vickrey",
        "description": "Subasta Vickrey (segundo precio, sellada).",
        "parameters": [
            {"name": "topic", "type": "string", "required": False},
            {"name": "resource_id", "type": "string", "required": True},
            {"name": "reserve_price", "type": "float", "required": False, "default": 0.0},
            {"name": "bids", "type": "list[VickreyBid]", "required": True,
             "example": [{"bidder": "agent_a", "bid_value": 100.0, "resource_id": "GPU_1"}]},
        ],
    },
    {
        "endpoint": "POST /api/v1/negotiate/argumentation",
        "description": "Negociación por argumentación con justificaciones y ataques.",
        "parameters": [
            {"name": "topic", "type": "string", "required": False},
            {"name": "arguments", "type": "list[Argument]", "required": True,
             "example": [{"agent_name": "budget", "claim": "Price too high", "justification": "Market average is $500", "strength": 0.8}]},
        ],
    },
    {
        "endpoint": "POST /api/v1/blackboard/write",
        "description": "Escribir conocimiento en la pizarra compartida.",
        "parameters": [
            {"name": "key", "type": "string", "required": True},
            {"name": "category", "type": "string", "required": True},
            {"name": "value", "type": "any", "required": True},
            {"name": "author", "type": "string", "required": True},
            {"name": "confidence", "type": "float (0-1)", "required": True},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/negotiate/nash",
        "description": "Resultado de equilibrio cooperativo con Pareto frontier.",
        "fields": [
            {"name": "orchestration_id", "type": "UUID"},
            {"name": "topic", "type": "string"},
            {"name": "conflict_severity", "type": "string"},
            {"name": "protocol_selected", "type": "string"},
            {"name": "negotiation.status", "type": "string"},
            {"name": "negotiation.winner", "type": "string"},
            {"name": "negotiation.utilities", "type": "dict"},
            {"name": "negotiation.nash_product", "type": "float"},
            {"name": "equilibrium.pareto_frontier", "type": "list"},
        ],
    },
    {
        "endpoint": "POST /api/v1/negotiate/contract-net",
        "description": "Resultado de adjudicación por Contract Net.",
        "fields": [
            {"name": "negotiation.winner", "type": "string"},
            {"name": "negotiation.final_terms", "type": "dict"},
            {"name": "negotiation.utilities", "type": "dict"},
        ],
    },
    {
        "endpoint": "POST /api/v1/negotiate/vickrey",
        "description": "Resultado de subasta Vickrey (segundo precio).",
        "fields": [
            {"name": "negotiation.winner", "type": "string"},
            {"name": "negotiation.final_terms.price_paid", "type": "float"},
        ],
    },
    {
        "endpoint": "POST /api/v1/negotiate/argumentation",
        "description": "Resultado de debate por argumentación.",
        "fields": [
            {"name": "winner_agent", "type": "string"},
            {"name": "winning_argument", "type": "UUID"},
            {"name": "rationale", "type": "string"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC272_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
