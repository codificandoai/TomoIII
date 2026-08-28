"""API Flask para el protocolo Contract Net de UC-269.

Exposición:
- /health
- /api/v1/schema (card views)
- /api/v1/contractnet/run (ejecutar ronda completa)
- /api/v1/contractnet/outcome/<task_id> (consultar resultado)
- /api/v1/metrics (formato Prometheus para Grafana)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from flask import Flask, jsonify, request

from config import get_config
from contract_net import ContractNetManager, WorkerAgent
from metrics import METRICS
from models import ContractNetOutcome, TaskAnnouncement, WorkerProfile


app = Flask(__name__)


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


def _default_workers() -> List[WorkerAgent]:
    profiles = [
        WorkerProfile(name="researcher", skills=["feature_extraction"], skill_score=0.95, reliability=0.92, cost_factor=1.4, latency_factor=0.8),
        WorkerProfile(name="coder", skills=["classification"], skill_score=0.85, reliability=0.88, cost_factor=1.1, latency_factor=0.6),
        WorkerProfile(name="reviewer", skills=["validation"], skill_score=0.90, reliability=0.95, cost_factor=1.2, latency_factor=0.7),
    ]
    return [WorkerAgent(profile) for profile in profiles]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc269-contract-net", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


# Almacén simple de resultados en memoria para la API
_OUTCOMES: Dict[UUID, ContractNetOutcome] = {}


@app.route("/api/v1/contractnet/run", methods=["POST"])
def run_contract_net() -> tuple:
    """Ejecuta una ronda completa del protocolo Contract Net y guarda el resultado."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "Tarea sin título")
    description = data.get("description", "")
    requirements = data.get("requirements", {})

    workers_data = data.get("workers")
    if workers_data:
        try:
            profiles = [WorkerProfile.model_validate(w) for w in workers_data]
            workers = [WorkerAgent(profile) for profile in profiles]
        except Exception as exc:
            return _err(f"Invalid worker profiles: {exc}", 400)
    else:
        workers = _default_workers()

    manager = ContractNetManager(workers, config=get_config())
    task = asyncio.run(manager.announce(title, description, **requirements))
    outcome = asyncio.run(manager.run(task))
    _OUTCOMES[outcome.task_id] = outcome
    return _ok(outcome.model_dump(mode="json"))


@app.route("/api/v1/contractnet/outcome/<task_id>", methods=["GET"])
def get_outcome(task_id: str) -> tuple:
    try:
        uuid_ = UUID(task_id)
    except ValueError:
        return _err("Invalid task_id UUID", 400)
    outcome = _OUTCOMES.get(uuid_)
    if outcome is None:
        return _err("Outcome not found", 404)
    return _ok(outcome.model_dump(mode="json"))


@app.route("/api/v1/metrics", methods=["GET"])
def metrics() -> tuple:
    """Métricas en formato Prometheus para Grafana."""
    data = METRICS.exposition()
    return data, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}


@app.route("/api/v1/metrics/json", methods=["GET"])
def metrics_json() -> tuple:
    """Métricas como JSON legible."""
    return _ok(METRICS.to_dict())


INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/contractnet/run",
        "description": "Ejecuta una ronda del protocolo Contract Net: anuncio, propuestas, adjudicación y ejecución.",
        "parameters": [
            {"name": "title", "type": "string", "required": True, "example": "Clasificación de patrones con Fourier"},
            {"name": "description", "type": "string", "required": False, "example": "Extraer características con Fourier y clasificar patrones"},
            {"name": "requirements", "type": "object", "required": False, "example": {"domain": "signal_processing", "min_accuracy": 0.9}},
            {"name": "workers", "type": "list[object]", "required": False, "description": "Perfiles de workers; si no se envían, se usan workers por defecto."},
        ],
    },
    {
        "endpoint": "GET /api/v1/contractnet/outcome/<task_id>",
        "description": "Consulta el resultado de una ronda ejecutada previamente.",
        "parameters": [
            {"name": "task_id", "type": "UUID", "required": True},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/contractnet/run",
        "description": "Resultado completo de la ronda Contract Net.",
        "fields": [
            {"name": "task_id", "type": "UUID"},
            {"name": "task_title", "type": "string"},
            {"name": "status", "type": "string", "enum": ["announced", "bidding", "awarded", "executing", "completed", "failed"]},
            {"name": "proposals", "type": "list[object]"},
            {"name": "winner", "type": "string"},
            {"name": "award", "type": "object"},
            {"name": "report", "type": "object"},
            {"name": "consensus_log", "type": "object"},
            {"name": "metrics", "type": "object"},
        ],
    },
    {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas en formato Prometheus para Grafana.",
        "fields": [
            {"name": "contractnet_tasks_total", "type": "counter"},
            {"name": "contractnet_proposals_total", "type": "counter"},
            {"name": "contractnet_selection_score", "type": "histogram"},
            {"name": "contractnet_execution_duration_seconds", "type": "histogram"},
            {"name": "contractnet_results_total", "type": "counter"},
        ],
    },
]


if __name__ == "__main__":
    import os

    port = int(os.getenv("UC269_PORT", get_config().port))
    app.run(host="0.0.0.0", port=port, debug=False)
