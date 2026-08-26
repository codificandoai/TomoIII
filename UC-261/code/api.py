"""API REST Flask para UC-261 - Agente adaptativo BDI con memoria persistente."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request as flask_request

from config import get_config
from graph import build_agent, build_output, resume_agent_threaded, run_agent_threaded
from memory import PatternMemoryDB
from models import FlightPlanRequest

app = Flask(__name__)

_config = get_config()
_memory = PatternMemoryDB(_config.memory.path)
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
        "endpoint": "POST /api/v1/agent/plan",
        "description": (
            "Ejecuta el agente BDI adaptativo. Planifica el viaje, predice retrasos, "
            "genera recomendaciones personales, aplica el control gate y aprende del feedback. "
            "Si se incluye thread_id, el estado se persiste en el checkpointer de LangGraph "
            "(MemorySaver por defecto, SqliteSaver si UC261_CHECKPOINT_PATH está definido)."
        ),
        "parameters": [
            {"name": "origin", "type": "string", "required": True, "example": "Madrid"},
            {"name": "destination", "type": "string", "required": True, "example": "Barcelona"},
            {"name": "departure_date", "type": "string (YYYY-MM-DD)", "required": True, "example": "2026-09-15"},
            {"name": "return_date", "type": "string", "required": False, "example": "2026-09-17"},
            {"name": "travelers", "type": "integer", "required": False, "default": 1, "example": 2},
            {"name": "budget", "type": "number", "required": False, "example": 2000},
            {"name": "currency", "type": "string", "required": False, "default": "USD", "example": "EUR"},
            {"name": "user_id", "type": "string", "required": False, "default": "anonymous", "example": "user-42"},
            {"name": "thread_id", "type": "string", "required": False, "description": "Identificador de sesión persistente. Si no se envía se genera uno nuevo.", "example": "sess-abc123"},
            {
                "name": "preferences",
                "type": "object",
                "required": False,
                "example": {
                    "seat": "window",
                    "direct_flight": True,
                    "optimize_for": "cheapest",
                    "hotel_chain": "Marriott",
                    "dietary": "vegetarian",
                    "meeting_time": "15:00",
                    "meeting_buffer_minutes": 120,
                },
            },
            {"name": "constraints", "type": "list[string]", "required": False, "example": ["max_layover_hours=3"]},
            {"name": "confirm_irreversible", "type": "boolean", "required": False, "default": False, "description": "Permite reservas irreversibles"},
            {"name": "predict_delays", "type": "boolean", "required": False, "default": True},
            {"name": "enable_learning", "type": "boolean", "required": False, "default": True},
            {"name": "auto_approve_all", "type": "boolean", "required": False, "default": False, "description": "Auto-aprobar todas las recomendaciones (demo)"},
            {"name": "approved_action_ids", "type": "list[string]", "required": False, "description": "IDs de recomendaciones pre-aprobadas (para continuar sin /resume)"},
            {"name": "rejected_action_ids", "type": "list[string]", "required": False, "description": "IDs de recomendaciones rechazadas"},
            {"name": "recursion_limit", "type": "integer", "required": False, "default": 50},
        ],
    },
    {
        "endpoint": "POST /api/v1/agent/resume",
        "description": "Reanuda un thread previamente pausado por un approval gate con los IDs aprobados/rechazados.",
        "parameters": [
            {"name": "thread_id", "type": "string", "required": True},
            {"name": "approved_action_ids", "type": "list[string]", "required": False, "default": []},
            {"name": "rejected_action_ids", "type": "list[string]", "required": False, "default": []},
        ],
    },
    {
        "endpoint": "GET /api/v1/profile/<user_id>",
        "description": "Consulta el perfil y patrones aprendidos de un usuario.",
        "parameters": [
            {"name": "user_id", "type": "string", "required": True, "example": "user-42"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/plan y POST /api/v1/agent/resume",
        "description": "Resultado del agente adaptativo BDI con itinerario, recomendaciones y perfil actualizado.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "user_id", "type": "string"},
            {"name": "thread_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["done", "awaiting_confirmation", "awaiting_approval", "awaiting_input", "failed"]},
            {"name": "itinerary", "type": "list[object]"},
            {"name": "total_cost", "type": "number"},
            {"name": "currency", "type": "string"},
            {"name": "beliefs", "type": "list[object]"},
            {"name": "desires", "type": "list[object]"},
            {"name": "intentions", "type": "list[object]"},
            {"name": "experiences", "type": "list[object]"},
            {"name": "recommendations", "type": "list[object]"},
            {"name": "auto_actions", "type": "list[object]"},
            {"name": "approval_actions", "type": "list[object]"},
            {"name": "profile", "type": "object"},
            {"name": "reflections", "type": "list[string]"},
            {"name": "safety_flags", "type": "list[string]"},
            {"name": "missing_info", "type": "list[string]"},
            {"name": "requires_confirmation", "type": "boolean"},
            {"name": "retry_count", "type": "integer"},
        ],
    },
]


def _wrap_output(state: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
    output = state.get("final_output") or build_output(state)
    output["thread_id"] = thread_id
    return output


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc261-adaptive-bdi-agent", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/agent/plan", methods=["POST"])
def plan() -> tuple:
    global _last_trace
    payload = flask_request.get_json(silent=True) or {}
    try:
        req = FlightPlanRequest.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"Invalid request: {exc}", 400)

    thread_id = str(payload.get("thread_id")) if payload.get("thread_id") else str(uuid.uuid4())
    recursion_limit = int(payload.get("recursion_limit", _config.agent.max_iterations or 50))
    final_state = run_agent_threaded(_agent, req, thread_id, recursion_limit=recursion_limit)
    output = _wrap_output(final_state, thread_id)

    trace = {
        "request_id": req.request_id,
        "thread_id": thread_id,
        "final_output": output,
        "logs": final_state.get("logs", []),
        "state": {
            "status": final_state.get("status"),
            "reflections": final_state.get("reflections", []),
            "safety_flags": final_state.get("safety_flags", []),
            "missing_info": final_state.get("missing_info", []),
        },
    }
    _last_trace = trace
    return _ok(output)


@app.route("/api/v1/agent/resume", methods=["POST"])
def resume() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    thread_id = payload.get("thread_id")
    if not thread_id:
        return _err("thread_id is required", 400)

    approved = payload.get("approved_action_ids") or []
    rejected = payload.get("rejected_action_ids") or []
    try:
        final_state = resume_agent_threaded(_agent, thread_id, approved, rejected)
    except ValueError as exc:
        return _err(str(exc), 404)
    output = _wrap_output(final_state, thread_id)
    return _ok(output)


@app.route("/api/v1/profile/<user_id>", methods=["GET"])
def get_profile(user_id: str) -> tuple:
    profile = _memory.get_profile(user_id)
    return _ok(profile.to_dict())


@app.route("/api/v1/agent/last_trace", methods=["GET"])
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
    port = int(os.getenv("UC261_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
