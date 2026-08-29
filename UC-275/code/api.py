"""API Flask para UC-275 — Autorreflexión de Agentes.

Endpoints:
- /health
- /api/v1/schema
- /api/v1/agent/create
- /api/v1/agent/<agent_id>
- /api/v1/agents
- /api/v1/reflect/run
- /api/v1/reflect/self-refine
- /api/v1/reflect/evaluate
- /api/v1/reflect/critique
- /api/v1/reflect/episodes
- /api/v1/reflect/episode/<episode_id>
- /api/v1/memory/lessons/<action_type>
- /api/v1/memory/similar
- /api/v1/memory/stats
- /api/v1/system/status
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from config import get_config
from critic import SelfCritic
from evaluator import MetricEvaluator
from memory import ReflectionMemory
from models import ActionTrace, OutcomeObservation, ReflectionOutcome
from refiner import SelfRefiner
from reflexion_loop import ReflexionLoop, SelfReflectiveAgent

app = Flask(__name__)
_config = get_config()

# Singleton instances
_memory = ReflectionMemory(
    max_episodes=_config.memory.max_episodes,
    similarity_threshold=_config.memory.similarity_threshold,
)
_evaluator = MetricEvaluator(_config.evaluation.default_weights)
_critic = SelfCritic()
_refiner = SelfRefiner(
    max_refinement_steps=_config.refiner.max_refinement_steps,
    min_improvement_threshold=_config.refiner.min_improvement_threshold,
)

# Agentes registrados
_agents: Dict[str, ReflexionLoop] = {}
_self_refine_agents: Dict[str, SelfReflectiveAgent] = {}


def _get_or_create_loop(agent_id: str) -> ReflexionLoop:
    if agent_id not in _agents:
        _agents[agent_id] = ReflexionLoop(
            agent_id=agent_id,
            evaluator=_evaluator,
            critic=_critic,
            refiner=_refiner,
            memory=_memory,
            max_iterations=_config.refiner.max_iterations,
            convergence_threshold=_config.evaluation.convergence_threshold,
        )
    return _agents[agent_id]


def _get_or_create_sr_agent(agent_id: str) -> SelfReflectiveAgent:
    if agent_id not in _self_refine_agents:
        _self_refine_agents[agent_id] = SelfReflectiveAgent(
            agent_id=agent_id,
            criteria=_config.evaluation.default_weights,
            threshold=_config.evaluation.convergence_threshold,
            max_iterations=_config.refiner.max_iterations,
        )
    return _self_refine_agents[agent_id]


def _ok(data: Any, status: int = 200) -> tuple:
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}), status


def _err(msg: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": msg}), status


# ============================================================
# Health & Schema
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc275-agent-self-reflection", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


# ============================================================
# Agent Management
# ============================================================

@app.route("/api/v1/agent/create", methods=["POST"])
def create_agent():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    if not agent_id:
        return _err("agent_id is required")
    _get_or_create_loop(agent_id)
    _get_or_create_sr_agent(agent_id)
    return _ok({"agent_id": agent_id, "status": "created"})


@app.route("/api/v1/agent/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    stats = _memory.get_agent_stats(agent_id)
    if stats["total_episodes"] == 0 and agent_id not in _agents:
        return _err(f"Agent {agent_id} not found", 404)
    return _ok({"agent_id": agent_id, **stats})


@app.route("/api/v1/agents", methods=["GET"])
def list_agents():
    agents = []
    all_ids = set(list(_agents.keys()) + list(_self_refine_agents.keys()))
    for aid in all_ids:
        stats = _memory.get_agent_stats(aid)
        agents.append({"agent_id": aid, **stats})
    return _ok(agents)


# ============================================================
# Reflection Operations
# ============================================================

@app.route("/api/v1/reflect/run", methods=["POST"])
def reflect_run():
    """Ejecuta una acción con ciclo completo de autorreflexión (6 fases)."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    action_params = data.get("action_params", {})
    expected = data.get("expected_outcome", {})
    context = data.get("context", {})

    if not agent_id:
        return _err("agent_id is required")
    if not action_params:
        return _err("action_params is required")
    if not expected:
        return _err("expected_outcome is required")

    loop = _get_or_create_loop(agent_id)

    def action_fn(params):
        """Acción simulada: produce métricas basadas en parámetros."""
        import hashlib
        seed = int(hashlib.md5(str(params).encode()).hexdigest()[:8], 16)
        base = 0.4 + (seed % 50) / 100.0
        return {k: base + (hash(k) % 20) / 100.0 for k in expected}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics={k: min(1.0, max(0.0, v)) for k, v in result.items()},
        )

    episode = loop.execute_with_reflection(
        action_fn=action_fn,
        observe_fn=observe_fn,
        action_params=action_params,
        expected_outcome=expected,
        context=context,
    )

    return _ok({
        "episode_id": episode.episode_id,
        "agent_id": episode.agent_id,
        "final_outcome": episode.final_outcome.value if episode.final_outcome else None,
        "final_score": episode.final_score,
        "iterations": episode.iterations,
        "duration_seconds": episode.duration_seconds,
        "reflection_hash": episode.reflection_hash,
        "refinements_applied": len(episode.refinements),
        "root_cause": episode.root_cause.category.value if episode.root_cause else None,
    })


