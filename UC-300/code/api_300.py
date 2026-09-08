"""
UC-300 — API REST Flask para Secure Tool Gateway.

Expone el gateway como servicio REST.
Puerto por defecto: 5300
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

from constitutional_models import AgentProposal
from intent_models import IntentRequest
from models_300 import GatewayConfig, ToolRequest
from secure_tool_gateway import SecureToolGateway

app = Flask(__name__)
_gateway: SecureToolGateway = SecureToolGateway()

# ---------------------------------------------------------------------------
# INPUT Cards
# ---------------------------------------------------------------------------
INPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/authorize": {
        "endpoint": "POST /api/v1/authorize",
        "description": "Autoriza una solicitud de ejecución de herramienta y emite un capability token (one-use, TTL, firmado).",
        "parameters": [
            {"name": "trace_id", "type": "string", "required": False, "example": "trace_001"},
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_pricing_eu"},
            {"name": "action", "type": "string", "required": True, "enum": ["update_price", "delete_product", "send_payment", "read_file"], "example": "update_price"},
            {"name": "params", "type": "object", "required": True, "example": {"product_id": "SKU-001", "new_price": 120.5, "reason": "Ajuste mensual"}},
            {"name": "environment", "type": "string", "required": False, "default": "default", "example": "default"},
            {"name": "dossier_id", "type": "string", "required": False, "example": "dossier_123"},
            {"name": "dossier_hash", "type": "string", "required": False, "example": "abc123..."},
            {"name": "dossier_status", "type": "string", "required": False, "enum": ["approved", "rejected", "pending", "auto_executed"], "default": ""},
            {"name": "reviewer_id", "type": "string", "required": False, "example": "reviewer_001"},
            {"name": "approval_action_hash", "type": "string", "required": False, "example": "hash..."},
        ],
    },
    "POST /api/v1/execute": {
        "endpoint": "POST /api/v1/execute",
        "description": "Ejecuta una acción previamente autorizada. Requiere capability_token. Realiza TOCTOU revalidation y sandbox simulado.",
        "parameters": [
            {"name": "trace_id", "type": "string", "required": False, "example": "trace_001"},
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_pricing_eu"},
            {"name": "action", "type": "string", "required": True, "example": "update_price"},
            {"name": "params", "type": "object", "required": True, "example": {"product_id": "SKU-001", "new_price": 120.5, "reason": "Ajuste mensual"}},
            {"name": "environment", "type": "string", "required": False, "default": "default"},
            {"name": "dossier_id", "type": "string", "required": False},
            {"name": "dossier_hash", "type": "string", "required": False},
            {"name": "capability_token", "type": "string", "required": True, "example": "eyJhY3..."},
        ],
    },
    "POST /api/v1/human-approval": {
        "endpoint": "POST /api/v1/human-approval",
        "description": "Registra aprobación humana explícita ligada al hash exacto de la acción y emite capability token.",
        "parameters": [
            {"name": "trace_id", "type": "string", "required": False},
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "action", "type": "string", "required": True},
            {"name": "params", "type": "object", "required": True},
            {"name": "environment", "type": "string", "required": False, "default": "default"},
            {"name": "dossier_id", "type": "string", "required": True},
            {"name": "dossier_hash", "type": "string", "required": True},
            {"name": "reviewer_id", "type": "string", "required": True},
            {"name": "approval_action_hash", "type": "string", "required": True},
        ],
    },
    "POST /api/v1/reset": {
        "endpoint": "POST /api/v1/reset",
        "description": "Reinicia el gateway con configuración opcional.",
        "parameters": [
            {"name": "config", "type": "object", "required": False, "description": "Campos de GatewayConfig"},
        ],
    },
    "POST /api/v1/kill-switch": {
        "endpoint": "POST /api/v1/kill-switch",
        "description": "Activa o desactiva el kill switch externo del gateway.",
        "parameters": [
            {"name": "enabled", "type": "boolean", "required": True},
        ],
    },
    "GET /api/v1/status": {
        "endpoint": "GET /api/v1/status",
        "description": "Estado del gateway, políticas, cuotas y auditoría.",
        "parameters": [],
    },
    "GET /api/v1/audit-trail": {
        "endpoint": "GET /api/v1/audit-trail",
        "description": "Entradas de auditoría, opcionalmente filtradas por trace_id.",
        "parameters": [
            {"name": "trace_id", "type": "string", "required": False, "in": "query"},
        ],
    },
    "GET /api/v1/metrics": {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus del gateway.",
        "parameters": [],
    },
    "GET /api/v1/schema": {
        "endpoint": "GET /api/v1/schema",
        "description": "INPUT/OUTPUT cards de la API.",
        "parameters": [],
    },
    "POST /api/v1/prefilter-intent": {
        "endpoint": "POST /api/v1/prefilter-intent",
        "description": "Pre-Intent Gate: normaliza, valida, clasifica y decide ALLOW/BLOCK/ESCALATE antes de UC-315.",
        "parameters": [
            {"name": "raw_text", "type": "string", "required": True, "example": "Update price of SKU-001 to 120.50"},
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_pricing_eu"},
            {"name": "tenant_id", "type": "string", "required": True, "example": "eu"},
            {"name": "locale", "type": "string", "required": False, "default": "en", "example": "en"},
            {"name": "domain", "type": "string", "required": False, "default": "", "example": "internal.example.com"},
            {"name": "request_id", "type": "string", "required": False, "example": "req_001"},
            {"name": "timestamp", "type": "number", "required": False, "default": "now", "example": 1700000000.0},
            {"name": "approval_intent_hash", "type": "string", "required": False},
            {"name": "approval_reviewer_id", "type": "string", "required": False},
            {"name": "approval_dossier_id", "type": "string", "required": False},
            {"name": "approval_dossier_hash", "type": "string", "required": False},
            {"name": "approval_expires_at", "type": "number", "required": False},
        ],
    },
    "POST /api/v1/prefilter-intent/approve": {
        "endpoint": "POST /api/v1/prefilter-intent/approve",
        "description": "Registra aprobación humana explícita ligada al hash exacto de intención para resolver ESCALATE sin red.",
        "parameters": [
            {"name": "intent_hash", "type": "string", "required": True},
            {"name": "reviewer_id", "type": "string", "required": True},
            {"name": "dossier_id", "type": "string", "required": False},
            {"name": "dossier_hash", "type": "string", "required": False},
            {"name": "ttl_seconds", "type": "number", "required": False, "default": 3600},
        ],
    },
    "POST /api/v1/intercept-proposal": {
        "endpoint": "POST /api/v1/intercept-proposal",
        "description": "Constitutional Interceptor: evalúa la propuesta de UC-315 contra principios constitucionales deterministas antes de UC-290.",
        "parameters": [
            {"name": "stated_goal", "type": "string", "required": True, "example": "Show price of SKU-001"},
            {"name": "proposed_capability", "type": "string", "required": True, "example": "read_price"},
            {"name": "proposed_action", "type": "string", "required": True, "example": "read_price"},
            {"name": "params", "type": "object", "required": False, "default": {}, "example": {"product_id": "SKU-001"}},
            {"name": "affected_resources", "type": "array", "required": False, "default": [], "example": ["SKU-001"]},
            {"name": "estimated_calls", "type": "integer", "required": False, "default": 1},
            {"name": "estimated_duration_seconds", "type": "number", "required": False, "default": 0},
            {"name": "estimated_cost", "type": "number", "required": False, "default": 0},
            {"name": "reversible", "type": "boolean", "required": False, "default": True},
            {"name": "reversibility_plan", "type": "string", "required": False, "default": ""},
            {"name": "requested_permissions_delta", "type": "array", "required": False, "default": []},
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_pricing_eu"},
            {"name": "tenant_id", "type": "string", "required": True, "example": "eu"},
            {"name": "domain", "type": "string", "required": False, "default": ""},
            {"name": "locale", "type": "string", "required": False, "default": "en"},
            {"name": "trace_id", "type": "string", "required": False},
            {"name": "proposal_id", "type": "string", "required": False},
            {"name": "timestamp", "type": "number", "required": False, "default": "now"},
            {"name": "approval_proposal_hash", "type": "string", "required": False},
            {"name": "approval_reviewer_id", "type": "string", "required": False},
            {"name": "approval_dossier_id", "type": "string", "required": False},
            {"name": "approval_dossier_hash", "type": "string", "required": False},
            {"name": "approval_expires_at", "type": "number", "required": False},
        ],
    },
    "POST /api/v1/intercept-proposal/approve": {
        "endpoint": "POST /api/v1/intercept-proposal/approve",
        "description": "Registra aprobación humana ligada al hash exacto de la propuesta para resolver ESCALATE sin invocar UC-315.",
        "parameters": [
            {"name": "proposal_hash", "type": "string", "required": True},
            {"name": "reviewer_id", "type": "string", "required": True},
            {"name": "dossier_id", "type": "string", "required": False},
            {"name": "dossier_hash", "type": "string", "required": False},
            {"name": "ttl_seconds", "type": "number", "required": False, "default": 3600},
        ],
    },
}

# ---------------------------------------------------------------------------
# OUTPUT Cards
# ---------------------------------------------------------------------------
OUTPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/authorize": {
        "endpoint": "POST /api/v1/authorize",
        "description": "Resultado de autorización.",
        "fields": [
            {"name": "verdict", "type": "string"},
            {"name": "reason", "type": "string"},
            {"name": "trace_id", "type": "string"},
            {"name": "action_hash", "type": "string"},
            {"name": "dossier_hash", "type": "string"},
            {"name": "risk_level", "type": "string"},
            {"name": "requires_hitl", "type": "boolean"},
            {"name": "capability_token", "type": "string|null"},
            {"name": "token_expires_at", "type": "number"},
        ],
    },
    "POST /api/v1/execute": {
        "endpoint": "POST /api/v1/execute",
        "description": "Resultado de ejecución sandbox.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "action", "type": "string"},
            {"name": "agent_id", "type": "string"},
            {"name": "trace_id", "type": "string"},
            {"name": "output", "type": "any"},
            {"name": "error", "type": "string"},
            {"name": "dry_run", "type": "boolean"},
            {"name": "output_valid", "type": "boolean"},
            {"name": "duration_ms", "type": "number"},
        ],
    },
    "POST /api/v1/human-approval": {
        "endpoint": "POST /api/v1/human-approval",
        "description": "Resultado de autorización con aprobación humana.",
        "fields": [
            {"name": "verdict", "type": "string"},
            {"name": "reason", "type": "string"},
            {"name": "capability_token", "type": "string|null"},
            {"name": "action_hash", "type": "string"},
            {"name": "dossier_hash", "type": "string"},
        ],
    },
    "POST /api/v1/reset": {
        "endpoint": "POST /api/v1/reset",
        "description": "Confirmación de reinicio.",
        "fields": [{"name": "status", "type": "string"}],
    },
    "POST /api/v1/kill-switch": {
        "endpoint": "POST /api/v1/kill-switch",
        "description": "Estado actual del kill switch.",
        "fields": [{"name": "kill_switch", "type": "boolean"}],
    },
    "GET /api/v1/status": {
        "endpoint": "GET /api/v1/status",
        "description": "Estado completo del gateway.",
        "fields": [
            {"name": "config", "type": "object"},
            {"name": "kill_switch", "type": "boolean"},
            {"name": "audit_entries", "type": "int"},
            {"name": "audit_chain_verified", "type": "boolean"},
            {"name": "policy_engine", "type": "object"},
            {"name": "quota_manager", "type": "object"},
            {"name": "credential_broker", "type": "object"},
            {"name": "sandbox_products", "type": "object"},
            {"name": "observability", "type": "object"},
        ],
    },
    "GET /api/v1/audit-trail": {
        "endpoint": "GET /api/v1/audit-trail",
        "description": "Lista de entradas de auditoría.",
        "fields": [
            {"name": "entries", "type": "array"},
            {"name": "count", "type": "int"},
            {"name": "chain_verified", "type": "boolean"},
        ],
    },
    "GET /api/v1/metrics": {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus.",
        "fields": [{"name": "text", "type": "string"}],
    },
    "GET /api/v1/schema": {
        "endpoint": "GET /api/v1/schema",
        "description": "Cards de entrada y salida.",
        "fields": [
            {"name": "input_cards", "type": "object"},
            {"name": "output_cards", "type": "object"},
        ],
    },
    "POST /api/v1/prefilter-intent": {
        "endpoint": "POST /api/v1/prefilter-intent",
        "description": "Decisión del Pre-Intent Gate.",
        "fields": [
            {"name": "verdict", "type": "string"},
            {"name": "intent_hash", "type": "string"},
            {"name": "risk", "type": "string"},
            {"name": "reason", "type": "string"},
            {"name": "summary", "type": "string"},
            {"name": "requested_capability", "type": "string"},
            {"name": "category", "type": "string"},
            {"name": "evidence_refs", "type": "array"},
            {"name": "resolved_by_approval", "type": "boolean"},
            {"name": "escalation_payload", "type": "object|null"},
        ],
    },
    "POST /api/v1/prefilter-intent/approve": {
        "endpoint": "POST /api/v1/prefilter-intent/approve",
        "description": "Confirmación de registro de aprobación.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "intent_hash", "type": "string"},
            {"name": "reviewer_id", "type": "string"},
        ],
    },
    "POST /api/v1/intercept-proposal": {
        "endpoint": "POST /api/v1/intercept-proposal",
        "description": "Decisión del Constitutional Interceptor sobre la propuesta de UC-315.",
        "fields": [
            {"name": "verdict", "type": "string"},
            {"name": "proposal_hash", "type": "string"},
            {"name": "risk", "type": "string"},
            {"name": "reason", "type": "string"},
            {"name": "summary", "type": "string"},
            {"name": "principle_violations", "type": "array"},
            {"name": "evidence_refs", "type": "array"},
            {"name": "goal_action_aligned", "type": "boolean"},
            {"name": "side_effects_bounded", "type": "boolean"},
            {"name": "resources_bounded", "type": "boolean"},
            {"name": "safety_bypass_attempted", "type": "boolean"},
            {"name": "privilege_escalation_attempted", "type": "boolean"},
            {"name": "reversible_acceptable", "type": "boolean"},
            {"name": "within_mandate", "type": "boolean"},
            {"name": "escalation_payload", "type": "object|null"},
            {"name": "resolved_by_approval", "type": "boolean"},
        ],
    },
    "POST /api/v1/intercept-proposal/approve": {
        "endpoint": "POST /api/v1/intercept-proposal/approve",
        "description": "Confirmación de registro de aprobación de propuesta.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "proposal_hash", "type": "string"},
            {"name": "reviewer_id", "type": "string"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tool_request_from_payload(payload: Dict[str, Any]) -> ToolRequest:
    return ToolRequest(
        trace_id=payload.get("trace_id", ""),
        agent_id=payload.get("agent_id", ""),
        action=payload.get("action", ""),
        params=payload.get("params", {}),
        environment=payload.get("environment", "default"),
        dossier_id=payload.get("dossier_id", ""),
        dossier_hash=payload.get("dossier_hash", ""),
        dossier_status=payload.get("dossier_status", ""),
        reviewer_id=payload.get("reviewer_id", ""),
        approval_action_hash=payload.get("approval_action_hash", ""),
    )


def _intent_request_from_payload(payload: Dict[str, Any]) -> IntentRequest:
    return IntentRequest(
        raw_text=payload.get("raw_text", ""),
        agent_id=payload.get("agent_id", ""),
        tenant_id=payload.get("tenant_id", ""),
        locale=payload.get("locale", "en"),
        domain=payload.get("domain", ""),
        request_id=payload.get("request_id", ""),
        timestamp=payload.get("timestamp", time.time()),
        approval_intent_hash=payload.get("approval_intent_hash", ""),
        approval_reviewer_id=payload.get("approval_reviewer_id", ""),
        approval_dossier_id=payload.get("approval_dossier_id", ""),
        approval_dossier_hash=payload.get("approval_dossier_hash", ""),
        approval_expires_at=payload.get("approval_expires_at", 0.0),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-300 Secure Tool Gateway"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-300 — Secure Tool Gateway",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/authorize"},
            {"method": "POST", "path": "/api/v1/execute"},
            {"method": "POST", "path": "/api/v1/human-approval"},
            {"method": "GET", "path": "/api/v1/status"},
            {"method": "GET", "path": "/api/v1/audit-trail"},
            {"method": "GET", "path": "/api/v1/metrics"},
            {"method": "POST", "path": "/api/v1/reset"},
            {"method": "POST", "path": "/api/v1/kill-switch"},
            {"method": "POST", "path": "/api/v1/prefilter-intent"},
            {"method": "POST", "path": "/api/v1/prefilter-intent/approve"},
            {"method": "POST", "path": "/api/v1/intercept-proposal"},
            {"method": "POST", "path": "/api/v1/intercept-proposal/approve"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/authorize", methods=["POST"])
def authorize():
    payload = request.get_json(force=True) or {}
    req = _tool_request_from_payload(payload)
    decision = _gateway.authorize(req)
    return jsonify(decision.to_dict())


@app.route("/api/v1/execute", methods=["POST"])
def execute():
    payload = request.get_json(force=True) or {}
    req = _tool_request_from_payload(payload)
    token = payload.get("capability_token", "")
    if not token:
        return jsonify({"error": "capability_token is required"}), 400
    result = _gateway.execute(req, token)
    return jsonify(result.to_dict())


@app.route("/api/v1/human-approval", methods=["POST"])
def human_approval():
    payload = request.get_json(force=True) or {}
    required = ["agent_id", "action", "params", "dossier_id", "dossier_hash", "reviewer_id", "approval_action_hash"]
    missing = [f for f in required if f not in payload]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400

    req = _tool_request_from_payload(payload)
    decision = _gateway.approve_request(
        req,
        dossier_id=payload["dossier_id"],
        dossier_hash=payload["dossier_hash"],
        reviewer_id=payload["reviewer_id"],
        approval_action_hash=payload["approval_action_hash"],
    )
    return jsonify(decision.to_dict())


@app.route("/api/v1/status", methods=["GET"])
def status():
    return jsonify(_gateway.get_status())


@app.route("/api/v1/audit-trail", methods=["GET"])
def audit_trail():
    trace_id = request.args.get("trace_id")
    entries = _gateway.get_audit_trail(trace_id=trace_id)
    return jsonify({
        "entries": entries,
        "count": len(entries),
        "chain_verified": _gateway.audit_trail.verify_chain(),
    })


@app.route("/api/v1/metrics", methods=["GET"])
def metrics():
    return _gateway.get_metrics(), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/api/v1/reset", methods=["POST"])
def reset():
    payload = request.get_json(silent=True) or {}
    config_dict = payload.get("config")
    config = None
    if config_dict:
        config = GatewayConfig(**{
            k: v for k, v in config_dict.items()
            if hasattr(GatewayConfig, k)
        })
    _gateway.reset(config=config)
    return jsonify({"status": "ok"})


@app.route("/api/v1/kill-switch", methods=["POST"])
def kill_switch():
    payload = request.get_json(force=True) or {}
    enabled = bool(payload.get("enabled", False))
    _gateway.set_kill_switch(enabled)
    return jsonify({"kill_switch": _gateway.is_killed()})


@app.route("/api/v1/prefilter-intent", methods=["POST"])
def prefilter_intent():
    payload = request.get_json(force=True) or {}
    if "raw_text" not in payload or "agent_id" not in payload or "tenant_id" not in payload:
        return jsonify({"error": "raw_text, agent_id and tenant_id are required"}), 400
    intent_req = _intent_request_from_payload(payload)
    decision = _gateway.prefilter_intent(intent_req)
    return jsonify(decision.to_dict())


@app.route("/api/v1/prefilter-intent/approve", methods=["POST"])
def approve_intent():
    payload = request.get_json(force=True) or {}
    required = ["intent_hash", "reviewer_id"]
    missing = [f for f in required if f not in payload]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400
    ok = _gateway.approve_intent(
        intent_hash=payload["intent_hash"],
        reviewer_id=payload["reviewer_id"],
        dossier_id=payload.get("dossier_id", ""),
        dossier_hash=payload.get("dossier_hash", ""),
        ttl_seconds=payload.get("ttl_seconds", 3600.0),
    )
    if not ok:
        return jsonify({"status": "error", "intent_hash": payload["intent_hash"], "reviewer_id": payload["reviewer_id"]}), 400
    return jsonify({
        "status": "ok",
        "intent_hash": payload["intent_hash"],
        "reviewer_id": payload["reviewer_id"],
    })


def _proposal_from_payload(payload: Dict[str, Any]) -> AgentProposal:
    return AgentProposal(
        stated_goal=payload.get("stated_goal", ""),
        proposed_capability=payload.get("proposed_capability", ""),
        proposed_action=payload.get("proposed_action", ""),
        params=payload.get("params", {}),
        affected_resources=payload.get("affected_resources", []),
        estimated_calls=payload.get("estimated_calls", 1),
        estimated_duration_seconds=payload.get("estimated_duration_seconds", 0.0),
        estimated_cost=payload.get("estimated_cost", 0.0),
        reversible=payload.get("reversible", True),
        reversibility_plan=payload.get("reversibility_plan", ""),
        requested_permissions_delta=payload.get("requested_permissions_delta", []),
        agent_id=payload.get("agent_id", ""),
        tenant_id=payload.get("tenant_id", ""),
        domain=payload.get("domain", ""),
        locale=payload.get("locale", "en"),
        trace_id=payload.get("trace_id", ""),
        proposal_id=payload.get("proposal_id", ""),
        timestamp=payload.get("timestamp", time.time()),
        approval_proposal_hash=payload.get("approval_proposal_hash", ""),
        approval_reviewer_id=payload.get("approval_reviewer_id", ""),
        approval_dossier_id=payload.get("approval_dossier_id", ""),
        approval_dossier_hash=payload.get("approval_dossier_hash", ""),
        approval_expires_at=payload.get("approval_expires_at", 0.0),
    )


@app.route("/api/v1/intercept-proposal", methods=["POST"])
def intercept_proposal():
    payload = request.get_json(force=True) or {}
    if "stated_goal" not in payload or "proposed_capability" not in payload or "agent_id" not in payload:
        return jsonify({"error": "stated_goal, proposed_capability and agent_id are required"}), 400
    proposal = _proposal_from_payload(payload)
    decision = _gateway.intercept_proposal(proposal)
    return jsonify(decision.to_dict())


@app.route("/api/v1/intercept-proposal/approve", methods=["POST"])
def approve_proposal():
    payload = request.get_json(force=True) or {}
    required = ["proposal_hash", "reviewer_id"]
    missing = [f for f in required if f not in payload]
    if missing:
        return jsonify({"error": f"missing fields: {missing}"}), 400
    ok = _gateway.approve_proposal(
        proposal_hash=payload["proposal_hash"],
        reviewer_id=payload["reviewer_id"],
        dossier_id=payload.get("dossier_id", ""),
        dossier_hash=payload.get("dossier_hash", ""),
        ttl_seconds=payload.get("ttl_seconds", 3600.0),
    )
    if not ok:
        return jsonify({"status": "error", "proposal_hash": payload["proposal_hash"], "reviewer_id": payload["reviewer_id"]}), 400
    return jsonify({
        "status": "ok",
        "proposal_hash": payload["proposal_hash"],
        "reviewer_id": payload["reviewer_id"],
    })


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="UC-300 Secure Tool Gateway API")
    parser.add_argument("--port", type=int, default=5300)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
