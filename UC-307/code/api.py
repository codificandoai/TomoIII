"""API Flask para UC-307: evaluación y evolución de agentes autónomos.

Endpoints:
- GET  /health
- GET  /api/v1/schema                (card views de entrada/salida)
- POST /api/v1/evaluate              (evaluar un agente)
- POST /api/v1/evolve/run            (aplicar decisión evolutiva)
- POST /api/v1/simulate/task         (simular tarea + evaluación)
- GET  /api/v1/metrics               (Prometheus)
- GET  /api/v1/metrics/json          (JSON legible)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from agent_evolution import AgentPopulation, DNAOperators
from config import EVOLUTION
from decision_engine import DecisionEngine
from evaluator import AgentPerformanceEvaluator
from metrics import METRICS
from models import (
    AgentDNA,
    DecisionAction,
    EfficiencyMetrics,
    EvaluationInput,
    EvolutionResult,
    TaskSimulation,
)

app = Flask(__name__)

# Componentes globales (pueden reemplazarse por inyección en tests)
_evaluator = AgentPerformanceEvaluator()
_operators = DNAOperators()
_population = AgentPopulation(_operators)
_engine = DecisionEngine()


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
    return _ok({"service": "uc307-agent-evolution", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/evaluate", methods=["POST"])
def evaluate() -> tuple:
    """Evalúa el rendimiento de un agente y recomienda acción."""
    data = request.get_json(silent=True) or {}
    try:
        payload = EvaluationInput.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid evaluation payload: {exc}", 400)

    evaluation = _evaluator.evaluate(payload, population_size=_population.size())
    return _ok(evaluation.model_dump_json_safe())


@app.route("/api/v1/evolve/run", methods=["POST"])
def evolve_run() -> tuple:
    """Aplica una acción evolutiva sobre el ADN de un agente."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    action_str = data.get("action")
    dna_data = data.get("dna")
    mate_id = data.get("mate_id")

    if not agent_id or not action_str:
        return _err("agent_id and action are required", 400)

    try:
        action = DecisionAction(action_str)
    except ValueError:
        valid = ", ".join(a.value for a in DecisionAction)
        return _err(f"Invalid action. Valid values: {valid}", 400)

    # Si se envía ADN, lo registra; si no, usa un ADN por defecto
    if dna_data:
        try:
            # Asegurar que el ADN se vincule al agent_id de la solicitud
            if "agent_id" not in dna_data:
                dna_data = {**dna_data, "agent_id": agent_id}
            dna = AgentDNA.model_validate(dna_data)
        except Exception as exc:
            return _err(f"Invalid DNA: {exc}", 400)
    else:
        dna = _operators.default_dna(agent_id)
    _population.register(dna)

    # Resuelve compañero de cruza si aplica
    mate_dna = _population.get(mate_id) if mate_id else _population.select_mate(agent_id)

    reason = f"Acción '{action.value}' ordenada por el orquestador central."
    new_dna: Any = None
    eliminated = False

    if action == DecisionAction.ELIMINATE:
        _population.eliminate(agent_id)
        eliminated = True
        # Si la población queda bajo mínimo, generar descendencia
        if _population.size() < 3 and mate_dna is not None:
            new_dna = _operators.crossover(
                DNAOperators().default_dna(f"rescue_{agent_id}"), mate_dna
            )
            _population.register(new_dna)
            action = DecisionAction.GROW_CROSSOVER
            reason += " Población bajo mínimo; se generó descendencia de rescate."
        elif _population.size() < 3:
            new_dna = _operators.default_dna()
            _population.register(new_dna)
            action = DecisionAction.GROW_RANDOM
            reason += " Población bajo mínimo; se generó agente aleatorio."
    else:
        new_dna = _population.evolve_one(agent_id, action, reason=reason, mate_id=mate_id)

    result = EvolutionResult(
        original_agent_id=agent_id,
        action=action,
        child_dna=new_dna if action in {DecisionAction.GROW_CROSSOVER, DecisionAction.GROW_RANDOM} else None,
        adjusted_dna=new_dna if action in {DecisionAction.ADJUST_PARAMS, DecisionAction.MUTATE, DecisionAction.RETRAIN} else None,
        eliminated=eliminated,
        reason=reason,
    )
    return _ok(result.model_dump_json_safe())


@app.route("/api/v1/simulate/task", methods=["POST"])
def simulate_task() -> tuple:
    """Simula una ejecución de agente, la evalúa con LLM Juez y registra métricas."""
    data = request.get_json(silent=True) or {}
    try:
        task = TaskSimulation.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid task payload: {exc}", 400)

    evaluation = _evaluator.evaluate_task(
        {
            "agent_id": data.get("agent_id", f"sim_{os.urandom(4).hex()}"),
            "description": task.description,
            "type": task.task_type,
            "subjective": task.subjective,
            "expected": task.expected,
        }
    )
    return _ok(evaluation.model_dump_json_safe())


