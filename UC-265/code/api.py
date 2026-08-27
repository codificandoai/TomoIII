"""API REST Flask para UC-265 - Probabilistic Model-Based Multi-Agent Travel Planner."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request as flask_request

from config import get_config
from graph import build_agent, run_agent
from models import TravelPlanRequest

app = Flask(__name__)

_config = get_config()
_agent = build_agent(_config)
_last_trace: Dict[str, Any] | None = None


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
        "endpoint": "POST /api/v1/model/plan",
        "description": (
            "Planifica un viaje usando un agente basado en modelo probabilístico. "
            "Genera planes candidatos (incluyendo MCTS), simula con Monte Carlo, "
            "selecciona el mejor y puede ejecutarlo si se autoriza. "
            "Soporta entornos parcialmente observables con estados de creencia."
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
            {"name": "preferences", "type": "object", "required": False, "example": {"airline": "Delta", "direct_only": True}},
            {"name": "constraints", "type": "list[string]", "required": False},
            {"name": "confirm_irreversible", "type": "boolean", "required": False, "default": False, "description": "Autoriza reservas irreversibles"},
            {"name": "predict_delays", "type": "boolean", "required": False, "default": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/execute",
        "description": "Ejecuta el plan seleccionado previamente (requiere confirmación).",
        "parameters": [
            {"name": "request", "type": "object", "required": True, "description": "Mismo payload que /plan pero con confirm_irreversible=true"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/feedback",
        "description": "Envía observaciones reales para reentrenar el world model probabilístico.",
        "parameters": [
            {"name": "action_type", "type": "string", "required": True},
            {"name": "item_id", "type": "string", "required": True},
            {"name": "actual_success", "type": "boolean", "required": True},
            {"name": "actual_cost", "type": "number", "required": True},
            {"name": "reward", "type": "number", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/retrain",
        "description": "Fuerza el reentrenamiento del world model con todas las experiencias acumuladas.",
        "parameters": [],
    },
    {
        "endpoint": "GET /api/v1/model/world_model",
        "description": "Devuelve el estado actual del world model.",
        "parameters": [],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/model/plan",
        "description": "Resultado de la planificación probabilística: candidatos, simulaciones, selección, ejecución y creencia.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "user_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["done", "awaiting_input", "awaiting_confirmation", "failed"]},
            {"name": "selected_plan", "type": "object"},
            {"name": "candidates", "type": "list[object]"},
            {"name": "evaluations", "type": "list[object]"},
            {"name": "execution_result", "type": "object"},
            {"name": "world_model", "type": "object"},
            {"name": "belief_state", "type": "object"},
            {"name": "partial_observations", "type": "list[object]"},
            {"name": "reflections", "type": "list[object]"},
            {"name": "logs", "type": "list[object]"},
            {"name": "missing_info", "type": "list[string]"},
            {"name": "requires_confirmation", "type": "boolean"},
        ],
    },
]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc265-probabilistic-model-based-planner", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/model/plan", methods=["POST"])
def plan() -> tuple:
    global _last_trace
    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TravelPlanRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        final_state = run_agent(request, _config, recursion_limit=50)
    except Exception as exc:
        return _err(str(exc), 500)
    output = final_state.get("final_output", {})
    _last_trace = {"request_id": request.request_id, "output": output}
    return _ok(output)


@app.route("/api/v1/model/execute", methods=["POST"])
def execute() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    req_data = payload.get("request") or payload
    req_data["confirm_irreversible"] = True
    try:
        request = TravelPlanRequest.from_dict(req_data)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        final_state = run_agent(request, _config, recursion_limit=50)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(final_state.get("final_output", {}))


@app.route("/api/v1/model/feedback", methods=["POST"])
def feedback() -> tuple:
    from models import WorldModelObservation
    from world_model import TravelWorldModel
    from travel_world import TravelWorldSimulator

    payload = flask_request.get_json(silent=True) or {}
    try:
        obs = WorldModelObservation(**payload)
    except Exception as exc:
        return _err(f"Invalid observation: {exc}", 400)
    world_model = TravelWorldModel(_config.model, TravelWorldSimulator(_config.world), app_config=_config)
    world_model.update_from_observation(obs)
    return _ok({"updated": True, "world_model": world_model.to_dict()})


@app.route("/api/v1/model/retrain", methods=["POST"])
def retrain() -> tuple:
    from world_model import TravelWorldModel
    from travel_world import TravelWorldSimulator

    world_model = TravelWorldModel(_config.model, TravelWorldSimulator(_config.world), app_config=_config)
    world_model.retrain()
    return _ok({"retrained": True, "world_model": world_model.to_dict()})


@app.route("/api/v1/model/world_model", methods=["GET"])
def world_model_state() -> tuple:
    from world_model import TravelWorldModel
    from travel_world import TravelWorldSimulator

    wm = TravelWorldModel(_config.model, TravelWorldSimulator(_config.world), app_config=_config)
    return _ok(wm.to_dict())


@app.route("/api/v1/model/last_trace", methods=["GET"])
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
    port = int(os.getenv("UC265_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
