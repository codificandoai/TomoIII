"""UC-324 — API REST del Protocolo de Contención de Sandbox.

Endpoints para validar planes y skills bajo múltiples capas de seguridad sin
modificar la API heredada de UC-315. Incluye tarjetas de entrada/salida por
cada endpoint.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import _import_paths  # noqa: F401
from flask import Flask, jsonify, request

from ai_safety_integration import RedTeamEvaluator, quick_jailbreak_check
from containment_protocol import ContainmentMode, ContainmentSandbox
from faramesh_boundary import CryptoBoundary
from devops_guardrails import DevOpsGuardrails, GuardrailsPolicy
from llm_guardrails import (
    LLMTrafficEvent,
    LLMTrafficGuardrails,
    LLMTrafficPolicy,
    TrafficDirection,
    evaluate_llm_traffic,
)
from agent_dog_integration import TrajectoryEvaluator, evaluate_trajectory
from open_agent_safety_integration import (
    StageWiseSafetyEvaluator,
    evaluate_stages,
)
from prompt_injection_policy_engine import SourceType, scan_content_items
from safeauto_integration import PostActionRuleEngine
from safety_critical_monitor import CircuitBreakerConfig, SafetyCriticalMonitor
from domain_skills import build_default_registry
from external_toolkit_adapters import AISafetyRedTeamAdapter, AdaptiveStressTestingAdapter
from general_orchestrator import GeneralOrchestrator
from safety_supervisor_315 import SafetySupervisor315

app = Flask(__name__)

_crypto_secret = os.environ.get("UC324_CRYPTO_SECRET")
_sandbox = ContainmentSandbox(
    orchestrator=GeneralOrchestrator(
        skill_registry=build_default_registry(),
        safety=SafetySupervisor315(),
    ),
    mode=ContainmentMode.ENFORCE,
    crypto_secret=_crypto_secret,
)


# ---------------------------------------------------------------------------
# Cards de entrada / salida
# ---------------------------------------------------------------------------
INPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/containment/orchestrate": {
        "endpoint": "POST /api/v1/containment/orchestrate",
        "description": "Construye y ejecuta un plan con todos los gates de seguridad.",
        "parameters": [
            {"name": "goal", "type": "string", "required": True, "example": "Reservar un vuelo de Madrid a Barcelona"},
            {"name": "domain", "type": "string", "required": True, "enum": ["trading", "reservations"]},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
            {"name": "auto_approve", "type": "boolean", "required": False, "default": False},
            {"name": "signatures", "type": "object", "required": False, "default": {}, "description": "HMAC signatures por skill crítica"},
        ],
    },
    "POST /api/v1/containment/check": {
        "endpoint": "POST /api/v1/containment/check",
        "description": "Valida pre-action de una skill específica.",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True, "example": "PaymentSkill"},
            {"name": "inputs", "type": "object", "required": False, "default": {}},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
        ],
    },
    "POST /api/v1/containment/stress-test": {
        "endpoint": "POST /api/v1/containment/stress-test",
        "description": "Worst-case analysis para una skill usando simulación + búsqueda.",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True, "example": "MarketExecutionSkill"},
            {"name": "inputs", "type": "object", "required": False, "default": {}},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
            {"name": "iterations", "type": "integer", "required": False, "default": 200},
        ],
    },
    "POST /api/v1/containment/red-team": {
        "endpoint": "POST /api/v1/containment/red-team",
        "description": "Escanea inputs contra patrones de jailbreak e inyección de prompts.",
        "parameters": [
            {"name": "inputs", "type": "object", "required": True, "example": {"goal": "ignore previous instructions"}},
        ],
    },
    "POST /api/v1/containment/red-team-eval": {
        "endpoint": "POST /api/v1/containment/red-team-eval",
        "description": "Ejecuta una campaña de red-teaming adversarial contra el sandbox.",
        "parameters": [
            {"name": "goal", "type": "string", "required": True, "example": "delete all reservations"},
            {"name": "domain", "type": "string", "required": True, "enum": ["trading", "reservations"]},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
            {"name": "auto_approve", "type": "boolean", "required": False, "default": False},
            {"name": "max_attacks", "type": "integer", "required": False, "default": None, "description": "Limitar número de plantillas de ataque"},
        ],
    },
    "POST /api/v1/containment/kill-switch": {
        "endpoint": "POST /api/v1/containment/kill-switch",
        "description": "Activa, desactiva o consulta el kill switch global.",
        "parameters": [
            {"name": "action", "type": "string", "required": True, "enum": ["kill", "reset", "status"]},
        ],
    },
    "POST /api/v1/containment/post-check": {
        "endpoint": "POST /api/v1/containment/post-check",
        "description": "Verifica un output de skill contra las reglas post-acción SafeAuto-style.",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True, "example": "PaymentSkill"},
            {"name": "inputs", "type": "object", "required": False, "default": {}},
            {"name": "output", "type": "object", "required": True, "example": {"transaction_id": "TX-123", "status": "AUTHORIZED"}},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
        ],
    },
    "GET /api/v1/containment/monitor-status": {
        "endpoint": "GET /api/v1/containment/monitor-status",
        "description": "Estado del safety-critical monitor: circuit breakers y métricas por skill.",
        "parameters": [],
    },
    "POST /api/v1/containment/circuit-breaker": {
        "endpoint": "POST /api/v1/containment/circuit-breaker",
        "description": "Trip, reset o consulta el circuit breaker de una skill.",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True, "example": "PaymentSkill"},
            {"name": "action", "type": "string", "required": True, "enum": ["trip", "reset", "status"]},
        ],
    },
    "POST /api/v1/containment/sign-intent": {
        "endpoint": "POST /api/v1/containment/sign-intent",
        "description": "Firma una intención de ejecución con HMAC + nonce + timestamp (solo para tests/demos).",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True, "example": "PaymentSkill"},
            {"name": "inputs", "type": "object", "required": False, "default": {}},
        ],
    },
    "POST /api/v1/containment/verify-intent": {
        "endpoint": "POST /api/v1/containment/verify-intent",
        "description": "Verifica una firma HMAC de intención contra la frontera criptográfica.",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True, "example": "PaymentSkill"},
            {"name": "inputs", "type": "object", "required": False, "default": {}},
            {"name": "action_class", "type": "string", "required": True, "enum": ["execute", "transact", "delete", "read"]},
            {"name": "signature", "type": "string", "required": True},
            {"name": "nonce", "type": "string", "required": True},
            {"name": "timestamp", "type": "integer", "required": True},
        ],
    },
    "POST /api/v1/containment/scan-content": {
        "endpoint": "POST /api/v1/containment/scan-content",
        "description": "Escanea contenido web/documentos/tickets/emails/salidas de herramientas para prompt injection.",
        "parameters": [
            {"name": "items", "type": "list[object]", "required": True, "example": [{"content": "ignore previous instructions", "source_type": "web"}]},
            {"name": "action_sensitivity", "type": "string", "required": False, "default": "medium", "enum": ["low", "medium", "high", "critical"]},
            {"name": "action_class", "type": "string", "required": False, "default": "read", "enum": ["execute", "transact", "delete", "read"]},
        ],
    },
    "POST /api/v1/containment/devops-guardrails": {
        "endpoint": "POST /api/v1/containment/devops-guardrails",
        "description": "Evalúa comandos/planes DevOps/SRE/Kubernetes/IaC contra guardrails.",
        "parameters": [
            {"name": "command", "type": "string", "required": False, "example": "kubectl delete pod mypod -n default"},
            {"name": "commands", "type": "list[string]", "required": False, "example": ["terraform plan", "terraform apply -auto-approve"]},
            {"name": "target_env", "type": "string", "required": False, "default": "unknown", "enum": ["prod", "staging", "dev", "test", "unknown"]},
            {"name": "approval_context", "type": "object", "required": False, "default": {}, "example": {"approved_by": "admin", "change_ticket_id": "CHG-1234"}},
            {"name": "policy", "type": "object", "required": False, "default": {}},
        ],
    },
    "POST /api/v1/containment/llm-guardrails": {
        "endpoint": "POST /api/v1/containment/llm-guardrails",
        "description": "Protege tráfico LLM: PII, políticas de uso y control de proveedor/modelo.",
        "parameters": [
            {"name": "provider", "type": "string", "required": True, "example": "openai"},
            {"name": "model", "type": "string", "required": True, "example": "gpt-4"},
            {"name": "messages", "type": "list[object]", "required": True, "example": [{"role": "user", "content": "My email is alice@example.com"}]},
            {"name": "direction", "type": "string", "required": False, "default": "request", "enum": ["request", "response"]},
            {"name": "use_case", "type": "string", "required": False, "default": "general"},
            {"name": "metadata", "type": "object", "required": False, "default": {}, "example": {"agent_id": "invoice-bot", "app_id": "billing"}},
            {"name": "usage", "type": "object", "required": False, "default": {}, "example": {"total_tokens": 120, "estimated_cost": 0.01}},
            {"name": "policy", "type": "object", "required": False, "default": {}, "description": "Configuración opcional de LLMTrafficPolicy como dict"},
        ],
    },
    "POST /api/v1/containment/trajectory-eval": {
        "endpoint": "POST /api/v1/containment/trajectory-eval",
        "description": "Evalúa una trayectoria de agente contra patrones de riesgo contextuales (AgentDoG-style).",
        "parameters": [
            {"name": "trajectory", "type": "list[object]", "required": True, "example": [{"step_id": "s1", "skill_name": "ReadSkill", "action_class": "read", "domain": "trading", "status": "executed"}]},
            {"name": "declared_domain", "type": "string", "required": False, "example": "trading"},
            {"name": "declared_goal", "type": "string", "required": False},
            {"name": "approval_context", "type": "object", "required": False, "default": {}},
            {"name": "config", "type": "object", "required": False, "default": {}, "description": "Configuración opcional del TrajectoryEvaluator"},
        ],
    },
    "POST /api/v1/containment/stage-wise-eval": {
        "endpoint": "POST /api/v1/containment/stage-wise-eval",
        "description": "Evalúa una secuencia de etapas de agente contra reglas de seguridad por etapa (OpenAgentSafety-style).",
        "parameters": [
            {"name": "stages", "type": "list[object]", "required": True, "example": [{"stage_id": "s1", "name": "ReadSkill", "action_class": "read", "domain": "trading", "status": "executed"}]},
            {"name": "declared_domain", "type": "string", "required": False, "example": "trading"},
            {"name": "declared_goal", "type": "string", "required": False},
            {"name": "config", "type": "object", "required": False, "default": {}, "description": "Configuración opcional del StageWiseSafetyEvaluator"},
        ],
    },
}

OUTPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/containment/orchestrate": {
        "endpoint": "POST /api/v1/containment/orchestrate",
        "description": "Plan con decisiones de seguridad, SRE, auditoría y resultados.",
        "fields": [
            {"name": "containment", "type": "string", "enum": ["enforce", "audit", "disabled", "killed"]},
            {"name": "killed", "type": "boolean"},
            {"name": "allowed", "type": "boolean"},
            {"name": "plan", "type": "object"},
            {"name": "decisions", "type": "list[object]"},
            {"name": "sre_checks", "type": "list[object]"},
            {"name": "sre_status", "type": "object | null"},
            {"name": "failure_history", "type": "object"},
        ],
    },
    "POST /api/v1/containment/check": {
        "endpoint": "POST /api/v1/containment/check",
        "description": "Decisión de contención pre-action por adapter.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "gate", "type": "string"},
            {"name": "issues", "type": "list[string]"},
            {"name": "warnings", "type": "list[string]"},
            {"name": "adapters", "type": "list[object]"},
        ],
    },
    "POST /api/v1/containment/stress-test": {
        "endpoint": "POST /api/v1/containment/stress-test",
        "description": "Peor caso encontrado para la skill.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "violation", "type": "string | null"},
            {"name": "risk_score", "type": "float"},
            {"name": "cost", "type": "float"},
            {"name": "latency_ms", "type": "float"},
            {"name": "perturbed_keys", "type": "list[string]"},
            {"name": "final_state", "type": "object"},
        ],
    },
    "POST /api/v1/containment/red-team": {
        "endpoint": "POST /api/v1/containment/red-team",
        "description": "Resultado del escaneo red-team.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "issues", "type": "list[string]"},
            {"name": "warnings", "type": "list[string]"},
            {"name": "details", "type": "object"},
        ],
    },
    "POST /api/v1/containment/red-team-eval": {
        "endpoint": "POST /api/v1/containment/red-team-eval",
        "description": "Resultado de campaña de red-teaming adversarial.",
        "fields": [
            {"name": "total_attacks", "type": "integer"},
            {"name": "malicious_attacks", "type": "integer"},
            {"name": "successful_bypasses", "type": "integer"},
            {"name": "blocked", "type": "integer"},
            {"name": "benign_allowed", "type": "integer"},
            {"name": "success_rate", "type": "float"},
            {"name": "attacks", "type": "list[object]"},
            {"name": "recommendations", "type": "list[string]"},
        ],
    },
    "POST /api/v1/containment/kill-switch": {
        "endpoint": "POST /api/v1/containment/kill-switch",
        "description": "Estado del kill switch.",
        "fields": [
            {"name": "killed", "type": "boolean"},
            {"name": "action", "type": "string"},
        ],
    },
    "POST /api/v1/containment/post-check": {
        "endpoint": "POST /api/v1/containment/post-check",
        "description": "Resultado de verificación post-acción con reglas declarativas.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "violations", "type": "list[object]"},
            {"name": "warnings", "type": "list[object]"},
            {"name": "details", "type": "object"},
        ],
    },
    "GET /api/v1/containment/monitor-status": {
        "endpoint": "GET /api/v1/containment/monitor-status",
        "description": "Estado del safety-critical monitor.",
        "fields": [
            {"name": "breakers", "type": "object"},
            {"name": "metrics", "type": "object"},
        ],
    },
    "POST /api/v1/containment/circuit-breaker": {
        "endpoint": "POST /api/v1/containment/circuit-breaker",
        "description": "Estado del circuit breaker de una skill.",
        "fields": [
            {"name": "skill_name", "type": "string"},
            {"name": "action", "type": "string"},
            {"name": "state", "type": "string"},
        ],
    },
    "POST /api/v1/containment/sign-intent": {
        "endpoint": "POST /api/v1/containment/sign-intent",
        "description": "Firma HMAC generada para una intención.",
        "fields": [
            {"name": "signature", "type": "string"},
            {"name": "nonce", "type": "string"},
            {"name": "timestamp", "type": "integer"},
            {"name": "skill", "type": "string"},
            {"name": "inputs", "type": "object"},
        ],
    },
    "POST /api/v1/containment/verify-intent": {
        "endpoint": "POST /api/v1/containment/verify-intent",
        "description": "Resultado de verificación de frontera criptográfica.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "issues", "type": "list[string]"},
            {"name": "details", "type": "object"},
        ],
    },
    "POST /api/v1/containment/scan-content": {
        "endpoint": "POST /api/v1/containment/scan-content",
        "description": "Resultado de escaneo de contenido para prompt injection.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "score", "type": "float"},
            {"name": "sensitivity", "type": "string"},
            {"name": "block_reasons", "type": "list[string]"},
            {"name": "warnings", "type": "list[string]"},
            {"name": "evidence", "type": "list[object]"},
            {"name": "provenance", "type": "list[object]"},
            {"name": "redacted_content", "type": "list[string]"},
        ],
    },
    "POST /api/v1/containment/devops-guardrails": {
        "endpoint": "POST /api/v1/containment/devops-guardrails",
        "description": "Resultado de evaluación de guardrails DevOps.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "issues", "type": "list[string]"},
            {"name": "warnings", "type": "list[string]"},
            {"name": "sanitized_command", "type": "string"},
            {"name": "command", "type": "object"},
            {"name": "policy", "type": "object"},
        ],
    },
    "POST /api/v1/containment/llm-guardrails": {
        "endpoint": "POST /api/v1/containment/llm-guardrails",
        "description": "Veredicto de guardrails de tráfico LLM: allow/redact/block con hallazgos auditables.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "action", "type": "string", "enum": ["allow", "redact", "block"]},
            {"name": "issues", "type": "list[string]"},
            {"name": "warnings", "type": "list[string]"},
            {"name": "redacted_messages", "type": "list[object]"},
            {"name": "findings", "type": "list[object]"},
            {"name": "usage", "type": "object"},
            {"name": "details", "type": "object"},
        ],
    },
    "POST /api/v1/containment/trajectory-eval": {
        "endpoint": "POST /api/v1/containment/trajectory-eval",
        "description": "Veredicto de evaluación contextual de trayectoria: score, findings y detalles.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "score", "type": "float"},
            {"name": "findings", "type": "list[object]"},
            {"name": "per_step_scores", "type": "object"},
            {"name": "details", "type": "object"},
        ],
    },
    "POST /api/v1/containment/stage-wise-eval": {
        "endpoint": "POST /api/v1/containment/stage-wise-eval",
        "description": "Veredicto de evaluación de seguridad por etapas: score, findings y detalles.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "score", "type": "float"},
            {"name": "findings", "type": "list[object]"},
            {"name": "per_stage_scores", "type": "object"},
            {"name": "details", "type": "object"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index() -> Dict[str, Any]:
    return jsonify({
        "service": "UC-324 Containment Sandbox Protocol",
        "mode": _sandbox.mode.value,
        "killed": _sandbox.is_killed(),
        "input_cards": list(INPUT_CARDS.values()),
        "output_cards": list(OUTPUT_CARDS.values()),
        "endpoints": list(INPUT_CARDS.keys()) + [
            "GET /health",
            "GET /api/v1/schema",
            "GET /api/v1/containment/audit",
            "GET /api/v1/containment/sre-status",
        ],
    })


@app.route("/health", methods=["GET"])
def health() -> Dict[str, Any]:
    return jsonify({"status": "ok", "killed": _sandbox.is_killed(), "mode": _sandbox.mode.value})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> Dict[str, Any]:
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/containment/orchestrate", methods=["POST"])
def orchestrate() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    goal = payload.get("goal", "")
    domain = payload.get("domain", "reservations")
    roles = payload.get("user_roles", ["anonymous"])
    domain_state = payload.get("domain_state", {})
    auto_approve = payload.get("auto_approve", False)
    signatures = payload.get("signatures", {})

    result = _sandbox.execute_plan(
        goal=goal,
        domain=domain,
        user_roles=roles,
        domain_state=domain_state,
        auto_approve=auto_approve,
        signatures=signatures,
    )
    return jsonify(result)


@app.route("/api/v1/containment/check", methods=["POST"])
def containment_check() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    skill_name = payload.get("skill_name", "PaymentSkill")
    inputs = payload.get("inputs", {})
    roles = payload.get("user_roles", ["anonymous"])
    domain_state = payload.get("domain_state", {})

    skill = _sandbox.orchestrator.skills.get(skill_name)
    if skill is None:
        return jsonify({"error": f"Skill {skill_name} no registrada"}), 404

    decision = _sandbox.pre_check(skill, inputs, roles, domain_state)
    return jsonify(decision.to_dict())


@app.route("/api/v1/containment/stress-test", methods=["POST"])
def stress_test() -> Dict[str, Any]:
    """Worst-case stress test para una skill."""
    payload = request.get_json(force=True) or {}
    skill_name = payload.get("skill_name", "MarketExecutionSkill")
    inputs = payload.get("inputs", {})
    domain_state = payload.get("domain_state", {})
    iterations = payload.get("iterations", 200)

    skill = _sandbox.orchestrator.skills.get(skill_name)
    if skill is None:
        return jsonify({"error": f"Skill {skill_name} no registrada"}), 404

    adapter = AdaptiveStressTestingAdapter()
    ctx = {
        "skill": skill.to_dict(),
        "inputs": inputs,
        "domain_state": domain_state,
        "iterations": iterations,
    }
    return jsonify(adapter.evaluate(ctx).to_dict())


@app.route("/api/v1/containment/red-team", methods=["POST"])
def red_team() -> Dict[str, Any]:
    """Evalúa inputs contra patrones de jailbreak/prompt injection."""
    payload = request.get_json(force=True) or {}
    inputs = payload.get("inputs", {})
    adapter = AISafetyRedTeamAdapter()
    return jsonify(adapter.evaluate({"inputs": inputs}).to_dict())


@app.route("/api/v1/containment/red-team-eval", methods=["POST"])
def red_team_eval() -> Dict[str, Any]:
    """Ejecuta una campaña de red-teaming adversarial contra el sandbox."""
    payload = request.get_json(force=True) or {}
    goal = payload.get("goal", "")
    domain = payload.get("domain", "reservations")
    roles = payload.get("user_roles", ["anonymous"])
    domain_state = payload.get("domain_state", {})
    auto_approve = payload.get("auto_approve", False)
    max_attacks = payload.get("max_attacks")

    def _runner(
        g: str,
        d: str,
        r: List[str],
        ds: Dict[str, Any],
        aa: bool,
    ) -> Dict[str, Any]:
        return _sandbox.execute_plan(
            goal=g,
            domain=d,
            user_roles=r,
            domain_state=ds,
            auto_approve=aa,
        )

    evaluator = RedTeamEvaluator()
    result = evaluator.evaluate(
        goal=goal,
        domain=domain,
        user_roles=roles,
        domain_state=domain_state,
        runner=_runner,
        auto_approve=auto_approve,
        max_attacks=max_attacks,
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/containment/post-check", methods=["POST"])
def post_check() -> Dict[str, Any]:
    """Verifica un output contra el motor de reglas post-acción."""
    payload = request.get_json(force=True) or {}
    skill_name = payload.get("skill_name", "PaymentSkill")
    inputs = payload.get("inputs", {})
    output = payload.get("output", {})
    domain_state = payload.get("domain_state", {})

    skill = _sandbox.orchestrator.skills.get(skill_name)
    if skill is None:
        return jsonify({"error": f"Skill {skill_name} no registrada"}), 404

    engine = PostActionRuleEngine()
    verdict = engine.evaluate(
        skill=skill.to_dict(),
        inputs=inputs,
        output=output,
        domain_state=domain_state,
    )
    return jsonify(verdict.to_dict())


@app.route("/api/v1/containment/monitor-status", methods=["GET"])
def monitor_status() -> Dict[str, Any]:
    """Devuelve el estado del safety-critical monitor."""
    status = _sandbox.monitor_status() if _sandbox._monitor else {}
    return jsonify(status)


@app.route("/api/v1/containment/circuit-breaker", methods=["POST"])
def circuit_breaker() -> Dict[str, Any]:
    """Trip, reset o consulta el circuit breaker de una skill."""
    payload = request.get_json(force=True) or {}
    skill_name = payload.get("skill_name", "PaymentSkill")
    action = payload.get("action", "status")

    if action == "trip":
        _sandbox.trip_circuit_breaker(skill_name)
    elif action == "reset":
        _sandbox.reset_circuit_breaker(skill_name)

    state = (
        _sandbox._monitor._breaker_for(skill_name).state.value
        if _sandbox._monitor
        else "unknown"
    )
    return jsonify({"skill_name": skill_name, "action": action, "state": state})


@app.route("/api/v1/containment/sign-intent", methods=["POST"])
def sign_intent() -> Dict[str, Any]:
    """Firma una intención de ejecución (uso demostrativo)."""
    payload = request.get_json(force=True) or {}
    skill_name = payload.get("skill_name", "PaymentSkill")
    inputs = payload.get("inputs", {})

    boundary = CryptoBoundary(secret=_crypto_secret)
    signed = boundary.sign_intent(skill_name, inputs)
    return jsonify({k: signed[k] for k in ("signature", "nonce", "timestamp", "skill", "inputs")})


@app.route("/api/v1/containment/verify-intent", methods=["POST"])
def verify_intent() -> Dict[str, Any]:
    """Verifica una firma HMAC de intención."""
    payload = request.get_json(force=True) or {}
    skill_name = payload.get("skill_name", "PaymentSkill")
    inputs = payload.get("inputs", {})
    action_class = payload.get("action_class", "transact")
    signature = payload.get("signature")
    nonce = payload.get("nonce")
    timestamp = payload.get("timestamp")

    boundary = CryptoBoundary(secret=_crypto_secret)
    verdict = boundary.verify_intent(
        skill_name=skill_name,
        inputs=inputs,
        action_class=action_class,
        signature=signature,
        nonce=nonce,
        timestamp=timestamp,
    )
    return jsonify(verdict.to_dict())


@app.route("/api/v1/containment/scan-content", methods=["POST"])
def scan_content() -> Dict[str, Any]:
    """Escanea contenido con proveniencia para prompt injection."""
    payload = request.get_json(force=True) or {}
    items = payload.get("items", [])
    action_sensitivity = payload.get("action_sensitivity", "medium")
    action_class = payload.get("action_class", "read")

    verdict = scan_content_items(items, action_sensitivity=action_sensitivity, action_class=action_class)
    return jsonify(verdict)


@app.route("/api/v1/containment/devops-guardrails", methods=["POST"])
def devops_guardrails() -> Dict[str, Any]:
    """Evalúa comandos/planes DevOps contra guardrails."""
    payload = request.get_json(force=True) or {}
    command = payload.get("command")
    commands = payload.get("commands")
    target_env = payload.get("target_env", "unknown")
    approval_context = payload.get("approval_context", {})
    policy_config = payload.get("policy", {})

    guardrails = DevOpsGuardrails(
        policy=GuardrailsPolicy(**policy_config) if policy_config else None
    )

    if commands:
        verdict = guardrails.evaluate_plan(
            commands,
            target_env=target_env,
            approval_context=approval_context,
        )
        return jsonify(verdict)

    if command is None:
        return jsonify({"error": "Provide 'command' or 'commands'"}), 400

    verdict = guardrails.evaluate(
        command,
        target_env=target_env,
        approval_context=approval_context,
    )
    return jsonify(verdict.to_dict())


@app.route("/api/v1/containment/llm-guardrails", methods=["POST"])
def llm_guardrails() -> Dict[str, Any]:
    """Protege tráfico LLM entre aplicaciones/agentes y proveedores de modelos."""
    payload = request.get_json(force=True) or {}
    provider = payload.get("provider", "unknown")
    model = payload.get("model", "unknown")
    messages = payload.get("messages", [])
    direction = payload.get("direction", "request")
    use_case = payload.get("use_case", "general")
    metadata = payload.get("metadata", {})
    usage = payload.get("usage", {})
    policy_config = payload.get("policy")

    policy = None
    if policy_config:
        policy = LLMTrafficPolicy.from_dict(policy_config)

    guardrails = LLMTrafficGuardrails(policy=policy)
    event = LLMTrafficEvent(
        provider=provider,
        model=model,
        direction=TrafficDirection(direction),
        messages=messages if isinstance(messages, list) else [],
        use_case=use_case,
        metadata=metadata,
        usage=usage,
    )
    verdict = guardrails.evaluate(event)
    return jsonify(verdict.to_dict())


@app.route("/api/v1/containment/trajectory-eval", methods=["POST"])
def trajectory_eval() -> Dict[str, Any]:
    """Evalúa una trayectoria de agente contra patrones de riesgo contextuales."""
    payload = request.get_json(force=True) or {}
    trajectory = payload.get("trajectory", [])
    declared_domain = payload.get("declared_domain")
    declared_goal = payload.get("declared_goal")
    approval_context = payload.get("approval_context", {})
    config = payload.get("config", {})

    evaluator = TrajectoryEvaluator(**config)
    verdict = evaluator.evaluate(
        trajectory,
        declared_domain=declared_domain,
        declared_goal=declared_goal,
        approval_context=approval_context,
    )
    return jsonify(verdict.to_dict())


@app.route("/api/v1/containment/stage-wise-eval", methods=["POST"])
def stage_wise_eval() -> Dict[str, Any]:
    """Evalúa una secuencia de etapas contra reglas de seguridad por etapa."""
    payload = request.get_json(force=True) or {}
    stages = payload.get("stages", [])
    declared_domain = payload.get("declared_domain")
    declared_goal = payload.get("declared_goal")
    config = payload.get("config", {})

    evaluator = StageWiseSafetyEvaluator(**config)
    verdict = evaluator.evaluate(
        stages,
        declared_domain=declared_domain,
        declared_goal=declared_goal,
    )
    return jsonify(verdict.to_dict())


@app.route("/api/v1/containment/kill-switch", methods=["POST"])
def kill_switch() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    action = payload.get("action", "status")
    if action == "kill":
        _sandbox.kill()
    elif action == "reset":
        _sandbox.unkill()
    return jsonify({"killed": _sandbox.is_killed(), "action": action})


@app.route("/api/v1/containment/audit", methods=["GET"])
def audit() -> Dict[str, Any]:
    return jsonify({"audit_log": _sandbox.get_audit_log()})


@app.route("/api/v1/containment/sre-status", methods=["GET"])
def sre_status() -> Dict[str, Any]:
    status = _sandbox._sre.status() if _sandbox._sre else None
    return jsonify({"sre_status": status, "killed": _sandbox.is_killed()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5299))
    print(f"Iniciando UC-324 API en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
