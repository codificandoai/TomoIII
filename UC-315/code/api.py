"""API REST Flask para UC-315 — Orquestador general + SkillRegistry + memoria AGI.

Combina los endpoints de UC-313/296 (cerebro, memoria, plasticidad, CNP y
curiosidad) con los nuevos endpoints de UC-315 para skills por dominio,
orquestación segura y reutilización de plantillas de planificación.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UC-295", "code")))

from flask import Flask, jsonify, request as flask_request

from attention_spotlight import AttentionSpotlight
from brain_memory_pipeline import BrainMemoryPipeline
from cognitive_evolution_layer import (
    AdjustmentType,
    ExecutionObservation,
    UC307CognitiveEvolutionLayer,
)
from continuous_self_eval import ContinuousSelfEvaluator
from cnp_broadcast_middleware import ContractNetMiddleware, CNPAgentProfile
from curiosity_skill_loop import CuriositySkillLoop
from domain_policy import PolicyRegistry
from domain_skills import build_default_registry
from general_orchestrator import ExecutionStep, GeneralOrchestrator, Plan
from memory_config import get_config
from memory_router import IntelligentMemoryRouter
from memory_types import SpotlightItem
from metacognitive_goals import GoalManager
from models import Portfolio, TradingRequest
from safety_supervisor_315 import SafetySupervisor315
from self_awareness_loop import SelfAwarenessLoop
from self_model_store import SelfModelStore
from skill_contracts import SkillRegistry

app = Flask(__name__)

# -----------------------------------------------------------------------------
# Infraestructura compartida UC-313/296
# -----------------------------------------------------------------------------
_cfg = get_config()
_router = IntelligentMemoryRouter()
_self_store = SelfModelStore()
_self_store.load()
_spotlight = AttentionSpotlight()
_goal_manager = GoalManager()
_evaluator = ContinuousSelfEvaluator(_self_store)
_evolution_layer = UC307CognitiveEvolutionLayer(
    memory_router=_router,
    self_store=_self_store,
    evaluator=_evaluator,
    goal_manager=_goal_manager,
)
_cnp_middleware = ContractNetMiddleware(
    agents=[
        CNPAgentProfile("alpha", skills=["technical"], reliability=0.95),
        CNPAgentProfile("beta", skills=["sentiment"], reliability=0.75),
    ],
    evolution_layer=_evolution_layer,
    memory_router=_router,
)
_curiosity_loop = CuriositySkillLoop(evolution_layer=_evolution_layer)

# -----------------------------------------------------------------------------
# Nueva capa UC-315: orquestador + SkillRegistry
# -----------------------------------------------------------------------------
_orchestrator = GeneralOrchestrator(
    skill_registry=build_default_registry(),
    safety=SafetySupervisor315(PolicyRegistry()),
)


def _ok(data: Any, status: int = 200) -> tuple:
    return (
        jsonify({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }),
        status,
    )


def _err(message: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": message}), status


# -----------------------------------------------------------------------------
# Cards de entrada/salida combinadas
# -----------------------------------------------------------------------------
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "GET /health",
        "description": "Estado de salud del servicio.",
        "parameters": [],
    },
    {
        "endpoint": "POST /api/v1/memory/route",
        "description": "Clasifica la intención de una consulta y la enruta a notepad, SQL o vectorial.",
        "parameters": [
            {"name": "query", "type": "string", "required": True},
            {"name": "context", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "GET /api/v1/memory/self_model",
        "description": "Recupera el self-model persistente del agente.",
    },
    {
        "endpoint": "POST /api/v1/brain/memory_pipeline",
        "description": "Ejecuta el pipeline integrado cerebro + memoria AGI.",
        "parameters": [
            {"name": "symbols", "type": "list[string]", "required": True},
            {"name": "ticks", "type": "list[object]", "required": True},
            {"name": "portfolio", "type": "object", "required": False},
            {"name": "mode", "type": "string", "required": False, "enum": ["paper", "live", "sim"], "default": "paper"},
            {"name": "approved", "type": "boolean", "required": False, "default": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/brain/plasticity/evaluate",
        "description": "Evalúa una observación con la capa de plasticidad UC-313.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "success", "type": "boolean", "required": True},
            {"name": "reward", "type": "number", "required": False, "default": 0.0},
            {"name": "latency_seconds", "type": "number", "required": False, "default": 0.0},
            {"name": "confidence", "type": "number", "required": False, "default": 0.0},
            {"name": "coherence", "type": "number", "required": False, "default": 0.0},
        ],
    },
    {
        "endpoint": "POST /api/v1/brain/cnp/run",
        "description": "Ejecuta una ronda de Contract Net con evaluación evolutiva.",
        "parameters": [
            {"name": "description", "type": "string", "required": True},
            {"name": "execution_success", "type": "boolean", "required": False, "default": True},
            {"name": "requirements", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/brain/curiosity/learn",
        "description": "Metaherramienta 'aprender nueva habilidad'.",
        "parameters": [
            {"name": "problem", "type": "string", "required": True},
            {"name": "expected_answer", "type": "any", "required": True},
        ],
    },
    # UC-315
    {
        "endpoint": "GET /api/v1/skills",
        "description": "Lista de skills registrados por dominio.",
        "parameters": [
            {"name": "domain", "type": "string", "required": False, "enum": ["trading", "reservations"]},
        ],
    },
    {
        "endpoint": "GET /api/v1/domains",
        "description": "Dominios y políticas de seguridad disponibles.",
    },
    {
        "endpoint": "POST /api/v1/plan",
        "description": "Construye un plan adaptativo a partir de un objetivo y dominio.",
        "parameters": [
            {"name": "goal", "type": "string", "required": True, "example": "Reservar un tren de Madrid a Barcelona mañana"},
            {"name": "domain", "type": "string", "required": True, "enum": ["trading", "reservations"]},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/plan/execute",
        "description": "Valida seguridad y ejecuta un plan previamente construido.",
        "parameters": [
            {"name": "plan", "type": "object", "required": True},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
            {"name": "auto_approve", "type": "boolean", "required": False, "default": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/orchestrate",
        "description": "Construye y ejecuta un plan en un solo paso.",
        "parameters": [
            {"name": "goal", "type": "string", "required": True},
            {"name": "domain", "type": "string", "required": True},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
            {"name": "auto_approve", "type": "boolean", "required": False, "default": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/safety/check",
        "description": "Consulta si una skill concreta está autorizada.",
        "parameters": [
            {"name": "skill_name", "type": "string", "required": True},
            {"name": "inputs", "type": "object", "required": False, "default": {}},
            {"name": "user_roles", "type": "list[string]", "required": False, "default": ["anonymous"]},
            {"name": "domain_state", "type": "object", "required": False, "default": {}},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/templates",
        "description": "Recupera o lista plantillas de plan de un dominio.",
        "parameters": [
            {"name": "domain", "type": "string", "required": True},
            {"name": "goal", "type": "string", "required": False},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "GET /health",
        "description": "Estado del servicio.",
        "fields": [{"name": "service", "type": "string"}, {"name": "status", "type": "string"}],
    },
    {
        "endpoint": "POST /api/v1/memory/route",
        "description": "Resultado de la consulta enrutada.",
        "fields": [{"name": "intent", "type": "string"}, {"name": "source", "type": "string"}, {"name": "data", "type": "any"}, {"name": "latency_ms", "type": "number"}, {"name": "confidence", "type": "number"}],
    },
    {
        "endpoint": "POST /api/v1/brain/memory_pipeline",
        "description": "Salida completa del pipeline cerebro + memoria AGI.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "symbol", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "trading_output", "type": "object"},
            {"name": "tot_prediction", "type": "object"},
            {"name": "memories", "type": "object"},
            {"name": "plasticity_result", "type": "object"},
            {"name": "reflection", "type": "object"},
        ],
    },
    {
        "endpoint": "GET /api/v1/skills",
        "description": "Lista de skills con contratos.",
        "fields": [{"name": "skills", "type": "list[object]"}],
    },
    {
        "endpoint": "POST /api/v1/plan",
        "description": "Plan adaptado con pasos candidatos y skills seleccionadas.",
        "fields": [
            {"name": "plan_id", "type": "string"},
            {"name": "domain", "type": "string"},
            {"name": "goal", "type": "string"},
            {"name": "template", "type": "string | null"},
            {"name": "steps", "type": "list[object]"},
            {"name": "status", "type": "string"},
        ],
    },
    {
        "endpoint": "POST /api/v1/orchestrate",
        "description": "Plan con decisiones de seguridad y resultados de ejecución.",
        "fields": [
            {"name": "plan_id", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "steps", "type": "list[object]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/safety/check",
        "description": "Decisión de seguridad.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "issues", "type": "list[string]"},
            {"name": "requires_approval", "type": "boolean"},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/templates",
        "description": "Plantilla de plan recuperada o lista completa.",
        "fields": [{"name": "templates", "type": "list[object]"}, {"name": "matched_template", "type": "object | null"}],
    },
]


# -----------------------------------------------------------------------------
# Endpoints UC-313/296
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index() -> tuple:
    return _ok({
        "service": "UC-315 General Orchestrator + SkillRegistry",
        "input_cards": INPUT_CARDS,
        "output_cards": OUTPUT_CARDS,
    })


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc315-memory-agi", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/memory/route", methods=["POST"])
def memory_route() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    query = payload.get("query")
    if not query:
        return _err("query is required", 400)
    result = _router.retrieve(query, context=payload.get("context", {}))
    return _ok(result.to_dict())


@app.route("/api/v1/memory/store_working", methods=["POST"])
def store_working() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    content = payload.get("content")
    if not content:
        return _err("content is required", 400)
    _router.store_working_memory(content, payload.get("note_type", "general"), payload.get("metadata", {}))
    return _ok({"stored": True, "notepad": _router.notepad.to_dict()})


@app.route("/api/v1/memory/store_episode", methods=["POST"])
def store_episode() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    text = payload.get("text")
    if not text:
        return _err("text is required", 400)
    record_id = _router.store_episode(text, payload.get("metadata", {}))
    return _ok({"stored": True, "record_id": record_id})


@app.route("/api/v1/memory/self_model", methods=["GET"])
def get_self_model() -> tuple:
    return _ok(_self_store.get_summary())


@app.route("/api/v1/memory/self_model/goal", methods=["POST"])
def propose_goal() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    proposed = payload.get("proposed_goal")
    reason = payload.get("reason")
    if not proposed or not reason:
        return _err("proposed_goal and reason are required", 400)
    current = _self_store.load().get("current_goal", "")
    result = _goal_manager.apply_goal_change(
        current,
        proposed,
        reason,
        context=payload.get("context", {}),
        approved=payload.get("approved", False),
    )
    if result["status"] == "applied":
        _self_store.update_goal(result["new_goal"], reason)
    return _ok(result)


@app.route("/api/v1/memory/spotlight", methods=["POST"])
def spotlight() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    candidates_raw = payload.get("candidates", [])
    if not candidates_raw:
        return _err("candidates are required", 400)
    candidates = [
        SpotlightItem(
            item_id=c.get("item_id", f"item_{i}"),
            item_type=c.get("item_type", "unknown"),
            content=c.get("content", {}),
        )
        for i, c in enumerate(candidates_raw)
    ]
    selected = _spotlight.select(
        candidates,
        current_goal=payload.get("current_goal", ""),
        current_price=payload.get("current_price", 0.0),
    )
    return _ok({"selected": [s.to_dict() for s in selected]})


@app.route("/api/v1/memory/evaluate", methods=["POST"])
def evaluate() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    task = payload.get("task")
    success = payload.get("success")
    if task is None or success is None:
        return _err("task and success are required", 400)
    episode = _evaluator.evaluate_execution(
        task=task,
        success=bool(success),
        metrics=payload.get("metrics", {}),
        context=payload.get("context", {}),
    )
    return _ok({
        "episode": episode.to_dict(),
        "reflection": _evaluator.reflect(limit=20),
        "self_model_summary": _self_store.get_summary(),
    })


@app.route("/api/v1/brain/memory_pipeline", methods=["POST"])
def brain_memory_pipeline() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    pipeline = BrainMemoryPipeline()
    result = pipeline.run(request, propose_goal=payload.get("propose_goal", True))
    return _ok(result)


@app.route("/api/v1/brain/plasticity/evaluate", methods=["POST"])
def plasticity_evaluate() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    try:
        obs = ExecutionObservation(**payload)
    except Exception as exc:
        return _err(f"Invalid observation: {exc}", 400)
    result = _evolution_layer.evaluate_execution(obs)
    return _ok(result.to_dict())


@app.route("/api/v1/brain/plasticity/propose", methods=["POST"])
def plasticity_propose() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    adj_type = payload.get("adjustment_type", "parameter")
    try:
        proposal = _evolution_layer.propose_adjustment(
            AdjustmentType(adj_type),
            target=payload.get("target", ""),
            change=payload.get("change", {}),
            reason=payload.get("reason", ""),
            risk_level=payload.get("risk_level", "low"),
        )
    except Exception as exc:
        return _err(f"Invalid proposal: {exc}", 400)
    return _ok(proposal.to_dict())


@app.route("/api/v1/brain/plasticity/apply", methods=["POST"])
def plasticity_apply() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    proposal_id = payload.get("proposal_id")
    if not proposal_id:
        return _err("proposal_id is required", 400)
    result = _evolution_layer.apply_proposal(
        proposal_id,
        approved=bool(payload.get("approved", False)),
        approved_by=payload.get("approved_by"),
    )
    return _ok(result)


@app.route("/api/v1/brain/plasticity/state", methods=["GET"])
def plasticity_state() -> tuple:
    return _ok({
        "synaptic_weights": _evolution_layer.get_synaptic_snapshot(),
        "homeostasis": _evolution_layer.check_homeostasis().to_dict(),
        "recent_decisions": _evolution_layer.decision_log[-10:],
    })


@app.route("/api/v1/brain/cnp/run", methods=["POST"])
def cnp_run() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    result = _cnp_middleware.run_round(
        task_id=payload.get("task_id", f"cnp_{uuid.uuid4().hex[:6]}"),
        description=payload.get("description", "Tarea CNP"),
        execution_success=bool(payload.get("execution_success", True)),
        requirements=payload.get("requirements", {}),
    )
    return _ok(result)


@app.route("/api/v1/brain/curiosity/learn", methods=["POST"])
def curiosity_learn() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    problem = payload.get("problem")
    expected = payload.get("expected_answer")
    if problem is None or expected is None:
        return _err("problem and expected_answer are required", 400)
    result = _curiosity_loop.metatool_learn_new_skill(problem, expected)
    return _ok(result)


@app.route("/api/v1/brain/curiosity/summary", methods=["GET"])
def curiosity_summary() -> tuple:
    return _ok(_curiosity_loop.summary())


@app.route("/api/v1/brain/self_awareness/loop", methods=["POST"])
def self_awareness_loop() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    n_episodes = max(1, min(int(payload.get("n_episodes", 2)), 10))
    symbol = payload.get("symbol", "AAPL")
    approved = bool(payload.get("approved", True))
    mode = payload.get("mode", "paper")
    loop = SelfAwarenessLoop()
    summary = loop.run_loop(
        n_episodes=n_episodes,
        symbol=symbol,
        approved=approved,
        mode=mode,
    )
    return _ok(summary)


# -----------------------------------------------------------------------------
# Endpoints UC-315
# -----------------------------------------------------------------------------
def _plan_from_dict(data: Dict[str, Any]) -> Plan:
    steps = [
        ExecutionStep(
            step_id=s["step_id"],
            skill_name=s["skill_name"],
            inputs=s.get("inputs", {}),
            status=s.get("status", "pending"),
            safety_decision=s.get("safety_decision"),
            result=s.get("result"),
        )
        for s in data.get("steps", [])
    ]
    return Plan(
        plan_id=data["plan_id"],
        domain=data["domain"],
        goal=data["goal"],
        template=data.get("template"),
        steps=steps,
        status=data.get("status", "draft"),
    )


@app.route("/api/v1/skills", methods=["GET"])
def list_skills() -> tuple:
    domain = flask_request.args.get("domain")
    return _ok(_orchestrator.skills.list_skills(domain))


@app.route("/api/v1/domains", methods=["GET"])
def list_domains() -> tuple:
    registry = PolicyRegistry()
    return _ok({
        "domains": registry.list(),
        "policies": {d: registry.get(d).__dict__ for d in registry.list()},
    })


@app.route("/api/v1/plan", methods=["POST"])
def build_plan() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    goal = payload.get("goal")
    domain = payload.get("domain")
    if not goal or not domain:
        return _err("'goal' y 'domain' son obligatorios", 400)
    user_roles = payload.get("user_roles", ["anonymous"])
    plan = _orchestrator.build_plan(goal, domain, user_roles)
    return _ok(plan.to_dict())


@app.route("/api/v1/plan/execute", methods=["POST"])
def execute_plan() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    plan_data = payload.get("plan")
    if not plan_data:
        return _err("'plan' es obligatorio", 400)
    plan = _plan_from_dict(plan_data)
    executed = _orchestrator.validate_and_execute(
        plan,
        user_roles=payload.get("user_roles", ["anonymous"]),
        domain_state=payload.get("domain_state", {}),
        auto_approve=payload.get("auto_approve", False),
    )
    return _ok(executed.to_dict())


@app.route("/api/v1/orchestrate", methods=["POST"])
def orchestrate() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    goal = payload.get("goal")
    domain = payload.get("domain")
    if not goal or not domain:
        return _err("'goal' y 'domain' son obligatorios", 400)
    user_roles = payload.get("user_roles", ["anonymous"])
    domain_state = payload.get("domain_state", {})
    auto_approve = payload.get("auto_approve", False)
    plan = _orchestrator.build_plan(goal, domain, user_roles)
    executed = _orchestrator.validate_and_execute(plan, user_roles, domain_state, auto_approve)
    return _ok(executed.to_dict())


@app.route("/api/v1/safety/check", methods=["POST"])
def safety_check() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    skill_name = payload.get("skill_name")
    if not skill_name:
        return _err("'skill_name' es obligatorio", 400)
    skill = _orchestrator.skills.get(skill_name)
    if not skill:
        return _err(f"Skill '{skill_name}' no encontrada", 404)
    decision = _orchestrator.safety.check(
        skill,
        payload.get("inputs", {}),
        payload.get("user_roles", ["anonymous"]),
        payload.get("domain_state", {}),
    )
    return _ok(decision)


@app.route("/api/v1/memory/templates", methods=["POST"])
def memory_templates() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    domain = payload.get("domain")
    if not domain:
        return _err("'domain' es obligatorio", 400)
    memory = _orchestrator._get_memory(domain)
    goal = payload.get("goal")
    if goal:
        template = memory.retrieve_similar_template(goal)
        return _ok({"matched_template": template.to_dict() if template else None, "all_templates": memory.list_templates()})
    return _ok({"templates": memory.list_templates()})


def main() -> int:
    app.run(host="0.0.0.0", port=_cfg.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
