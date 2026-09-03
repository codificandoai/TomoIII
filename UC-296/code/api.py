"""API REST Flask para UC-296 — Gestión de memoria AGI."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UC-295", "code")))

from flask import Flask, jsonify, request as flask_request

from attention_spotlight import AttentionSpotlight
from brain_memory_pipeline import BrainMemoryPipeline
from continuous_self_eval import ContinuousSelfEvaluator
from memory_config import get_config
from memory_router import IntelligentMemoryRouter
from memory_types import SpotlightItem
from metacognitive_goals import GoalManager
from models import Portfolio, TradingRequest
from self_model_store import SelfModelStore

app = Flask(__name__)

_cfg = get_config()
_router = IntelligentMemoryRouter()
_self_store = SelfModelStore()
_self_store.load()  # Garantiza que exista un self-model por defecto persistente
_spotlight = AttentionSpotlight()
_goal_manager = GoalManager()
_evaluator = ContinuousSelfEvaluator(_self_store)


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


INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "GET /health",
        "description": "Estado de salud del servicio.",
        "parameters": [],
    },
    {
        "endpoint": "POST /api/v1/memory/route",
        "description": "Clasifica la intención de una consulta y enruta a notepad, SQL o vectorial.",
        "parameters": [
            {"name": "query", "type": "string", "required": True, "example": "¿Cuál es mi objetivo actual?"},
            {"name": "context", "type": "object", "required": False, "example": {"entity_type": "products", "entity_id": "SKU-001", "attribute": "cost"}},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/store_working",
        "description": "Guarda una nota en el bloc de notas de corto plazo.",
        "parameters": [
            {"name": "content", "type": "string", "required": True},
            {"name": "note_type", "type": "string", "required": False, "default": "general"},
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/store_episode",
        "description": "Almacena un episodio en la memoria a largo plazo vectorial.",
        "parameters": [
            {"name": "text", "type": "string", "required": True},
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "GET /api/v1/memory/self_model",
        "description": "Recupera el self-model persistente del agente.",
        "parameters": [],
    },
    {
        "endpoint": "POST /api/v1/memory/self_model/goal",
        "description": "Propone o aplica un cambio seguro al current_goal del self-model.",
        "parameters": [
            {"name": "proposed_goal", "type": "string", "required": True},
            {"name": "reason", "type": "string", "required": True},
            {"name": "context", "type": "object", "required": False},
            {"name": "approved", "type": "boolean", "required": False, "default": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/spotlight",
        "description": "Aplica el spotlight de atención sobre una lista de candidatos.",
        "parameters": [
            {"name": "candidates", "type": "list[object]", "required": True, "example": [{"item_id": "hyp_1", "item_type": "hypothesis", "content": {"name": "bullish", "confidence": 0.8}}]},
            {"name": "current_goal", "type": "string", "required": False},
            {"name": "current_price", "type": "number", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/evaluate",
        "description": "Registra un episodio de desempeño y devuelve una reflexión.",
        "parameters": [
            {"name": "task", "type": "string", "required": True},
            {"name": "success", "type": "boolean", "required": True},
            {"name": "metrics", "type": "object", "required": False},
            {"name": "context", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/brain/memory_pipeline",
        "description": "Ejecuta el pipeline integrado cerebro + memoria AGI.",
        "parameters": [
            {"name": "symbols", "type": "list[string]", "required": True, "example": ["AAPL"]},
            {"name": "ticks", "type": "list[object]", "required": True},
            {"name": "portfolio", "type": "object", "required": False, "example": {"cash": 100000, "positions": {}}},
            {"name": "news", "type": "list[object]", "required": False},
            {"name": "mode", "type": "string", "required": False, "enum": ["paper", "live", "sim"], "default": "paper"},
            {"name": "approved", "type": "boolean", "required": False, "default": False},
            {"name": "propose_goal", "type": "boolean", "required": False, "default": True},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/memory/route",
        "description": "Resultado de la consulta enrutada.",
        "fields": [
            {"name": "intent", "type": "string", "enum": ["WORKING_STATE", "FACTUAL_LOOKUP", "SEMANTIC_RECALL", "SELF_MODEL"]},
            {"name": "source", "type": "string"},
            {"name": "data", "type": "any"},
            {"name": "latency_ms", "type": "number"},
            {"name": "confidence", "type": "number"},
        ],
    },
    {
        "endpoint": "GET /api/v1/memory/self_model",
        "description": "Self-model persistente y resumen de desempeño.",
        "fields": [
            {"name": "self_model", "type": "object"},
            {"name": "performance_attempts", "type": "integer"},
            {"name": "performance_successes", "type": "integer"},
            {"name": "success_rate", "type": "number"},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/self_model/goal",
        "description": "Veredicto del cambio de objetivo.",
        "fields": [
            {"name": "status", "type": "string", "enum": ["applied", "awaiting_approval", "rejected"]},
            {"name": "new_goal", "type": "string"},
            {"name": "proposal", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/spotlight",
        "description": "Candidatos seleccionados por el spotlight de atención.",
        "fields": [
            {"name": "selected", "type": "list[object]", "note": "item_id, item_type, content, score, reason"},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/evaluate",
        "description": "Episodio registrado y reflexión de desempeño.",
        "fields": [
            {"name": "episode", "type": "object"},
            {"name": "reflection", "type": "object"},
            {"name": "self_model_summary", "type": "object"},
        ],
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
            {"name": "spotlight", "type": "list[object]"},
            {"name": "self_model", "type": "object"},
            {"name": "performance_episode", "type": "object"},
            {"name": "goal_proposal", "type": "object"},
            {"name": "reflection", "type": "object"},
        ],
    },
]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc296-memory-agi", "status": "ready"})


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


def main() -> int:
    app.run(host="0.0.0.0", port=_cfg.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
