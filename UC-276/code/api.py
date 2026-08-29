"""API Flask para UC-276 — Recursive Prompting.

Endpoints:
- /health
- /api/v1/schema
- /api/v1/agent/create
- /api/v1/agent/<agent_id>
- /api/v1/agents
- /api/v1/recursive/run
- /api/v1/recursive/refine
- /api/v1/recursive/evaluate
- /api/v1/recursive/rsi
- /api/v1/recursive/sessions
- /api/v1/recursive/session/<session_id>
- /api/v1/recursive/strategies
- /api/v1/recursive/stagnation/check
- /api/v1/stats
- /api/v1/system/status
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from config import get_config
from models import (
    QualityCriteria,
    QualityLevel,
    RecursiveSession,
    RecursiveVersion,
    RefinementStrategy,
    SessionStatus,
)
from quality import QualityEvaluator
from recursive_prompter import RecursivePrompter, RSILoop
from refiner import Refiner
from stagnation import StagnationDetector

app = Flask(__name__)
_config = get_config()

# Criterios por defecto
_default_criteria = [
    QualityCriteria(name=name, weight=v["weight"],
                    min_threshold=v["min_threshold"], target=v["target"])
    for name, v in _config.quality.default_criteria.items()
]

# Agentes registrados
_agents: Dict[str, RecursivePrompter] = {}
_rsi_agents: Dict[str, RSILoop] = {}


def _get_or_create_prompter(agent_id: str) -> RecursivePrompter:
    if agent_id not in _agents:
        _agents[agent_id] = RecursivePrompter(
            agent_id=agent_id,
            criteria=_default_criteria,
            max_iterations=_config.refiner.max_iterations,
            target_score=_config.quality.target_score,
            min_acceptable_score=_config.quality.min_acceptable_score,
        )
    return _agents[agent_id]


def _get_or_create_rsi(agent_id: str) -> RSILoop:
    if agent_id not in _rsi_agents:
        _rsi_agents[agent_id] = RSILoop(agent_id=agent_id, max_cycles=5)
    return _rsi_agents[agent_id]


def _ok(data: Any, status: int = 200) -> tuple:
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }), status


def _err(msg: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": msg}), status


# ============================================================
# Health & Schema
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc276-recursive-prompting", "status": "ready"})


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
    _get_or_create_prompter(agent_id)
    _get_or_create_rsi(agent_id)
    return _ok({"agent_id": agent_id, "status": "created"})


@app.route("/api/v1/agent/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    if agent_id not in _agents:
        return _err(f"Agent {agent_id} not found", 404)
    prompter = _agents[agent_id]
    return _ok({"agent_id": agent_id, **prompter.get_stats()})


@app.route("/api/v1/agents", methods=["GET"])
def list_agents():
    agents = []
    for aid, prompter in _agents.items():
        agents.append({"agent_id": aid, **prompter.get_stats()})
    return _ok(agents)


# ============================================================
# Recursive Prompting Operations
# ============================================================

@app.route("/api/v1/recursive/run", methods=["POST"])
def recursive_run():
    """Ejecuta ciclo recursivo completo: GENERATE→EVALUATE→REFINE→COMMIT."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    input_data = data.get("input_data", "")
    task = data.get("task_description", "")
    context = data.get("context", {})
    initial = data.get("initial_version")

    if not agent_id:
        return _err("agent_id is required")
    if not input_data:
        return _err("input_data is required")
    if not task:
        return _err("task_description is required")

    prompter = _get_or_create_prompter(agent_id)
    session = prompter.run(
        input_data=input_data,
        task_description=task,
        context=context,
        initial_version=initial,
    )

    return _ok(_session_summary(session))


