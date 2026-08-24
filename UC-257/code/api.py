"""API REST Flask para el sistema de agentes de viajes UC-257.

Endpoints:
  GET  /health
  GET  /api/v1/schema                 -> card views de entrada/salida
  POST /api/v1/assistant/chat         -> asistente dependiente (Semantic Kernel / fallback)
  POST /api/v1/agent/plan             -> plan inicial autónomo
  POST /api/v1/agent/run              -> ejecución autónoma completa
  POST /api/v1/agent/simulate         -> simula evento externo (cancelación)
  GET  /api/v1/agent/status/<rid>     -> estado de un viaje
  GET  /api/v1/inventory/flights      -> buscar vuelos
  GET  /api/v1/inventory/hotels       -> buscar hoteles
  GET  /api/v1/inventory/activities   -> buscar actividades
  GET  /api/v1/bookings               -> listar reservas
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from agent_orchestrator import TravelAgentOrchestrator
from autogen_adapter import AutoGenAdapter
from config import CONFIG, AppConfig
from models import TripRequest
from semantic_kernel_adapter import SemanticKernelAdapter
from travel_services import BookingManager, TravelInventory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc257-api")

app = Flask(__name__)

# Componentes globales
_inventory = TravelInventory()
_bookings = BookingManager(_inventory)
_orchestrator = TravelAgentOrchestrator(_inventory, _bookings, CONFIG.agent)
_sk_adapter = SemanticKernelAdapter(CONFIG, _orchestrator)
_autogen_adapter = AutoGenAdapter(CONFIG, _orchestrator)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _ok(data: Any, status: int = 200):
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }), status


def _err(message: str, status: int = 400):
    return jsonify({"status": "error", "message": message}), status


def _build_trip_request(payload: Dict[str, Any]) -> TripRequest:
    return TripRequest(
        origin=payload["origin"],
        destination=payload["destination"],
        departure_date=payload["departure_date"],
        return_date=payload.get("return_date"),
        travelers=int(payload.get("travelers", 1)),
        budget=payload.get("budget"),
        preferences=payload.get("preferences", {}),
        meeting_ids=payload.get("meeting_ids", []),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Card views de esquema de API (entrada / salida)
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/assistant/chat",
        "description": "Asistente reactivo dependiente: un mensaje del usuario produce una única acción.",
        "parameters": [
            {"name": "user_id", "type": "string", "required": True, "example": "user-42"},
            {"name": "message", "type": "string", "required": True, "example": "Busca vuelos de Madrid a París para mañana"},
            {"name": "trip_request", "type": "object", "required": False,
             "example": {"origin": "Madrid", "destination": "París", "departure_date": "2026-07-15"}},
        ],
    },
    {
        "endpoint": "POST /api/v1/agent/run",
        "description": "Agente autónomo: planifica, reserva, monitoriza y recupera el viaje sin intervención humana.",
        "parameters": [
            {"name": "origin", "type": "string", "required": True, "example": "Madrid"},
            {"name": "destination", "type": "string", "required": True, "example": "París"},
            {"name": "departure_date", "type": "string", "required": True, "example": "2026-07-15"},
            {"name": "return_date", "type": "string", "required": False, "example": "2026-07-18"},
            {"name": "travelers", "type": "integer", "required": False, "example": 1},
            {"name": "budget", "type": "number", "required": False, "example": 500.0},
            {"name": "meeting_ids", "type": "list[string]", "required": False, "example": ["meet-15"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/agent/simulate",
        "description": "Simula un evento externo (cancelación de vuelo) y dispara la recuperación autónoma.",
        "parameters": [
            {"name": "request_id", "type": "string", "required": True},
            {"name": "event_type", "type": "string", "required": True, "enum": ["flight_cancelled"]},
            {"name": "payload", "type": "object", "required": True, "example": {"flight_id": "IB1001"}},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/assistant/chat",
        "description": "Resultado de la acción reactiva y estado parcial.",
        "fields": [
            {"name": "mode", "type": "string"},
            {"name": "user_message", "type": "string"},
            {"name": "intent", "type": "object"},
            {"name": "action", "type": "object"},
            {"name": "state", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/agent/run",
        "description": "Plan final, estado, resumen y notificaciones del agente autónomo.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "final_state", "type": "object"},
            {"name": "plan", "type": "object"},
            {"name": "summary", "type": "string"},
            {"name": "notifications", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "GET /api/v1/inventory/flights",
        "description": "Lista de vuelos disponibles.",
        "fields": [
            {"name": "flights", "type": "list[object]", "note": "flight_id, origin, destination, departure_time, price, status"},
        ],
    },
    {
        "endpoint": "GET /api/v1/bookings",
        "description": "Reservas activas.",
        "fields": [
            {"name": "bookings", "type": "list[object]", "note": "booking_id, service_type, reference_id, status"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc257-travel-agents", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/assistant/chat", methods=["POST"])
def assistant_chat():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    message = payload.get("message")
    if not user_id or not message:
        return _err("user_id y message son requeridos", 400)

    trip_payload = payload.get("trip_request")
    state = None
    if trip_payload:
        req = _build_trip_request(trip_payload)
        from models import TravelState
        state = TravelState(req)

    result = _sk_adapter.chat(user_id, message, state)
    return _ok(result)


@app.route("/api/v1/agent/plan", methods=["POST"])
def agent_plan():
    payload = request.get_json(silent=True) or {}
    try:
        req = _build_trip_request(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"TripRequest inválido: {exc}", 400)
    plan = _orchestrator.planner.create_plan(req)
    return _ok(plan.to_dict())


@app.route("/api/v1/agent/run", methods=["POST"])
def agent_run():
    payload = request.get_json(silent=True) or {}
    try:
        req = _build_trip_request(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"TripRequest inválido: {exc}", 400)
    result = _autogen_adapter.run(req)
    return _ok(result.to_dict())


@app.route("/api/v1/agent/simulate", methods=["POST"])
def agent_simulate():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    event_type = payload.get("event_type")
    event_payload = payload.get("payload", {})
    if not request_id or not event_type:
        return _err("request_id y event_type son requeridos", 400)

    state = _orchestrator._states.get(request_id)
    if state is None:
        return _err("request_id no encontrado", 404)

    if event_type == "flight_cancelled":
        flight_id = event_payload.get("flight_id")
        flight = state.selected_flight
        if flight and flight.flight_id == flight_id:
            flight.status = "cancelled"
            # Ejecutar recuperación
            plan = _orchestrator.planner.create_plan(state.request)
            plan.actions = []
            recovery = _orchestrator.planner.handle_disruption(plan, flight)
            for action in recovery:
                _orchestrator._execute_action(action, state)
            state.log.extend(recovery)
            summary = _orchestrator._build_summary(state)
            return _ok({
                "request_id": request_id,
                "event": event_type,
                "state": state.to_dict(),
                "summary": summary,
                "notifications": state.notifications,
            })
        return _err("El vuelo no coincide con la reserva actual", 409)

    return _err("event_type no soportado", 400)


@app.route("/api/v1/agent/status/<request_id>", methods=["GET"])
def agent_status(request_id: str):
    state = _orchestrator._states.get(request_id)
    if state is None:
        return _err("request_id no encontrado", 404)
    return _ok(state.to_dict())


@app.route("/api/v1/inventory/flights", methods=["GET"])
def search_flights():
    origin = request.args.get("origin")
    destination = request.args.get("destination")
    date = request.args.get("date")
    if not (origin and destination and date):
        return _err("origin, destination y date son requeridos", 400)
    flights = _inventory.search_flights(origin, destination, date)
    return _ok([f.to_dict() for f in flights])


@app.route("/api/v1/inventory/hotels", methods=["GET"])
def search_hotels():
    destination = request.args.get("destination")
    check_in = request.args.get("check_in")
    check_out = request.args.get("check_out")
    if not (destination and check_in):
        return _err("destination y check_in son requeridos", 400)
    hotels = _inventory.search_hotels(destination, check_in, check_out)
    return _ok([h.to_dict() for h in hotels])


@app.route("/api/v1/inventory/activities", methods=["GET"])
def search_activities():
    destination = request.args.get("destination")
    date = request.args.get("date")
    category = request.args.get("category")
    if not (destination and date):
        return _err("destination y date son requeridos", 400)
    activities = _inventory.search_activities(destination, date, category)
    return _ok([a.to_dict() for a in activities])


@app.route("/api/v1/bookings", methods=["GET"])
def list_bookings():
    return _ok([b.to_dict() for b in _bookings.list_bookings()])


@app.errorhandler(404)
def not_found(_e):
    return _err("Recurso no encontrado", 404)


@app.errorhandler(405)
def method_not_allowed(_e):
    return _err("Método no permitido", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC257_PORT", CONFIG.port))
    app.run(host="0.0.0.0", port=port, debug=False)