@app.route("/api/v1/reflect/self-refine", methods=["POST"])
def self_refine():
    """Ejecuta ciclo Self-Refine (generate → critique → refine) sobre una tarea de texto."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id", "default")
    task = data.get("task")
    if not task:
        return _err("task is required")

    agent = _get_or_create_sr_agent(agent_id)
    result = agent.run(task)
    return _ok(result)


@app.route("/api/v1/reflect/evaluate", methods=["POST"])
def evaluate_metrics():
    """Evalúa métricas contra expectativas (sin ejecutar acción)."""
    data = request.get_json(silent=True) or {}
    actual = data.get("actual_metrics", {})
    expected = data.get("expected_metrics", {})
    if not actual or not expected:
        return _err("actual_metrics and expected_metrics are required")

    evaluation = _evaluator.evaluate(actual, expected)
    return _ok({
        "outcome": evaluation.outcome.value,
        "score": evaluation.score,
        "metric_breakdown": evaluation.metric_breakdown,
        "expectations_met": evaluation.expectations_met,
        "deviations": evaluation.deviations,
        "severity": evaluation.severity,
        "needs_reflection": evaluation.needs_reflection,
    })


@app.route("/api/v1/reflect/critique", methods=["POST"])
def critique():
    """Analiza causa raíz a partir de evaluación y observación."""
    data = request.get_json(silent=True) or {}
    actual = data.get("actual_metrics", {})
    expected = data.get("expected_metrics", {})
    if not actual or not expected:
        return _err("actual_metrics and expected_metrics are required")

    evaluation = _evaluator.evaluate(actual, expected)
    observation = OutcomeObservation(
        trace_id="manual",
        actual_outcome=actual,
        expected_outcome=expected,
        metrics=actual,
    )
    root_cause = _critic.analyze(evaluation, observation)
    return _ok({
        "evaluation": {
            "outcome": evaluation.outcome.value,
            "score": evaluation.score,
            "needs_reflection": evaluation.needs_reflection,
        },
        "root_cause": {
            "category": root_cause.category.value,
            "primary_cause": root_cause.primary_cause,
            "contributing_factors": root_cause.contributing_factors,
            "confidence": root_cause.confidence,
        },
    })


# ============================================================
# Episodes
# ============================================================

@app.route("/api/v1/reflect/episodes", methods=["GET"])
def list_episodes():
    agent_id = request.args.get("agent_id")
    limit = int(request.args.get("limit", 50))
    episodes = list(_memory.episodes)
    if agent_id:
        episodes = [e for e in episodes if e.agent_id == agent_id]
    episodes = episodes[-limit:]
    return _ok([{
        "episode_id": ep.episode_id,
        "agent_id": ep.agent_id,
        "final_outcome": ep.final_outcome.value if ep.final_outcome else None,
        "final_score": ep.final_score,
        "iterations": ep.iterations,
        "duration_seconds": ep.duration_seconds,
        "reflection_hash": ep.reflection_hash,
    } for ep in episodes])


@app.route("/api/v1/reflect/episode/<episode_id>", methods=["GET"])
def get_episode(episode_id: str):
    ep = _memory._find_episode(episode_id)
    if not ep:
        return _err(f"Episode {episode_id} not found", 404)
    return _ok({
        "episode_id": ep.episode_id,
        "agent_id": ep.agent_id,
        "trace_id": ep.trace_id,
        "final_outcome": ep.final_outcome.value if ep.final_outcome else None,
        "final_score": ep.final_score,
        "iterations": ep.iterations,
        "duration_seconds": ep.duration_seconds,
        "reflection_hash": ep.reflection_hash,
        "evaluation": {
            "outcome": ep.evaluation.outcome.value,
            "score": ep.evaluation.score,
            "metric_breakdown": ep.evaluation.metric_breakdown,
            "deviations": ep.evaluation.deviations,
            "severity": ep.evaluation.severity,
        },
        "root_cause": {
            "category": ep.root_cause.category.value,
            "primary_cause": ep.root_cause.primary_cause,
            "confidence": ep.root_cause.confidence,
        } if ep.root_cause else None,
        "refinements": [{
            "iteration": r.iteration,
            "rationale": r.rationale,
            "expected_improvement": r.expected_improvement,
            "risk_of_change": r.risk_of_change,
            "net_benefit": r.net_benefit,
        } for r in ep.refinements],
    })


# ============================================================
# Memory
# ============================================================

@app.route("/api/v1/memory/lessons/<action_type>", methods=["GET"])
def get_lessons(action_type: str):
    return _ok(_memory.get_lessons_learned(action_type))


@app.route("/api/v1/memory/similar", methods=["POST"])
def find_similar():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id", "unknown")
    action_type = data.get("action_type", "unknown")
    action_params = data.get("action_params", {})
    top_k = data.get("top_k", 5)

    trace = ActionTrace(
        agent_id=agent_id,
        action_type=action_type,
        action_params=action_params,
    )
    similar = _memory.recall_similar(trace, top_k)
    return _ok([{
        "episode_id": ep.episode_id,
        "final_score": ep.final_score,
        "final_outcome": ep.final_outcome.value if ep.final_outcome else None,
        "iterations": ep.iterations,
    } for ep in similar])


@app.route("/api/v1/memory/stats", methods=["GET"])
def memory_stats():
    return _ok(_memory.get_system_stats())


# ============================================================
# System
# ============================================================

@app.route("/api/v1/system/status", methods=["GET"])
def system_status():
    stats = _memory.get_system_stats()
    stats["registered_agents"] = len(set(list(_agents.keys()) + list(_self_refine_agents.keys())))
    return _ok(stats)


# ============================================================
# Card Views
# ============================================================

INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/create",
        "description": "Crea un agente reflexivo con ID unico.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "trading_agent_alpha"},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/run",
        "description": "Ejecuta accion con ciclo completo de autorreflexion (6 fases: ACT->OBSERVE->EVALUATE->REFLECT->REFINE->FINALIZE).",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "trading_agent_alpha"},
            {"name": "action_params", "type": "dict", "required": True,
             "example": {"type": "trade", "risk_tolerance": 0.5, "position_size": 1.0}},
            {"name": "expected_outcome", "type": "dict", "required": True,
             "example": {"correctness": 0.8, "completeness": 0.7, "clarity": 0.8, "efficiency": 0.7}},
            {"name": "context", "type": "dict", "required": False, "example": {"market": "crypto"}},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/self-refine",
        "description": "Ejecuta ciclo Self-Refine (generate->critique->refine) sobre una tarea de texto.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": False, "default": "default"},
            {"name": "task", "type": "string", "required": True,
             "example": "Implementa una funcion que duplique un numero"},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/evaluate",
        "description": "Evalua metricas contra expectativas sin ejecutar accion (standalone).",
        "parameters": [
            {"name": "actual_metrics", "type": "dict", "required": True,
             "example": {"correctness": 0.9, "completeness": 0.6, "clarity": 0.8, "efficiency": 0.7}},
            {"name": "expected_metrics", "type": "dict", "required": True,
             "example": {"correctness": 0.8, "completeness": 0.8, "clarity": 0.7, "efficiency": 0.7}},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/critique",
        "description": "Analiza causa raiz a partir de metricas actuales vs esperadas.",
        "parameters": [
            {"name": "actual_metrics", "type": "dict", "required": True,
             "example": {"correctness": 0.4, "completeness": 0.3, "slippage": 0.1}},
            {"name": "expected_metrics", "type": "dict", "required": True,
             "example": {"correctness": 0.8, "completeness": 0.8, "slippage": 0.02}},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/similar",
        "description": "Busca episodios similares en la memoria episodica.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": False, "default": "unknown"},
            {"name": "action_type", "type": "string", "required": True, "example": "trade"},
            {"name": "action_params", "type": "dict", "required": True,
             "example": {"risk_tolerance": 0.5, "position_size": 1.0}},
            {"name": "top_k", "type": "int", "required": False, "default": 5},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/reflect/run",
        "description": "Resultado del ciclo completo de autorreflexion.",
        "fields": [
            {"name": "episode_id", "type": "string"},
            {"name": "agent_id", "type": "string"},
            {"name": "final_outcome", "type": "string", "enum": ["excellent", "good", "acceptable", "poor", "failure"]},
            {"name": "final_score", "type": "float", "range": "0.0-1.0"},
            {"name": "iterations", "type": "int"},
            {"name": "duration_seconds", "type": "float"},
            {"name": "reflection_hash", "type": "string", "description": "SHA-256 para auditoria on-chain"},
            {"name": "refinements_applied", "type": "int"},
            {"name": "root_cause", "type": "string", "enum": ["model_error", "data_stale", "strategy_flaw", "execution_error", "external_shock", "parameter_miscalibration"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/self-refine",
        "description": "Resultado del ciclo Self-Refine sobre tarea de texto.",
        "fields": [
            {"name": "output", "type": "string"},
            {"name": "score", "type": "float", "range": "0.0-1.0"},
            {"name": "iterations", "type": "int"},
            {"name": "accepted", "type": "bool"},
            {"name": "outcome", "type": "string"},
            {"name": "history", "type": "list", "description": "Historial de evaluaciones por iteracion"},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/evaluate",
        "description": "Evaluacion multi-criterio ponderada.",
        "fields": [
            {"name": "outcome", "type": "string"},
            {"name": "score", "type": "float"},
            {"name": "metric_breakdown", "type": "dict"},
            {"name": "expectations_met", "type": "bool"},
            {"name": "deviations", "type": "list"},
            {"name": "severity", "type": "float"},
            {"name": "needs_reflection", "type": "bool"},
        ],
    },
    {
        "endpoint": "POST /api/v1/reflect/critique",
        "description": "Analisis de causa raiz.",
        "fields": [
            {"name": "evaluation", "type": "dict", "description": "outcome + score + needs_reflection"},
            {"name": "root_cause", "type": "dict", "description": "category + primary_cause + contributing_factors + confidence"},
        ],
    },
    {
        "endpoint": "GET /api/v1/system/status",
        "description": "Estado global del sistema de autorreflexion.",
        "fields": [
            {"name": "total_agents", "type": "int"},
            {"name": "total_episodes", "type": "int"},
            {"name": "avg_score", "type": "float"},
            {"name": "avg_iterations", "type": "float"},
            {"name": "convergence_rate", "type": "float"},
            {"name": "memory_size", "type": "int"},
            {"name": "success_patterns", "type": "int"},
            {"name": "failure_patterns", "type": "int"},
        ],
    },
    {
        "endpoint": "GET /api/v1/memory/lessons/<action_type>",
        "description": "Lecciones aprendidas para un tipo de accion.",
        "fields": [
            {"name": "success_rate", "type": "float"},
            {"name": "common_causes", "type": "list"},
            {"name": "advice", "type": "list"},
            {"name": "total_episodes", "type": "int"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC275_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
