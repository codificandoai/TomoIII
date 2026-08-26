"""API REST Flask para UC-259 - Agentic Flight Planner.

Endpoints:
  GET  /health
  GET  /api/v1/schema
  POST /api/v1/plan
  POST /api/v1/simulate/event
  GET  /api/v1/agent/last_trace
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request as flask_request

from config import get_config
from graph import run_agent
from models import FlightPlanRequest
from world_simulator import WorldSimulator

app = Flask(__name__)

_config = get_config()
_world = WorldSimulator(_config.world)
_last_trace: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
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


# ------------------------------------------------------------------------------
# Card views
# ------------------------------------------------------------------------------
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/plan",
        "description": (
            "Ejecuta el agente LangGraph de planificación de viajes. "
            "El sistema planifica, ejecuta, monitorea y corrige el itinerario de forma autónoma."
        ),
        "parameters": [
            {"name": "origin", "type": "string", "required": True, "example": "Madrid"},
            {"name": "destination", "type": "string", "required": True, "example": "Barcelona"},
            {"name": "departure_date", "type": "string (YYYY-MM-DD)", "required": True, "example": "2026-09-15"},
            {"name": "return_date", "type": "string (YYYY-MM-DD)", "required": False, "example": "2026-09-17"},
            {"name": "travelers", "type": "integer", "required": False, "default": 1, "example": 2},
            {"name": "budget", "type": "number", "required": False, "example": 500},
            {"name": "currency", "type": "string", "required": False, "default": "USD", "example": "EUR"},
            {
                "name": "preferences",
                "type": "object",
                "required": False,
                "example": {
                    "seat": "window",
                    "direct_flight": True,
                    "optimize_for": "cheapest",
                    "hotel_stars": 4,
                    "meeting_time": "15:00",
                    "meeting_buffer_minutes": 120,
                },
            },
            {
                "name": "constraints",
                "type": "list[string]",
                "required": False,
                "example": ["max_layover_hours=3", "no_red_eye"],
            },
            {
                "name": "confirm_irreversible",
                "type": "boolean",
                "required": False,
                "default": False,
                "description": "Permite al agente ejecutar reservas irreversibles (vuelos/hoteles).",
            },
            {
                "name": "recursion_limit",
                "type": "integer",
                "required": False,
                "default": 50,
                "description": "Límite de iteraciones del grafo LangGraph.",
            },
        ],
    },
    {
        "endpoint": "POST /api/v1/simulate/event",
        "description": "Inyecta un evento externo para observar la autocorrección del agente.",
        "parameters": [
            {"name": "item_id", "type": "string", "required": True, "example": "FL-MADBCN-100"},
            {"name": "event_type", "type": "string", "required": True, "enum": ["DELAYED", "CANCELLED", "OVERBOOKED"], "example": "DELAYED"},
            {"name": "delay_minutes", "type": "integer", "required": False, "example": 180},
            {"name": "reason", "type": "string", "required": False, "example": "Maintenance"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/plan",
        "description": "Itinerario final, traza, reflexiones y flags de seguridad.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["done", "awaiting_confirmation", "awaiting_input", "failed"]},
            {"name": "itinerary", "type": "list[object]"},
            {"name": "total_cost", "type": "number"},
            {"name": "currency", "type": "string"},
            {"name": "reflections", "type": "list[string]"},
            {"name": "safety_flags", "type": "list[string]"},
            {"name": "missing_info", "type": "list[string]"},
            {"name": "requires_confirmation", "type": "boolean"},
            {"name": "error_count", "type": "integer"},
        ],
    },
    {
        "endpoint": "GET /api/v1/agent/last_trace",
        "description": "Última traza completa generada por el agente.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "final_output", "type": "object"},
            {"name": "logs", "type": "list[object]"},
            {"name": "state", "type": "object"},
        ],
    },
]


# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc259-agentic-flight-planner", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/plan", methods=["POST"])
def plan() -> tuple:
    global _last_trace
    payload = flask_request.get_json(silent=True) or {}
    try:
        req = FlightPlanRequest.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"Invalid request: {exc}", 400)

    recursion_limit = int(payload.get("recursion_limit", _config.agent.max_iterations or 50))
    final_state = run_agent(req, _config.agent, _world, recursion_limit=recursion_limit)
    trace = {
        "request_id": req.request_id,
        "final_output": final_state.get("final_output"),
        "logs": final_state.get("logs", []),
        "state": {
            "status": final_state.get("status"),
            "reflections": final_state.get("reflections", []),
            "safety_flags": final_state.get("safety_flags", []),
            "missing_info": final_state.get("missing_info", []),
        },
    }
    _last_trace = trace
    return _ok(final_state.get("final_output"))


@app.route("/api/v1/simulate/event", methods=["POST"])
def simulate_event() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    item_id = payload.get("item_id")
    event_type = payload.get("event_type")
    if not item_id or not event_type:
        return _err("item_id and event_type are required", 400)
    _world.inject_event(
        item_id,
        event_type,
        delay_minutes=payload.get("delay_minutes", 180),
        reason=payload.get("reason", "Simulated disruption"),
    )
    return _ok({"item_id": item_id, "event_type": event_type, "injected": True})


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
    port = int(os.getenv("UC259_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