@app.route("/api/v1/recursive/refine", methods=["POST"])
def recursive_refine():
    """Aplica una sola iteración de refinamiento a un texto existente."""
    data = request.get_json(silent=True) or {}
    content = data.get("content", "")
    strategy_name = data.get("strategy", "clarify")
    task = data.get("task_description", "")
    context = data.get("context", {})

    if not content:
        return _err("content is required")

    try:
        strategy = RefinementStrategy(strategy_name)
    except ValueError:
        return _err(f"Invalid strategy: {strategy_name}. Valid: {[s.value for s in RefinementStrategy]}")

    # Crea versión temporal
    version = RecursiveVersion.create(iteration=0, content=content)
    evaluator = QualityEvaluator(_default_criteria)
    quality = evaluator.evaluate(version, content, task)

    refiner = Refiner()
    refined = refiner.refine(version, quality, task, strategy, context)
    prompt_used = refiner.get_prompt_for_strategy(strategy, quality, context)

    # Evalúa versión refinada
    refined_version = RecursiveVersion.create(iteration=1, content=refined, strategy=strategy)
    refined_quality = evaluator.evaluate(refined_version, content, task)

    return _ok({
        "original_score": quality.overall_score,
        "refined_score": refined_quality.overall_score,
        "improvement": round(refined_quality.overall_score - quality.overall_score, 4),
        "strategy": strategy.value,
        "prompt_used": prompt_used,
        "refined_content": refined,
        "quality_level": refined_quality.quality_level.value,
    })


@app.route("/api/v1/recursive/evaluate", methods=["POST"])
def recursive_evaluate():
    """Evalúa calidad de un texto contra criterios (sin refinar)."""
    data = request.get_json(silent=True) or {}
    content = data.get("content", "")
    original_input = data.get("original_input", content)
    task = data.get("task_description", "")

    if not content:
        return _err("content is required")

    version = RecursiveVersion.create(iteration=0, content=content)
    evaluator = QualityEvaluator(_default_criteria)
    quality = evaluator.evaluate(version, original_input, task)

    return _ok({
        "overall_score": quality.overall_score,
        "quality_level": quality.quality_level.value,
        "criteria_scores": quality.criteria_scores,
        "issues": quality.issues,
        "strengths": quality.strengths,
        "meets_threshold": quality.meets_threshold,
        "meets_target": quality.meets_target,
    })


