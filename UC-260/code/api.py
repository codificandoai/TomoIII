"""API REST Flask para UC-260 - Agente BDI de viajes con predictor de retrasos."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request as flask_request

from config import get_config
from external_api import FlightDelayPredictor
from graph import run_agent
from models import FlightPlanRequest
from world_simulator import WorldSimulator

app = Flask(__name__)

_config = get_config()
_world = WorldSimulator(_config.world)
_predictor = FlightDelayPredictor(_config.predictor)
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
            "Ejecuta el agente BDI de planificación de viajes. "
            "El agente predice retrasos, delibera, forma intenciones, ejecuta, revisa y aprende."
        ),
        "parameters": [
            {"name": "origin", "type": "string", "required": True, "example": "Madrid"},
            {"name": "destination", "type": "string", "required": True, "example": "Barcelona"},
            {"name": "departure_date", "type": "string (YYYY-MM-DD)", "required": True, "example": "2026-09-15"},
            {"name": "return_date", "type": "string", "required": False, "example": "2026-09-17"},
            {"name": "travelers", "type": "integer", "required": False, "default": 1, "example": 2},
            {"name": "budget", "type": "number", "required": False, "example": 2000},
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
            {"name": "constraints", "type": "list[string]", "required": False, "example": ["max_layover_hours=3"]},
            {"name": "confirm_irreversible", "type": "boolean", "required": False, "default": False, "description": "Permite reservas irreversibles"},
            {"name": "predict_delays", "type": "boolean", "required": False, "default": True, "description": "Consultar predictor de retrasos"},
            {"name": "enable_learning", "type": "boolean", "required": False, "default": True, "description": "Habilitar memoria de experiencias"},
            {"name": "recursion_limit", "type": "integer", "required": False, "default": 50},
        ],
    },
    {
        "endpoint": "POST /api/v1/predict",
        "description": "Consulta directamente el predictor de retrasos de vuelos.",
        "parameters": [
            {"name": "flights", "type": "list[object]", "required": True, "example": [{"OPERA": "AA", "TIPOVUELO": "I", "MES": 4, "DIA": 20, "DIANOM": "Lunes", "SIGLAORI": "BOG", "SIGLAPOS": "SCL", "NROVUELO": "123", "CLASEVUELO": "Y", "TIPOPLANO": "B738"}]}
        ],
    },
    {
        "endpoint": "POST /api/v1/simulate/event",
        "description": "Inyecta un evento externo en el simulador para observar autocorrección.",
        "parameters": [
            {"name": "item_id", "type": "string", "required": True, "example": "FL-MADBAR-103"},
            {"name": "event_type", "type": "string", "required": True, "enum": ["DELAYED", "CANCELLED", "OVERBOOKED"], "example": "DELAYED"},
            {"name": "delay_minutes", "type": "integer", "required": False, "example": 180},
            {"name": "reason", "type": "string", "required": False, "example": "Maintenance"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/plan",
        "description": "Resultado BDI con itinerario, creencias, deseos, intenciones, experiencias y traza.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["done", "awaiting_confirmation", "awaiting_input", "failed"]},
            {"name": "itinerary", "type": "list[object]"},
            {"name": "total_cost", "type": "number"},
            {"name": "currency", "type": "string"},
            {"name": "beliefs", "type": "list[object]"},
            {"name": "desires", "type": "list[object]"},
            {"name": "intentions", "type": "list[object]"},
            {"name": "experiences", "type": "list[object]"},
            {"name": "reflections", "type": "list[string]"},
            {"name": "safety_flags", "type": "list[string]"},
            {"name": "missing_info", "type": "list[string]"},
            {"name": "requires_confirmation", "type": "boolean"},
            {"name": "retry_count", "type": "integer"},
        ],
    },
    {
        "endpoint": "POST /api/v1/predict",
        "description": "Respuesta normalizada del predictor de retrasos.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "source", "type": "string"},
            {"name": "error", "type": "string"},
            {"name": "predictions", "type": "list[object]"},
        ],
    },
]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc260-bdi-flight-agent", "status": "ready"})


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

    recursion_limit = int(payload.get("recursion_limit", _config.agent.max_iterations or 50))
    final_state = run_agent(req, _config.agent, _world, _predictor, recursion_limit=recursion_limit)
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


@app.route("/api/v1/predict", methods=["POST"])
def predict() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    flights = payload.get("flights", [])
    if not flights:
        return _err("flights list is required", 400)
    # Convertir cada vuelo en un ítem de itinerario mínimo para reutilizar el predictor
    items = [
        {
            "item_type": "flight",
            "id": f.get("NROVUELO", f"FL-{i}"),
            "details": {
                "airline": f.get("OPERA", ""),
                "origin": f.get("SIGLAORI", ""),
                "destination": f.get("SIGLAPOS", ""),
                "departure": f"2026-{int(f.get('MES',1)):02d}-{int(f.get('DIA',1)):02d}T08:00:00",
                "arrival": f"2026-{int(f.get('MES',1)):02d}-{int(f.get('DIA',1)):02d}T10:00:00",
                "flight_number": f.get("NROVUELO", ""),
                "cabin_class": f.get("CLASEVUELO", "Y"),
                "aircraft_type": f.get("TIPOPLANO", "B738"),
            },
        }
        for i, f in enumerate(flights)
    ]
    result = _predictor.predict(items)
    return _ok(result)


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
    port = int(os.getenv("UC260_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