@app.route("/api/v1/metrics", methods=["GET"])
def metrics() -> tuple:
    """Métricas en formato Prometheus para Grafana."""
    return METRICS.exposition(), 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}


@app.route("/api/v1/metrics/json", methods=["GET"])
def metrics_json() -> tuple:
    """Métricas en JSON legible (fallback o resumen)."""
    return _ok(METRICS.to_dict())


# ---------------------------------------------------------------------------
# Card views de entrada/salida de la API
# ---------------------------------------------------------------------------
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/evaluate",
        "description": "Recibe las tres métricas de evaluación de un agente y devuelve fitness, veredicto y acción recomendada.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_alpha_v1"},
            {"name": "task_success_rate", "type": "float (0..1)", "required": True, "example": 0.72},
            {"name": "quality_score", "type": "float (0..1 o 1..5)", "required": True, "example": 3.5},
            {
                "name": "efficiency",
                "type": "object",
                "required": True,
                "example": {
                    "tokens_used": 2400,
                    "tool_calls": 4,
                    "latency_seconds": 2.1,
                    "cost_usd": 0.04,
                },
            },
            {"name": "task_description", "type": "string", "required": False, "example": "Resumir reunión de estrategia"},
            {"name": "result_text", "type": "string", "required": False, "example": "Se acordó subir precios un 5%..."},
            {"name": "dna", "type": "object (AgentDNA)", "required": False, "example": {"hyperparams": {"temperature": 0.7}}},
            {"name": "mate_dna", "type": "object (AgentDNA)", "required": False, "example": {"hyperparams": {"temperature": 0.5}}},
        ],
    },
    {
        "endpoint": "POST /api/v1/evolve/run",
        "description": "Aplica una acción evolutiva sobre el ADN de un agente.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_alpha_v1"},
            {"name": "action", "type": "enum", "required": True, "example": "mutate", "enum": [a.value for a in DecisionAction]},
            {"name": "dna", "type": "object (AgentDNA)", "required": False, "example": {"hyperparams": {"learning_rate": 0.001, "temperature": 0.7}}},
            {"name": "mate_id", "type": "string", "required": False, "example": "agent_beta_v2"},
        ],
    },
    {
        "endpoint": "POST /api/v1/simulate/task",
        "description": "Simula una tarea del agente, evalúa calidad con LLM Juez y expone métricas.",
        "parameters": [
            {"name": "description", "type": "string", "required": True, "example": "Resumir reunión de estrategia"},
            {"name": "task_type", "type": "string", "required": False, "example": "summarization"},
            {"name": "subjective", "type": "bool", "required": False, "example": True},
            {"name": "expected", "type": "string", "required": False, "example": "decisiones clave de precios"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/evaluate",
        "description": "Resultado del análisis de performance y decisión del orquestador.",
        "fields": [
            {"name": "evaluation_id", "type": "UUID"},
            {"name": "agent_id", "type": "string"},
            {"name": "task_success_rate", "type": "float"},
            {"name": "quality_score", "type": "float"},
            {"name": "normalized_quality", "type": "float (0..1)"},
            {"name": "efficiency_score", "type": "float (0..1)"},
            {"name": "fitness", "type": "float (0..1)"},
            {"name": "verdict", "type": "string", "enum": [a.value for a in DecisionAction]},
            {"name": "actions", "type": "list[string]"},
            {"name": "reasoning", "type": "string"},
            {"name": "generated_at", "type": "ISO-8601 datetime"},
        ],
    },
    {
        "endpoint": "POST /api/v1/evolve/run",
        "description": "ADN resultante tras aplicar la acción evolutiva.",
        "fields": [
            {"name": "original_agent_id", "type": "string"},
            {"name": "action", "type": "string"},
            {"name": "child_dna", "type": "object | null"},
            {"name": "adjusted_dna", "type": "object | null"},
            {"name": "eliminated", "type": "bool"},
            {"name": "reason", "type": "string"},
        ],
    },
    {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus para Grafana.",
        "fields": [
            {"name": "uc307_tasks_total", "type": "counter", "labels": ["status"]},
            {"name": "uc307_quality_score", "type": "histogram", "buckets": [1, 2, 3, 4, 5]},
            {"name": "uc307_tokens_consumed_total", "type": "counter"},
            {"name": "uc307_tool_calls_total", "type": "counter"},
            {"name": "uc307_execution_latency_seconds", "type": "histogram"},
            {"name": "uc307_decisions_total", "type": "counter", "labels": ["action"]},
            {"name": "uc307_fitness_score", "type": "histogram"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC307_PORT", 5307))
    app.run(host="0.0.0.0", port=port, debug=False)