@app.route("/api/v1/recursive/rsi", methods=["POST"])
def recursive_rsi():
    """Ejecuta ciclo RSI (Recursive Self-Improvement) estilo Gödel Agent."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id", "rsi_default")
    task = data.get("task", "")
    current_output = data.get("current_output", "")
    max_cycles = data.get("max_cycles", 5)

    if not task:
        return _err("task is required")
    if not current_output:
        return _err("current_output is required")

    rsi = _get_or_create_rsi(agent_id)
    rsi.max_cycles = max_cycles
    result = rsi.run_cycle(task, current_output)

    return _ok(result)


# ============================================================
# Sessions
# ============================================================

@app.route("/api/v1/recursive/sessions", methods=["GET"])
def list_sessions():
    agent_id = request.args.get("agent_id")
    limit = int(request.args.get("limit", 50))

    all_sessions = []
    for aid, prompter in _agents.items():
        if agent_id and aid != agent_id:
            continue
        all_sessions.extend(prompter.sessions)

    all_sessions = list(all_sessions)[-limit:]
    return _ok([_session_summary(s) for s in all_sessions])


@app.route("/api/v1/recursive/session/<session_id>", methods=["GET"])
def get_session(session_id: str):
    for prompter in _agents.values():
        for s in prompter.sessions:
            if s.session_id == session_id:
                return _ok(_session_detail(s))
    return _err(f"Session {session_id} not found", 404)


# ============================================================
# Utilities
# ============================================================

@app.route("/api/v1/recursive/strategies", methods=["GET"])
def list_strategies():
    refiner = Refiner()
    strategies = []
    for s in RefinementStrategy:
        strategies.append({
            "name": s.value,
            "prompt_template": refiner.STRATEGY_PROMPTS[s],
        })
    return _ok(strategies)


@app.route("/api/v1/recursive/stagnation/check", methods=["POST"])
def check_stagnation():
    """Verifica si una trayectoria de scores está estancada."""
    data = request.get_json(silent=True) or {}
    trajectory = data.get("trajectory", [])
    if not trajectory or len(trajectory) < 2:
        return _err("trajectory must have at least 2 scores")

    detector = StagnationDetector.from_config()
    is_stagnated, reason = detector.is_stagnated(trajectory)
    return _ok({
        "is_stagnated": is_stagnated,
        "reason": reason,
        "trajectory_length": len(trajectory),
        "last_score": trajectory[-1],
        "best_score": max(trajectory),
    })


@app.route("/api/v1/stats", methods=["GET"])
def get_stats():
    """Estadísticas globales de todos los agentes."""
    total_sessions = 0
    all_scores = []
    all_iterations = []
    converged_count = 0

    for prompter in _agents.values():
        stats = prompter.get_stats()
        total_sessions += stats["total_sessions"]
        for s in prompter.sessions:
            all_scores.append(s.final_score)
            all_iterations.append(s.total_iterations)
            if s.status == SessionStatus.CONVERGED:
                converged_count += 1

    return _ok({
        "total_agents": len(_agents),
        "total_sessions": total_sessions,
        "avg_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0,
        "avg_iterations": round(sum(all_iterations) / len(all_iterations), 2) if all_iterations else 0.0,
        "convergence_rate": round(converged_count / total_sessions, 4) if total_sessions else 0.0,
        "rsi_agents": len(_rsi_agents),
    })


@app.route("/api/v1/system/status", methods=["GET"])
def system_status():
    total_sessions = sum(len(list(p.sessions)) for p in _agents.values())
    rsi_cycles = sum(len(r.history) for r in _rsi_agents.values())
    return _ok({
        "service": "uc276-recursive-prompting",
        "total_agents": len(_agents) + len(_rsi_agents),
        "total_recursive_sessions": total_sessions,
        "total_rsi_cycles": rsi_cycles,
        "config": {
            "max_iterations": _config.refiner.max_iterations,
            "target_score": _config.quality.target_score,
            "min_acceptable": _config.quality.min_acceptable_score,
        },
    })


# ============================================================
# Helpers
# ============================================================

def _session_summary(s: RecursiveSession) -> Dict[str, Any]:
    return {
        "session_id": s.session_id,
        "agent_id": s.agent_id,
        "task_description": s.task_description[:100],
        "status": s.status.value,
        "final_score": s.final_score,
        "total_iterations": s.total_iterations,
        "convergence_reason": s.convergence_reason,
        "total_duration_seconds": s.total_duration_seconds,
        "session_hash": s.session_hash,
        "improvement_trajectory": s.improvement_trajectory,
    }


def _session_detail(s: RecursiveSession) -> Dict[str, Any]:
    summary = _session_summary(s)
    summary["versions"] = []
    for v in s.versions:
        vd = {
            "version_id": v.version_id,
            "iteration": v.iteration,
            "content_preview": v.content[:200],
            "content_hash": v.content_hash,
            "refinement_strategy": v.refinement_strategy.value if v.refinement_strategy else None,
            "delta_from_parent": v.delta_from_parent,
            "discarded": v.metadata.get("discarded", False),
        }
        if v.quality_report:
            vd["quality"] = {
                "overall_score": v.quality_report.overall_score,
                "quality_level": v.quality_report.quality_level.value,
                "criteria_scores": v.quality_report.criteria_scores,
                "issues": v.quality_report.issues,
                "strengths": v.quality_report.strengths,
            }
        summary["versions"].append(vd)
    return summary


# ============================================================
# Card Views
# ============================================================

INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/create",
        "description": "Crea un agente de recursive prompting con ID unico.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "research_agent"},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/run",
        "description": "Ejecuta ciclo recursivo completo: GENERATE->EVALUATE->REFINE->COMMIT. El agente reutiliza su propia salida como entrada para refinarla iterativamente.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "research_agent"},
            {"name": "input_data", "type": "string", "required": True,
             "example": "El machine learning es un subcampo de la inteligencia artificial que permite a los sistemas aprender de datos..."},
            {"name": "task_description", "type": "string", "required": True,
             "example": "Genera un resumen ejecutivo claro y conciso"},
            {"name": "context", "type": "dict", "required": False,
             "example": {"audience": "ejecutivos", "objective": "decision de inversion"}},
            {"name": "initial_version", "type": "string", "required": False,
             "example": "Borrador inicial si ya existe"},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/refine",
        "description": "Aplica una sola iteracion de refinamiento a un texto con estrategia especifica.",
        "parameters": [
            {"name": "content", "type": "string", "required": True,
             "example": "El texto a refinar..."},
            {"name": "strategy", "type": "string", "required": False, "default": "clarify",
             "enum": ["clarify", "concise", "expand", "correct", "restructure", "validate", "optimize", "adapt_audience"]},
            {"name": "task_description", "type": "string", "required": False},
            {"name": "context", "type": "dict", "required": False,
             "example": {"objective": "claridad", "audience": "tecnicos"}},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/evaluate",
        "description": "Evalua calidad de un texto contra criterios multi-dimension (clarity, conciseness, completeness, accuracy, coherence).",
        "parameters": [
            {"name": "content", "type": "string", "required": True,
             "example": "El texto a evaluar..."},
            {"name": "original_input", "type": "string", "required": False,
             "example": "El input original para comparar cobertura"},
            {"name": "task_description", "type": "string", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/rsi",
        "description": "Ejecuta ciclo RSI (Recursive Self-Improvement) estilo Godel Agent: Propose->Verify->Apply->Benchmark->Evaluate->Learn.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": False, "default": "rsi_default"},
            {"name": "task", "type": "string", "required": True,
             "example": "Optimiza este algoritmo de sorting"},
            {"name": "current_output", "type": "string", "required": True,
             "example": "La implementacion actual del algoritmo..."},
            {"name": "max_cycles", "type": "int", "required": False, "default": 5},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/stagnation/check",
        "description": "Verifica si una trayectoria de scores esta estancada (plateau, oscilacion, degradacion).",
        "parameters": [
            {"name": "trajectory", "type": "list[float]", "required": True,
             "example": [0.5, 0.55, 0.56, 0.56, 0.55]},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/recursive/run",
        "description": "Resultado del ciclo recursivo completo.",
        "fields": [
            {"name": "session_id", "type": "string"},
            {"name": "agent_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["converged", "stagnated", "max_iterations", "failed"]},
            {"name": "final_score", "type": "float", "range": "0.0-1.0"},
            {"name": "total_iterations", "type": "int"},
            {"name": "convergence_reason", "type": "string"},
            {"name": "total_duration_seconds", "type": "float"},
            {"name": "session_hash", "type": "string", "description": "SHA-256 para auditoria on-chain"},
            {"name": "improvement_trajectory", "type": "list[float]", "description": "Scores por iteracion"},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/refine",
        "description": "Resultado de una iteracion de refinamiento.",
        "fields": [
            {"name": "original_score", "type": "float"},
            {"name": "refined_score", "type": "float"},
            {"name": "improvement", "type": "float"},
            {"name": "strategy", "type": "string"},
            {"name": "prompt_used", "type": "string"},
            {"name": "refined_content", "type": "string"},
            {"name": "quality_level", "type": "string"},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/evaluate",
        "description": "Evaluacion multi-criterio de un texto.",
        "fields": [
            {"name": "overall_score", "type": "float"},
            {"name": "quality_level", "type": "string", "enum": ["unacceptable", "poor", "acceptable", "good", "excellent", "outstanding"]},
            {"name": "criteria_scores", "type": "dict", "description": "Score por criterio: clarity, conciseness, completeness, accuracy, coherence"},
            {"name": "issues", "type": "list[str]"},
            {"name": "strengths", "type": "list[str]"},
            {"name": "meets_threshold", "type": "bool"},
            {"name": "meets_target", "type": "bool"},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/rsi",
        "description": "Resultado del ciclo RSI (Recursive Self-Improvement).",
        "fields": [
            {"name": "agent_id", "type": "string"},
            {"name": "baseline_score", "type": "float"},
            {"name": "final_score", "type": "float"},
            {"name": "total_improvement", "type": "float"},
            {"name": "cycles_run", "type": "int"},
            {"name": "accepted_changes", "type": "int"},
            {"name": "logic_version", "type": "int"},
            {"name": "final_output", "type": "string"},
            {"name": "history", "type": "list", "description": "Historial de cada ciclo RSI"},
        ],
    },
    {
        "endpoint": "POST /api/v1/recursive/stagnation/check",
        "description": "Resultado del chequeo de estancamiento.",
        "fields": [
            {"name": "is_stagnated", "type": "bool"},
            {"name": "reason", "type": "string"},
            {"name": "trajectory_length", "type": "int"},
            {"name": "last_score", "type": "float"},
            {"name": "best_score", "type": "float"},
        ],
    },
    {
        "endpoint": "GET /api/v1/system/status",
        "description": "Estado del sistema de recursive prompting.",
        "fields": [
            {"name": "service", "type": "string"},
            {"name": "total_agents", "type": "int"},
            {"name": "total_recursive_sessions", "type": "int"},
            {"name": "total_rsi_cycles", "type": "int"},
            {"name": "config", "type": "dict"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC276_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
