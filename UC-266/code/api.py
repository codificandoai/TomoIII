"""API REST Flask para UC-266 - Agente Resiliente y Robusto."""
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
        "endpoint": "POST /api/v1/model/train",
        "description": "Genera datos sintéticos, entrena el world model probabilístico y guarda los modelos en disco.",
        "parameters": [
            {"name": "samples", "type": "integer", "required": False, "default": 500},
            {"name": "output_dir", "type": "string", "required": False, "default": "models"}
        ]
    },
    {
        "endpoint": "POST /api/v1/model/infer",
        "description": "Realiza inferencia con el modelo entrenado para un estado y acción dados.",
        "parameters": [
            {"name": "state", "type": "object", "required": True, "example": {"remaining_budget": 2000, "step": 0, "preferences": {"airline": "Delta"}}},
            {"name": "action", "type": "object", "required": True, "example": {"action_type": "flight", "item_id": "FL-TEST", "estimated_cost": 300}}
        ]
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
    {
        "endpoint": "POST /api/v1/model/recover",
        "description": "Ejecuta un bucle de recuperación ante un cambio detectado: genera planes de respaldo y los evalúa.",
        "parameters": [
            {"name": "request", "type": "object", "required": True, "description": "Payload idéntico a /plan"},
            {"name": "failed_action", "type": "object", "required": False, "description": "Acción que falló y debe evitarse en los backups"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/detect_change",
        "description": "Compara predicción vs observación real y reporta si se detecta un cambio del entorno.",
        "parameters": [
            {"name": "action", "type": "object", "required": True},
            {"name": "predicted_success_prob", "type": "number", "required": True},
            {"name": "predicted_cost", "type": "number", "required": True},
            {"name": "actual_success", "type": "boolean", "required": True},
            {"name": "actual_cost", "type": "number", "required": True},
            {"name": "observed_delay", "type": "number", "required": False, "default": 0.0},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/model/train",
        "description": "Estadísticas del entrenamiento y rutas de los modelos guardados.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "metadata.n_samples", "type": "integer"},
            {"name": "metadata.n_transitions", "type": "integer"},
            {"name": "metadata.n_observations", "type": "integer"},
            {"name": "metadata.model_type", "type": "string"},
            {"name": "saved_paths", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/infer",
        "description": "Predicción del modelo entrenado: probabilidad de éxito, recompensa esperada e incertidumbre.",
        "fields": [
            {"name": "state", "type": "object"},
            {"name": "action", "type": "object"},
            {"name": "predicted_success_probability", "type": "number"},
            {"name": "predicted_reward", "type": "number"},
            {"name": "uncertainty", "type": "number"},
        ],
    },
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
            {"name": "change_events", "type": "list[object]", "description": "Eventos de cambio detectados durante la ejecución"},
            {"name": "resilience_logs", "type": "list[object]", "description": "Logs del motor de resiliencia"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/recover",
        "description": "Plan de respaldo generado tras un cambio detectado.",
        "fields": [
            {"name": "backups", "type": "list[object]"},
            {"name": "meta", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/detect_change",
        "description": "Evento de cambio detectado (None si no supera el umbral).",
        "fields": [
            {"name": "change_event", "type": "object"},
        ],
    },
]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc266-resilient-robust-agent", "status": "ready"})


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


@app.route("/api/v1/model/train", methods=["POST"])
def train() -> tuple:
    from train import train_world_model

    payload = flask_request.get_json(silent=True) or {}
    try:
        samples = int(payload.get("samples", 500))
        output_dir = payload.get("output_dir")
    except (TypeError, ValueError) as exc:
        return _err(f"Invalid parameters: {exc}", 400)
    try:
        result = train_world_model(n_samples=samples, config=_config, output_dir=output_dir)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(result)


@app.route("/api/v1/model/infer", methods=["POST"])
def infer() -> tuple:
    from train import load_trained_model
    from world_model import TravelWorldModel
    from travel_world import TravelWorldSimulator
    from models import PlanAction, WorldModelState
    from model_persistence import ModelPersistence

    payload = flask_request.get_json(silent=True) or {}
    try:
        state_data = payload.get("state", {})
        action_data = payload.get("action", {})
        state = WorldModelState(**state_data)
        action = PlanAction(**action_data)
    except Exception as exc:
        return _err(f"Invalid state/action: {exc}", 400)

    simulator_env = TravelWorldSimulator(_config.world)
    world_model = TravelWorldModel(_config.model, simulator_env, app_config=_config)
    persistence = ModelPersistence(payload.get("output_dir"))
    if not persistence.exists():
        return _err("No trained model found. Run /train first.", 404)
    try:
        load_trained_model(world_model, payload.get("output_dir"))
    except Exception as exc:
        return _err(str(exc), 500)

    success_prob, reward, uncertainty = world_model._predict_success_and_reward(state, action)
    return _ok({
        "state": state.to_dict(),
        "action": action.to_dict(),
        "predicted_success_probability": success_prob,
        "predicted_reward": reward,
        "uncertainty": uncertainty,
    })


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


@app.route("/api/v1/model/detect_change", methods=["POST"])
def detect_change() -> tuple:
    from models import PlanAction
    from world_model import TravelWorldModel
    from travel_world import TravelWorldSimulator

    payload = flask_request.get_json(silent=True) or {}
    try:
        action = PlanAction(**payload.get("action", {}))
        predicted_success_prob = float(payload.get("predicted_success_prob", 0.95))
        predicted_cost = float(payload.get("predicted_cost", 0.0))
        actual_success = bool(payload.get("actual_success", True))
        actual_cost = float(payload.get("actual_cost", 0.0))
        observed_delay = float(payload.get("observed_delay", 0.0))
    except (TypeError, ValueError) as exc:
        return _err(f"Invalid payload: {exc}", 400)

    wm = TravelWorldModel(_config.model, TravelWorldSimulator(_config.world), app_config=_config)
    event = wm.detect_change(action, predicted_success_prob, actual_success, predicted_cost, actual_cost, observed_delay)
    return _ok({"change_event": event.to_dict() if event else None})


@app.route("/api/v1/model/recover", methods=["POST"])
def recover() -> tuple:
    from planner import PlanGenerator
    from models import PlanAction, TravelPlanRequest, WorldModelState
    from world_model import TravelWorldModel
    from travel_world import TravelWorldSimulator
    from resilience import ResilienceEngine

    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TravelPlanRequest.from_dict(payload.get("request") or payload)
        failed_action_data = payload.get("failed_action")
        failed_action = PlanAction(**failed_action_data) if failed_action_data else None
        initial_state_data = payload.get("initial_state", {
            "request_id": request.request_id,
            "remaining_budget": request.budget,
            "currency": request.currency,
            "preferences": request.preferences,
            "constraints": request.constraints,
        })
        initial_state = WorldModelState(**initial_state_data)
    except Exception as exc:
        return _err(f"Invalid payload: {exc}", 400)

    simulator = TravelWorldSimulator(_config.world)
    world_model = TravelWorldModel(_config.model, simulator, app_config=_config)
    planner = PlanGenerator(simulator, _config.model)
    engine = ResilienceEngine(world_model, planner, _config)
    backups, meta = engine.generate_backup_plans(request, initial_state, failed_action=failed_action)
    return _ok({
        "backups": [[a.to_dict() for a in plan] for plan in backups],
        "meta": meta,
    })


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
    port = int(os.getenv("UC266_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
