"""API REST Flask para UC-262 - IA Genérica evolutiva."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request as flask_request

from config import get_config
from graph import build_agent, resume_agent_threaded, run_agent_threaded
from memory import LongTermMemory
from models import TravelRequest

app = Flask(__name__)

_config = get_config()
_memory = LongTermMemory(_config.memory.path)
_agent = build_agent(_config)
_last_trace: Optional[Dict[str, Any]] = None


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


INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/generic/plan",
        "description": (
            "Ejecuta el copiloto genérico evolutivo: carga memoria a largo plazo, "
            "evoluciona una población de agentes, selecciona el mejor plan, reflexiona, "
            "colabora si hay contradicciones y aprende."
        ),
        "parameters": [
            {"name": "origin", "type": "string", "required": True},
            {"name": "destination", "type": "string", "required": True},
            {"name": "departure_date", "type": "string (YYYY-MM-DD)", "required": True},
            {"name": "return_date", "type": "string", "required": False},
            {"name": "travelers", "type": "integer", "required": False, "default": 1},
            {"name": "budget", "type": "number", "required": False},
            {"name": "currency", "type": "string", "required": False, "default": "USD"},
            {"name": "user_id", "type": "string", "required": False, "default": "anonymous"},
            {"name": "thread_id", "type": "string", "required": False, "description": "Sesión persistente para colaboración"},
            {"name": "preferences", "type": "object", "required": False, "example": {"airline": "Delta", "seat": "aisle"}},
            {"name": "constraints", "type": "list[string]", "required": False},
            {"name": "long_term_goals", "type": "list[string]", "required": False, "example": ["Mantener estatus Platino"]},
            {"name": "confirm_irreversible", "type": "boolean", "required": False, "default": False},
            {"name": "predict_delays", "type": "boolean", "required": False, "default": False},
            {"name": "enable_learning", "type": "boolean", "required": False, "default": True},
            {"name": "human_feedback", "type": "string", "required": False, "description": "Feedback previo (o usar /resume)"},
            {"name": "approved_alternative", "type": "string", "required": False, "description": "ID de alternativa aprobada"},
        ],
    },
    {
        "endpoint": "POST /api/v1/generic/resume",
        "description": "Reanuda un thread pausado por colaboración con feedback humano.",
        "parameters": [
            {"name": "thread_id", "type": "string", "required": True},
            {"name": "human_feedback", "type": "string", "required": False},
            {"name": "approved_alternative", "type": "string", "required": False},
        ],
    },
    {
        "endpoint": "GET /api/v1/memory/<user_id>",
        "description": "Consulta la memoria a largo plazo de un usuario.",
        "parameters": [{"name": "user_id", "type": "string", "required": True}],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/generic/plan y POST /api/v1/generic/resume",
        "description": "Resultado del copiloto genérico con itinerario, evolución y trazabilidad.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "user_id", "type": "string"},
            {"name": "thread_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["done", "awaiting_input", "awaiting_confirmation", "awaiting_collaboration"]},
            {"name": "itinerary", "type": "list[object]"},
            {"name": "total_cost", "type": "number"},
            {"name": "currency", "type": "string"},
            {"name": "best_candidate", "type": "object"},
            {"name": "evolution_stats", "type": "object"},
            {"name": "memory_context", "type": "object"},
            {"name": "reasoning_chain", "type": "list[string]"},
            {"name": "self_critique", "type": "string"},
            {"name": "reflections", "type": "list[object]"},
            {"name": "beliefs", "type": "list[object]"},
            {"name": "desires", "type": "list[object]"},
            {"name": "intentions", "type": "list[object]"},
            {"name": "audit_trail", "type": "list[object]"},
            {"name": "safety_flags", "type": "list[string]"},
            {"name": "missing_info", "type": "list[string]"},
            {"name": "requires_confirmation", "type": "boolean"},
        ],
    },
]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc262-generic-ai-agent", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/generic/plan", methods=["POST"])
def plan() -> tuple:
    global _last_trace
    payload = flask_request.get_json(silent=True) or {}
    try:
        req = TravelRequest.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"Invalid request: {exc}", 400)

    thread_id = req.thread_id or str(uuid.uuid4())
    try:
        final_state = run_agent_threaded(_agent, req, thread_id, recursion_limit=50)
    except Exception as exc:
        return _err(str(exc), 500)

    output = final_state.get("final_output", {})
    _last_trace = {"request_id": req.request_id, "thread_id": thread_id, "output": output}
    return _ok(output)


@app.route("/api/v1/generic/resume", methods=["POST"])
def resume() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    thread_id = payload.get("thread_id")
    if not thread_id:
        return _err("thread_id is required", 400)
    try:
        final_state = resume_agent_threaded(
            _agent,
            thread_id,
            human_feedback=str(payload.get("human_feedback", "")),
            approved_alternative=str(payload.get("approved_alternative", "")),
        )
    except ValueError as exc:
        return _err(str(exc), 404)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(final_state.get("final_output", {}))


@app.route("/api/v1/memory/<user_id>", methods=["GET"])
def get_memory(user_id: str) -> tuple:
    profile = _memory.get_profile(user_id)
    return _ok(profile.to_dict())


@app.route("/api/v1/generic/last_trace", methods=["GET"])
def last_trace() -> tuple:
    if _last_trace is None:
        return _err("No previous trace", 404)
    return _ok(_last_trace)


@app.errorhandler(404)
def not_found(_e: Any) -> tuple:
    return _err("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_e: Any) -> tuple:
    return _err("Method not allowed", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC262_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
