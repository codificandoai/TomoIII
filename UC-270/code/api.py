"""API Flask para resolución de conflictos entre agentes (UC-270).

Endpoints:
- /health
- /api/v1/schema
- /api/v1/conflict/detect (detectar y clasificar conflictos)
- /api/v1/conflict/resolve (resolver un conflicto completo)
- /api/v1/state/propose (Propose-Validate-Commit)
- /api/v1/state/view (ver estado compartido)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from flask import Flask, jsonify, request

from config import get_config
from conflict_detector import ConflictDetector
from conflict_resolver import ConflictManager
from models import AgentProfile, ResourceClaim, StateProposal
from shared_state import SharedState


app = Flask(__name__)

_config = get_config()
_manager = ConflictManager(_config)


def _ok(data: Any, status: int = 200) -> tuple:
    return (
        jsonify(
            {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
        ),
        status,
    )


def _err(message: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": message}), status


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc270-conflict-resolution", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/conflict/detect", methods=["POST"])
def detect_conflicts() -> tuple:
    """Detecta y clasifica conflictos a partir de reclamaciones de recursos."""
    data = request.get_json(silent=True) or {}
    claims_data = data.get("claims", [])
    if not claims_data:
        return _err("At least 2 claims are required", 400)
    try:
        claims = [ResourceClaim.model_validate(c) for c in claims_data]
    except Exception as exc:
        return _err(f"Invalid claims: {exc}", 400)

    detector = ConflictDetector()
    conflicts = detector.detect(claims)
    return _ok([c.model_dump(mode="json") for c in conflicts])


@app.route("/api/v1/conflict/resolve", methods=["POST"])
def resolve_conflict() -> tuple:
    """Pipeline completo: detectar + clasificar + negociar/priorizar/escalar + commit."""
    data = request.get_json(silent=True) or {}
    claims_data = data.get("claims", [])
    profiles_data = data.get("profiles", [])

    if not claims_data:
        return _err("At least 2 claims are required", 400)
    try:
        claims = [ResourceClaim.model_validate(c) for c in claims_data]
        profiles_list = [AgentProfile.model_validate(p) for p in profiles_data]
        profiles = {p.name: p for p in profiles_list}
    except Exception as exc:
        return _err(f"Invalid input: {exc}", 400)

    # Asegurar perfil por defecto para agentes sin perfil explícito
    for claim in claims:
        if claim.agent_name not in profiles:
            profiles[claim.agent_name] = AgentProfile(
                name=claim.agent_name,
                priority=claim.priority,
                flexibility=claim.flexibility,
                negotiation_skill=0.5,
            )

    manager = ConflictManager(_config)
    outcomes = manager.resolve_all(claims, profiles)
    return _ok([o.model_dump(mode="json") for o in outcomes])


@app.route("/api/v1/state/propose", methods=["POST"])
def propose_state() -> tuple:
    """Propose-Validate-Commit al estado compartido."""
    data = request.get_json(silent=True) or {}
    try:
        proposal = StateProposal.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid proposal: {exc}", 400)
    try:
        record = _manager.state.propose_validate_commit(proposal)
        return _ok(record.model_dump(mode="json"))
    except ValueError as exc:
        return _err(str(exc), 409)


@app.route("/api/v1/state/view", methods=["GET"])
def view_state() -> tuple:
    """Ver el estado compartido actual."""
    resource = request.args.get("resource")
    if resource:
        value = _manager.state.get(resource)
        return _ok({"resource": resource, "value": value})
    return _ok({"message": "Use ?resource=<id> to query specific resource"})


@app.route("/api/v1/audit", methods=["GET"])
def audit_trail() -> tuple:
    """Devuelve el trail de auditoría del estado compartido."""
    trail = _manager.state.audit_trail
    return _ok([e.model_dump(mode="json") for e in trail])


INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/conflict/detect",
        "description": "Detecta y clasifica conflictos a partir de reclamaciones de recursos.",
        "parameters": [
            {
                "name": "claims",
                "type": "list[object]",
                "required": True,
                "description": "Lista de ResourceClaim",
                "example": [
                    {"agent_name": "planner", "resource_id": "GPU_1", "need": 0.9, "priority": 8, "flexibility": 0.7, "willingness": 0.8},
                    {"agent_name": "optimizer", "resource_id": "GPU_1", "need": 0.8, "priority": 8, "flexibility": 0.4, "willingness": 0.6},
                ],
            },
        ],
    },
    {
        "endpoint": "POST /api/v1/conflict/resolve",
        "description": "Pipeline completo: detectar, clasificar, negociar/priorizar/escalar, commit atómico y auditoría.",
        "parameters": [
            {
                "name": "claims",
                "type": "list[object]",
                "required": True,
                "description": "Lista de ResourceClaim",
            },
            {
                "name": "profiles",
                "type": "list[object]",
                "required": False,
                "description": "Lista de AgentProfile (opcional; se generan por defecto)",
                "example": [
                    {"name": "planner", "priority": 8, "flexibility": 0.7, "negotiation_skill": 0.8, "reputation": 0.9},
                    {"name": "optimizer", "priority": 8, "flexibility": 0.4, "negotiation_skill": 0.6, "reputation": 0.7},
                ],
            },
        ],
    },
    {
        "endpoint": "POST /api/v1/state/propose",
        "description": "Envía un Propose-Validate-Commit atómico al estado compartido.",
        "parameters": [
            {"name": "agent_name", "type": "string", "required": True},
            {"name": "resource_id", "type": "string", "required": True},
            {"name": "proposed_value", "type": "any", "required": True},
            {"name": "priority_level", "type": "int (0-3)", "required": False, "default": 0},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/conflict/detect",
        "description": "Lista de conflictos detectados con tipo, severidad y claimants.",
        "fields": [
            {"name": "conflict_id", "type": "UUID"},
            {"name": "conflict_type", "type": "string", "enum": ["resource_contention", "incompatible_actions", "inconsistent_state", "duplicate_ownership", "policy_violation"]},
            {"name": "severity", "type": "string", "enum": ["low", "medium", "high", "critical"]},
            {"name": "resource_id", "type": "string"},
            {"name": "claimants", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/conflict/resolve",
        "description": "Resultado completo de la resolución de conflictos.",
        "fields": [
            {"name": "conflict_id", "type": "UUID"},
            {"name": "conflict_type", "type": "string"},
            {"name": "severity", "type": "string"},
            {"name": "strategy", "type": "string", "enum": ["prioritization", "negotiation", "escalation"]},
            {"name": "status", "type": "string", "enum": ["agreement", "yield", "escalate", "committed", "rejected", "deadlock"]},
            {"name": "winner", "type": "string"},
            {"name": "allocation", "type": "object"},
            {"name": "negotiation", "type": "object"},
            {"name": "commits", "type": "list[object]"},
            {"name": "audit_trail", "type": "list[object]"},
            {"name": "rationale", "type": "string"},
            {"name": "metrics", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/state/propose",
        "description": "CommitRecord tras el Propose-Validate-Commit.",
        "fields": [
            {"name": "commit_id", "type": "UUID"},
            {"name": "proposal_id", "type": "UUID"},
            {"name": "agent_name", "type": "string"},
            {"name": "resource_id", "type": "string"},
            {"name": "committed_value", "type": "any"},
            {"name": "previous_value", "type": "any"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC270_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
