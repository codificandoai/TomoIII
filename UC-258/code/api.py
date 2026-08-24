"""API REST Flask del meta-framework de agentes adaptativos UC-258.

Endpoints:
  GET  /health
  GET  /api/v1/schema
  POST /api/v1/agent/run            -> ejecuta agente en cualquier entorno
  POST /api/v1/chess/move           -> ajedrez determinista
  POST /api/v1/travel/plan          -> planificación de viajes Komerzio
  POST /api/v1/stock/trade          -> operación bursátil secuencial
  GET  /api/v1/agent/last_trace     -> última traza ejecutada
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from agent.adaptive_agent import AdaptiveAgent
from config import CONFIG
from environments.chess_env import ChessboardEnvironment
from environments.stock_env import StockMarketEnvironment
from environments.travel_env import TravelEnvironment
from models import StepResult, TravelRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc258-api")

app = Flask(__name__)

_agent = AdaptiveAgent(config=CONFIG.agent)
_last_trace: Optional[Dict[str, Any]] = None


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


# ─────────────────────────────────────────────────────────────────────────────
# Card views
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/run",
        "description": "Ejecuta el agente adaptativo en un entorno registrado.",
        "parameters": [
            {"name": "environment", "type": "string", "required": True, "enum": ["chess", "travel", "stock"], "example": "travel"},
            {"name": "objective", "type": "object", "required": True, "example": {"origin": "Madrid", "destination": "París", "departure_date": "2026-07-15", "return_date": "2026-07-18", "budget": 1200}},
            {"name": "max_iterations", "type": "integer", "required": False, "example": 20},
        ],
    },
    {
        "endpoint": "POST /api/v1/chess/move",
        "description": "Ejecuta un movimiento en el tablero de ajedrez.",
        "parameters": [
            {"name": "move", "type": "string", "required": True, "example": "Qd8"},
            {"name": "fen", "type": "string", "required": False, "example": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"},
        ],
    },
    {
        "endpoint": "POST /api/v1/travel/plan",
        "description": "Planifica un itinerario para Komerzio.com usando datos externos simulados.",
        "parameters": [
            {"name": "origin", "type": "string", "required": True, "example": "Madrid"},
            {"name": "destination", "type": "string", "required": True, "example": "París"},
            {"name": "departure_date", "type": "string", "required": True, "example": "2026-07-15"},
            {"name": "return_date", "type": "string", "required": False, "example": "2026-07-18"},
            {"name": "travelers", "type": "integer", "required": False, "example": 2},
            {"name": "budget", "type": "number", "required": False, "example": 1200},
            {"name": "currency", "type": "string", "required": False, "example": "EUR"},
            {"name": "preferences", "type": "object", "required": False, "example": {"direct_flight": True}},
            {"name": "constraints", "type": "list[string]", "required": False, "example": ["no layovers > 3h"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/stock/trade",
        "description": "Ejecuta una estrategia bursátil secuencial.",
        "parameters": [
            {"name": "steps", "type": "integer", "required": False, "example": 5},
            {"name": "seed", "type": "integer", "required": False, "example": 42},
            {"name": "action", "type": "string", "required": False, "enum": ["hold", "buy_small", "buy_large", "sell_small", "sell_large"]},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/agent/run",
        "description": "Traza completa de la ejecución adaptativa.",
        "fields": [
            {"name": "trace_id", "type": "string"},
            {"name": "environment_kind", "type": "string"},
            {"name": "properties", "type": "object"},
            {"name": "selected_strategy", "type": "string"},
            {"name": "plan", "type": "object"},
            {"name": "actions", "type": "list[object]"},
            {"name": "final_observation", "type": "object"},
            {"name": "reward", "type": "number"},
            {"name": "iterations", "type": "integer"},
            {"name": "errors", "type": "list[string]"},
            {"name": "safety_flags", "type": "list[string]"},
            {"name": "latency_ms", "type": "number"},
        ],
    },
    {
        "endpoint": "POST /api/v1/chess/move",
        "description": "Resultado del movimiento: recompensa y estado del tablero.",
        "fields": [
            {"name": "move", "type": "string"},
            {"name": "reward", "type": "number"},
            {"name": "done", "type": "boolean"},
            {"name": "observation", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/travel/plan",
        "description": "Itinerario explicable con costes, fuentes, confianza y alternativas.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "items", "type": "list[object]"},
            {"name": "total_cost", "type": "number"},
            {"name": "currency", "type": "string"},
            {"name": "confidence", "type": "number"},
            {"name": "assumptions", "type": "list[string]"},
            {"name": "alternatives", "type": "list[string]"},
            {"name": "missing_info", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/stock/trade",
        "description": "Observación final del mercado, cartera y PnL.",
        "fields": [
            {"name": "observation", "type": "object"},
            {"name": "pnl", "type": "number"},
            {"name": "history", "type": "list[number]"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc258-adaptive-agent", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


def _build_travel_request(payload: Dict[str, Any]) -> TravelRequest:
    return TravelRequest(
        origin=payload["origin"],
        destination=payload["destination"],
        departure_date=payload["departure_date"],
        return_date=payload.get("return_date"),
        travelers=int(payload.get("travelers", 1)),
        budget=payload.get("budget"),
        currency=payload.get("currency", "USD"),
        preferences=payload.get("preferences", {}),
        constraints=payload.get("constraints", []),
    )


@app.route("/api/v1/agent/run", methods=["POST"])
def agent_run():
    payload = request.get_json(silent=True) or {}
    env_name = payload.get("environment")
    objective = payload.get("objective", {})
    max_iterations = payload.get("max_iterations")

    if not env_name:
        return _err("environment es requerido", 400)

    env = None
    obj = objective
    if env_name == "chess":
        env = ChessboardEnvironment()
        obj = objective.get("goal", "find_checkmate")
    elif env_name == "travel":
        req = _build_travel_request(objective)
        env = TravelEnvironment(request=req)
        obj = req
    elif env_name == "stock":
        env = StockMarketEnvironment()
        obj = objective.get("goal", "maximize_return")
    else:
        return _err("environment no soportado", 400)

    trace = _agent.run(env, obj, max_iterations=max_iterations)
    global _last_trace
    _last_trace = trace.to_dict()
    return _ok(trace.to_dict())


@app.route("/api/v1/chess/move", methods=["POST"])
def chess_move():
    payload = request.get_json(silent=True) or {}
    move = payload.get("move")
    fen = payload.get("fen")
    if not move:
        return _err("move es requerido", 400)
    env = ChessboardEnvironment(fen=fen)
    result = env.step(move)
    return _ok({"move": move, **result.to_dict()})


@app.route("/api/v1/travel/plan", methods=["POST"])
def travel_plan():
    payload = request.get_json(silent=True) or {}
    try:
        req = _build_travel_request(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"TravelRequest inválido: {exc}", 400)

    env = TravelEnvironment(request=req)
    trace = _agent.run(env, req, max_iterations=20)
    global _last_trace
    _last_trace = trace.to_dict()

    itinerary = env.itinerary.to_dict()
    return _ok({"trace": trace.to_dict(), "itinerary": itinerary})


@app.route("/api/v1/stock/trade", methods=["POST"])
def stock_trade():
    payload = request.get_json(silent=True) or {}
    steps = int(payload.get("steps", 5))
    seed = int(payload.get("seed", 42))
    action = payload.get("action")

    env = StockMarketEnvironment(seed=seed)
    pnl_history = []
    for _ in range(steps):
        if action:
            result = env.step(action)
        else:
            # Estrategia por defecto del agente adaptativo
            trace = _agent.run(env, "maximize_return", max_iterations=1)
            result_step = trace.actions[0]["result"] if trace.actions else None
            result = StepResult(
                observation=env.get_observation(),
                reward=result_step["reward"] if result_step else 0.0,
                done=False,
                info=result_step["info"] if result_step else {},
            )
        pnl_history.append(result.info.get("pnl", 0.0))

    final_obs = env.get_observation().to_dict()
    return _ok({"observation": final_obs, "pnl": pnl_history[-1], "history": pnl_history})


@app.route("/api/v1/agent/last_trace", methods=["GET"])
def last_trace():
    if _last_trace is None:
        return _err("No hay traza previa", 404)
    return _ok(_last_trace)


@app.errorhandler(404)
def not_found(_e):
    return _err("Recurso no encontrado", 404)


@app.errorhandler(405)
def method_not_allowed(_e):
    return _err("Método no permitido", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC258_PORT", CONFIG.port))
    app.run(host="0.0.0.0", port=port, debug=False)
