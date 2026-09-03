"""API REST Flask para UC-292 - Sistema Multi-Agente de Trading."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template_string, request as flask_request

from central_brain import CentralBrain
from config import get_config
from exchange import ExchangeSimulator
from graph import build_agent, run_agent
from juice_agents import JuiceValidator
from market_data import SyntheticMarketDataGenerator
from models import (
    MarketTick,
    NewsItem,
    Portfolio,
    RiskConstraints,
    TradingRequest,
)
from mcp_server import build_trading_mcp_server
from perception import MarketPerceptionPipeline
from react_tot import ReActReasonactToTBrain, TickPredictionEnvironment
from risk import RiskEngine
from trading_agents import PerceptionAgent, SentimentAnalyst, TechnicalAnalyst
from world_model import TradingWorldModel

app = Flask(__name__)

_config = get_config()
_perception = MarketPerceptionPipeline(_config.market, _config.features)
_world_model = TradingWorldModel(_config.model, app_config=_config)
_brain = CentralBrain(
    _config,
    world_model=_world_model,
    perception_pipeline=_perception,
)
_exchange = ExchangeSimulator()
_risk_engine = RiskEngine(_config.risk)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
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


def _ticks_from_json(raw: List[Dict[str, Any]]) -> List[MarketTick]:
    return [MarketTick(**item) for item in raw]


def _news_from_json(raw: List[Dict[str, Any]]) -> List[NewsItem]:
    return [NewsItem(**item) for item in raw]


# ─────────────────────────────────────────────────────────────────────────────
# Card views de esquema de API (entrada / salida)
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/market/perceive",
        "description": "Procesa ticks y noticias y devuelve snapshots estructurados del mercado.",
        "parameters": [
            {"name": "symbol", "type": "string", "required": True, "example": "AAPL"},
            {"name": "ticks", "type": "list[object]", "required": True, "example": [{"timestamp": "2026-07-09T06:25:00.123Z", "symbol": "AAPL", "bid": 234.56, "ask": 234.58, "last_price": 234.57, "volume": 45238921}]},
            {"name": "news", "type": "list[object]", "required": False, "example": [{"text": "AAPL partnership", "source": "bloomberg"}]},
        ],
    },
    {
        "endpoint": "POST /api/v1/market/analyze",
        "description": "Genera señales técnicas y de sentimiento a partir de un snapshot.",
        "parameters": [
            {"name": "symbol", "type": "string", "required": True},
            {"name": "ticks", "type": "list[object]", "required": True},
            {"name": "news", "type": "list[object]", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/plan",
        "description": "Ejecuta el ciclo completo de percepción-análisis-validación-planificación (paper).",
        "parameters": [
            {"name": "symbols", "type": "list[string]", "required": True, "example": ["AAPL"]},
            {"name": "ticks", "type": "list[object]", "required": True},
            {"name": "news", "type": "list[object]", "required": False},
            {"name": "portfolio", "type": "object", "required": False, "example": {"cash": 100000, "positions": {}}},
            {"name": "constraints", "type": "object", "required": False},
            {"name": "risk_tolerance", "type": "string", "required": False, "enum": ["conservative", "moderate", "aggressive"]},
            {"name": "mode", "type": "string", "required": False, "enum": ["paper", "live", "sim"]},
            {"name": "approved", "type": "boolean", "required": False, "default": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/execute",
        "description": "Ejecuta el plan seleccionado aprobando explícitamente (paper/live).",
        "parameters": [
            {"name": "request", "type": "object", "required": True, "description": "Mismo payload que /trading/plan con approved=true"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/train",
        "description": "Entrena el world model con datos sintéticos de mercado.",
        "parameters": [
            {"name": "samples", "type": "integer", "required": False, "default": 500},
            {"name": "output_dir", "type": "string", "required": False, "default": "models"},
        ],
    },
    {
        "endpoint": "POST /api/v1/bdi/state",
        "description": "Construye y devuelve el estado BDI (Beliefs, Desires, Intention) para un request.",
        "parameters": [
            {"name": "request", "type": "object", "required": True},
            {"name": "selected_strategy", "type": "object", "required": False},
            {"name": "signals", "type": "list[object]", "required": False},
            {"name": "evaluations", "type": "list[object]", "required": False},
            {"name": "snapshots", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/bdi/confront",
        "description": "Confronta una intención BDI contra beliefs/desires y devuelve el veredicto Juice.",
        "parameters": [
            {"name": "beliefs", "type": "object", "required": True},
            {"name": "desires", "type": "object", "required": True},
            {"name": "intention", "type": "object", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/plan_with_bdi",
        "description": "Pipeline completo de trading: percepción -> BDI -> Juice -> riesgo -> ejecución.",
        "parameters": [
            {"name": "request", "type": "object", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/sam/workspace",
        "description": "Construye el workspace global SAM (percepción, self-model, memoria, hipótesis).",
        "parameters": [
            {"name": "request", "type": "object", "required": True},
            {"name": "snapshots", "type": "object", "required": False},
            {"name": "signals", "type": "list[object]", "required": False},
            {"name": "hypotheses", "type": "list[object]", "required": False},
            {"name": "alerts", "type": "list[string]", "required": False},
            {"name": "agent_identity", "type": "string", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/plan_with_sam",
        "description": "Pipeline completo SAM -> BDI -> Juice -> World Model -> Ejecución.",
        "parameters": [
            {"name": "request", "type": "object", "required": True},
        ],
    },
    {
        "endpoint": "GET /api/v1/mcp/tools",
        "description": "Descubrimiento de herramientas MCP registradas.",
        "parameters": [],
    },
    {
        "endpoint": "POST /api/v1/mcp/call",
        "description": "Invoca una herramienta MCP dinámica.",
        "parameters": [
            {"name": "tool", "type": "string", "required": True},
            {"name": "arguments", "type": "object", "required": True},
            {"name": "approved", "type": "boolean", "required": False, "default": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/tot/predict",
        "description": "Predice ask/bid del siguiente tick con ReAct Híbrido + Tree of Thoughts (ToT).",
        "parameters": [
            {"name": "symbol", "type": "string", "required": True, "example": "AAPL"},
            {"name": "ticks", "type": "list[object]", "required": True, "example": [{"timestamp": "2026-07-09T06:25:00.123Z", "symbol": "AAPL", "bid": 234.56, "ask": 234.58, "last_price": 234.57, "volume": 45238921, "bid_size": 1000, "ask_size": 1200}]},
            {"name": "news", "type": "list[object]", "required": False, "example": [{"text": "AAPL strong earnings", "source": "bloomberg"}]},
            {"name": "predictors", "type": "list[string]", "required": False, "default": ["world_model", "technical", "microstructure"], "enum": ["brain", "world_model", "technical", "microstructure", "sentiment", "ensemble"]},
            {"name": "use_brain", "type": "boolean", "required": False, "default": False, "description": "Incluye CentralBrain.predict_next_price como predictor real."},
            {"name": "confidence_threshold", "type": "number", "required": False, "default": 0.5, "description": "Mínima confianza para aceptar una hoja; debajo se poda."},
            {"name": "max_depth", "type": "integer", "required": False, "default": 2, "description": "Profundidad máxima de retroceso/backtracking."},
            {"name": "simulate_failures", "type": "list[string]", "required": False, "example": ["technical"], "description": "Fuerza TIMEOUT en estas fuentes para demostrar poda y backtracking."},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/market/perceive",
        "description": "Snapshot de mercado con features técnicos y régimen.",
        "fields": [
            {"name": "symbol", "type": "string"},
            {"name": "latest_price", "type": "number"},
            {"name": "features", "type": "object", "note": "rsi, macd, atr, bollinger_position, obv, volatility, trend_direction"},
            {"name": "news_sentiment", "type": "number"},
            {"name": "regime", "type": "string"},
        ],
    },
    {
        "endpoint": "POST /api/v1/market/analyze",
        "description": "Señales de los agentes analistas.",
        "fields": [
            {"name": "snapshot", "type": "object"},
            {"name": "technical", "type": "object", "note": "side, confidence, entry_price, stop_loss, take_profit"},
            {"name": "sentiment", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/plan",
        "description": "Resultado del ciclo agente-entorno: estrategias, evaluaciones y decisión.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "status", "type": "string", "enum": ["done", "awaiting_confirmation", "blocked", "failed"]},
            {"name": "snapshots", "type": "object"},
            {"name": "signals", "type": "list[object]"},
            {"name": "juice_validations", "type": "list[object]"},
            {"name": "selected_strategy", "type": "object"},
            {"name": "candidates", "type": "list[object]"},
            {"name": "evaluations", "type": "list[object]"},
            {"name": "risk_decision", "type": "object"},
            {"name": "safety_decision", "type": "object", "note": "SafetySupervisor verdict"},
            {"name": "tot_prediction", "type": "object", "note": "ToT ask/bid prediction by symbol"},
            {"name": "execution_result", "type": "object"},
            {"name": "portfolio", "type": "object"},
            {"name": "reflections", "type": "list[object]"},
            {"name": "requires_confirmation", "type": "boolean"},
        ],
    },
    {
        "endpoint": "POST /api/v1/model/train",
        "description": "Estadísticas del entrenamiento y rutas guardadas.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "metadata.n_samples", "type": "integer"},
            {"name": "metadata.n_transitions", "type": "integer"},
            {"name": "metadata.model_type", "type": "string"},
            {"name": "saved_paths", "type": "object"},
        ],
    },
    {
        "endpoint": "GET /api/v1/mcp/tools",
        "description": "Lista de herramientas MCP disponibles.",
        "fields": [
            {"name": "tools", "type": "list[object]", "note": "name, description, inputSchema, risk"},
        ],
    },
    {
        "endpoint": "POST /api/v1/mcp/call",
        "description": "Resultado de invocar una herramienta MCP.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "tool", "type": "string"},
            {"name": "content", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/bdi/state",
        "description": "Estado BDI serializable: beliefs, desires, intención y traza CoT.",
        "fields": [
            {"name": "bdi_state_id", "type": "string"},
            {"name": "beliefs", "type": "object"},
            {"name": "desires", "type": "object"},
            {"name": "draft_intention", "type": "object"},
            {"name": "committed_intention", "type": "object"},
            {"name": "cot_trace", "type": "list[object]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/bdi/confront",
        "description": "Veredicto del filtro adversarial Juice sobre una intención BDI.",
        "fields": [
            {"name": "verdict.approved", "type": "boolean"},
            {"name": "verdict.survival_score", "type": "number"},
            {"name": "verdict.issues", "type": "list[string]"},
            {"name": "verdict.corrected_intention", "type": "object"},
            {"name": "bdi_state", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/plan_with_bdi",
        "description": "Resultado completo del pipeline de trading BDI + Juice.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "snapshots", "type": "object"},
            {"name": "signals", "type": "list[object]"},
            {"name": "juice_validations", "type": "list[object]"},
            {"name": "bdi_state", "type": "object"},
            {"name": "juice_verdict", "type": "object"},
            {"name": "selected_strategy", "type": "object"},
            {"name": "risk_decision", "type": "object"},
            {"name": "safety_decision", "type": "object", "note": "SafetySupervisor verdict"},
            {"name": "tot_prediction", "type": "object", "note": "ToT ask/bid prediction by symbol"},
            {"name": "requires_confirmation", "type": "boolean"},
        ],
    },
    {
        "endpoint": "POST /api/v1/sam/workspace",
        "description": "Estado SAM completo: self-model, memoria, workspace, metacognición, seguridad.",
        "fields": [
            {"name": "sam_state_id", "type": "string"},
            {"name": "self_model", "type": "object"},
            {"name": "working_memory", "type": "list[object]"},
            {"name": "environment", "type": "object"},
            {"name": "workspace", "type": "object"},
            {"name": "metacognition", "type": "object"},
            {"name": "safety_decision", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/trading/plan_with_sam",
        "description": "Resultado completo del pipeline SAM + BDI + Juice con sam_state anexado.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "sam_state", "type": "object"},
            {"name": "bdi_state", "type": "object"},
            {"name": "juice_verdict", "type": "object"},
            {"name": "selected_strategy", "type": "object"},
            {"name": "risk_decision", "type": "object"},
            {"name": "safety_decision", "type": "object", "note": "SafetySupervisor verdict"},
            {"name": "tot_prediction", "type": "object", "note": "ToT ask/bid prediction by symbol"},
            {"name": "requires_confirmation", "type": "boolean"},
        ],
    },
    {
        "endpoint": "POST /api/v1/tot/predict",
        "description": "Predicción ask/bid del siguiente tick con árbol de pensamientos ToT.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "symbol", "type": "string"},
            {"name": "request_id", "type": "string"},
            {"name": "final_prediction", "type": "object", "note": "predicted_ask, predicted_bid, predicted_mid, spread, confidence, source_strategy"},
            {"name": "selected_leaf", "type": "object"},
            {"name": "consensus", "type": "object"},
            {"name": "tree_summary", "type": "object", "note": "total_nodes, success_leaves, pruned_leaves, backtracked_nodes"},
            {"name": "leaves", "type": "list[object]"},
            {"name": "tree", "type": "object"},
            {"name": "trace", "type": "list[object]"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc293-bdi-juice-trading", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/market/perceive", methods=["POST"])
def market_perceive() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    ticks_raw = payload.get("ticks", [])
    news_raw = payload.get("news", [])
    symbol = payload.get("symbol") or (ticks_raw[0].get("symbol") if ticks_raw else "AAPL")
    if not ticks_raw:
        return _err("ticks are required", 400)
    ticks = _ticks_from_json(ticks_raw)
    news = _news_from_json(news_raw)
    snapshots = _perception.perceive(
        request_id="api-perceive",
        ticks_by_symbol={symbol: ticks},
        news=news,
    )
    return _ok({symbol: snapshots[symbol].to_dict()})


@app.route("/api/v1/market/analyze", methods=["POST"])
def market_analyze() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    ticks_raw = payload.get("ticks", [])
    news_raw = payload.get("news", [])
    symbol = payload.get("symbol") or (ticks_raw[0].get("symbol") if ticks_raw else "AAPL")
    if not ticks_raw:
        return _err("ticks are required", 400)
    request = TradingRequest(
        symbols=[symbol],
        ticks=_ticks_from_json(ticks_raw),
        news=_news_from_json(news_raw),
    )
    agent = PerceptionAgent(_perception)
    snapshots = agent.perceive(request)
    snap = snapshots[symbol]
    t = TechnicalAnalyst().analyze(snap)
    s = SentimentAnalyst().analyze(snap)
    return _ok({
        "snapshot": snap.to_dict(),
        "technical": t.to_dict(),
        "sentiment": s.to_dict(),
    })


@app.route("/api/v1/trading/plan", methods=["POST"])
def trading_plan() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        final_state = run_agent(request, _config, recursion_limit=50)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(final_state.get("final_output", {}))


@app.route("/api/v1/trading/execute", methods=["POST"])
def trading_execute() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    req_data = payload.get("request") or payload
    req_data["approved"] = True
    try:
        request = TradingRequest.from_dict(req_data)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        final_state = run_agent(request, _config, recursion_limit=50)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(final_state.get("final_output", {}))


@app.route("/api/v1/model/train", methods=["POST"])
def train() -> tuple:
    from train import train_world_model

    payload = flask_request.get_json(silent=True) or {}
    samples = int(payload.get("samples", 500))
    output_dir = payload.get("output_dir")
    try:
        result = train_world_model(n_samples=samples, config=_config, output_dir=output_dir)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(result)


@app.route("/api/v1/model/world_model", methods=["GET"])
def world_model_state() -> tuple:
    return _ok(_world_model.to_dict())


@app.route("/api/v1/model/predict_next_tick", methods=["POST"])
def predict_next_tick() -> tuple:
    """Predice el siguiente tick price y permite entrenar con ticks previos."""
    payload = flask_request.get_json(silent=True) or {}
    symbol = payload.get("symbol", "AAPL")
    current_price = payload.get("current_price")
    train = bool(payload.get("train", False))
    ticks_raw = payload.get("ticks", [])

    if current_price is None and ticks_raw:
        try:
            current_price = _ticks_from_json(ticks_raw)[-1].last_price
        except Exception:
            return _err("current_price or valid ticks required", 400)

    if current_price is None:
        return _err("current_price is required", 400)

    try:
        if train and len(ticks_raw) >= 2:
            ticks = _ticks_from_json(ticks_raw)
            for i in range(len(ticks) - 1):
                _world_model.update_from_tick(
                    symbol=symbol,
                    current_price=ticks[i].last_price,
                    next_price=ticks[i + 1].last_price,
                )
        result = _world_model.predict_next_price(symbol, float(current_price))
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(result)


@app.route("/api/v1/brain/state", methods=["GET"])
def brain_state() -> tuple:
    """Estado completo del cerebro central (snapshots, beliefs, predicciones, world model)."""
    return _ok(_brain.to_dict())


@app.route("/api/v1/brain/observe", methods=["POST"])
def brain_observe() -> tuple:
    """Alimenta el cerebro central con ticks y noticias, actualizando snapshots y creencias."""
    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    snapshots = _brain.observe(request)
    return _ok({symbol: snap.to_dict() for symbol, snap in snapshots.items()})


@app.route("/api/v1/brain/query", methods=["POST"])
def brain_query() -> tuple:
    """Consulta el cerebro central por contexto de un símbolo (snapshot, belief, predicción, riesgo)."""
    payload = flask_request.get_json(silent=True) or {}
    symbol = payload.get("symbol")
    if not symbol:
        return _err("symbol is required", 400)
    if symbol not in _brain.snapshots:
        return _err(f"symbol {symbol} not observed yet", 404)
    return _ok(_brain.get_context(symbol))


@app.route("/api/v1/brain/predict_next_tick", methods=["POST"])
def brain_predict_next_tick() -> tuple:
    """Predice el siguiente tick usando el cerebro central (requiere observar primero)."""
    payload = flask_request.get_json(silent=True) or {}
    symbol = payload.get("symbol")
    if not symbol:
        return _err("symbol is required", 400)
    if symbol not in _brain.snapshots:
        return _err(f"symbol {symbol} not observed yet", 404)
    return _ok(_brain.predict_next_price(symbol))


# ─────────────────────────────────────────────────────────────────────────────
# BDI + Filtro Adversarial Juice (UC-293)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/v1/bdi/state", methods=["POST"])
def bdi_state() -> tuple:
    """Construye y expone el estado BDI (Beliefs, Desires, Intention) para un request."""
    from agent_core import build_bdi_from_request

    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        state = build_bdi_from_request(
            request,
            selected_strategy=payload.get("selected_strategy"),
            signals=payload.get("signals", []),
            evaluations=payload.get("evaluations", []),
            snapshots=payload.get("snapshots"),
        )
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(state.to_dict())


@app.route("/api/v1/bdi/confront", methods=["POST"])
def bdi_confront() -> tuple:
    """Confronta una intención BDI contra beliefs/desires y devuelve el veredicto Juice."""
    from adversarial_juice import ConfrontationalJuice
    from bdi import BDIStateBuilder
    from models import BDIBeliefs, BDIDesires, BDIIntention

    payload = flask_request.get_json(silent=True) or {}
    try:
        beliefs = BDIBeliefs(**payload.get("beliefs", {}))
        desires = BDIDesires(**payload.get("desires", {}))
        intention = BDIIntention(**payload.get("intention", {}))
    except Exception as exc:
        return _err(f"Invalid BDI payload: {exc}", 400)

    juice = ConfrontationalJuice()
    verdict = juice.confront(beliefs, desires, intention)
    return _ok(
        {
            "verdict": verdict.to_dict(),
            "bdi_state": BDIStateBuilder.build(
                beliefs=beliefs,
                desires=desires,
                draft=intention,
                verdict=verdict,
            ).to_dict(),
        }
    )


@app.route("/api/v1/trading/plan_with_bdi", methods=["POST"])
def plan_with_bdi() -> tuple:
    """Pipeline completo de trading: percepción -> BDI -> Juice -> riesgo -> ejecución."""
    from agent_core import run_bdi_trading_pipeline

    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        output = run_bdi_trading_pipeline(request, _config)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(output)


# ─────────────────────────────────────────────────────────────────────────────
# SAM — Situational Awareness Middleware (UC-294)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/v1/sam/workspace", methods=["POST"])
def sam_workspace() -> tuple:
    """Construye el workspace global SAM (percepción, self-model, memoria, hipótesis)."""
    from agent_core import build_sam_state

    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        state = build_sam_state(
            request,
            snapshots=payload.get("snapshots"),
            signals=payload.get("signals", []),
            hypotheses=payload.get("hypotheses"),
            alerts=payload.get("alerts", []),
            agent_identity=payload.get("agent_identity", "UC294.API"),
        )
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(state.to_dict())


@app.route("/api/v1/trading/plan_with_sam", methods=["POST"])
def plan_with_sam() -> tuple:
    """Pipeline completo: SAM -> BDI -> Juice -> World Model -> Ejecución."""
    from agent_core import run_sam_aware_pipeline

    payload = flask_request.get_json(silent=True) or {}
    try:
        request = TradingRequest.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid request: {exc}", 400)
    try:
        output = run_sam_aware_pipeline(request, _config)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(output)


# ─────────────────────────────────────────────────────────────────────────────
# MCP dynamic registry
# ─────────────────────────────────────────────────────────────────────────────
def _build_mcp_server():
    def perception_handler(args: dict) -> dict:
        symbol = args["symbol"]
        ticks = _ticks_from_json(args["ticks"])
        news = _news_from_json(args.get("news", []))
        snapshots = _perception.perceive("mcp", {symbol: ticks}, news)
        return snapshots[symbol].to_dict()

    def analysis_handler(args: dict) -> dict:
        symbol = args["symbol"]
        ticks = _ticks_from_json(args["ticks"])
        snapshots = _perception.perceive("mcp", {symbol: ticks}, [])
        snap = snapshots[symbol]
        return {
            "technical": TechnicalAnalyst().analyze(snap).to_dict(),
            "sentiment": SentimentAnalyst().analyze(snap).to_dict(),
        }

    def risk_handler(args: dict) -> dict:
        from models import TradingSignal
        signal = TradingSignal(**args["signal"])
        portfolio = Portfolio(**args.get("portfolio", {}))
        constraints = RiskConstraints(**args.get("constraints", {}))
        engine = RiskEngine(constraints)
        from models import MarketSnapshot
        snapshot = MarketSnapshot(**args.get("snapshot", {}))
        return engine.assess_signal(signal, snapshot, portfolio).to_dict()

    def juice_handler(args: dict) -> dict:
        from models import MarketSnapshot, TradingSignal
        validator = JuiceValidator(_config.juice)
        signal = TradingSignal(**args["signal"])
        snapshot = MarketSnapshot(**args["snapshot"])
        return validator.validate(signal, snapshot).to_dict()

    def order_handler(args: dict) -> dict:
        action_dict = args["action"]
        from models import AgentAction
        action = AgentAction(**action_dict)
        portfolio = Portfolio(**args.get("portfolio", {}))
        price = args.get("price", action.price)
        return _exchange.submit_order(action, portfolio, price=price).to_dict()

    def portfolio_handler() -> dict:
        return Portfolio(cash=100_000.0).to_dict()

    return build_trading_mcp_server(
        perception_provider=perception_handler,
        analysis_provider=analysis_handler,
        risk_provider=risk_handler,
        juice_provider=juice_handler,
        order_provider=order_handler,
        portfolio_provider=portfolio_handler,
    )


_mcp_server = _build_mcp_server()


@app.route("/api/v1/mcp/tools", methods=["GET"])
def mcp_tools() -> tuple:
    return _ok({"tools": _mcp_server.list_tools()})


@app.route("/api/v1/mcp/call", methods=["POST"])
def mcp_call() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    tool = payload.get("tool")
    arguments = payload.get("arguments", {})
    approved = bool(payload.get("approved", False))
    if not tool:
        return _err("tool is required", 400)
    try:
        result = _mcp_server.call_tool(tool, arguments, approved=approved)
    except Exception as exc:
        return _err(str(exc), 400)
    return _ok(result)


# ─────────────────────────────────────────────────────────────────────────────
# ReAct Híbrido + Tree of Thoughts (UC-295)
# ─────────────────────────────────────────────────────────────────────────────
def _tot_environment(
    payload: Dict[str, Any], use_brain: bool
) -> TickPredictionEnvironment:
    brain = _brain if use_brain else None
    return TickPredictionEnvironment(
        brain=brain,
        fallback_map={
            "brain": ["ensemble"],
            "world_model": ["technical", "ensemble"],
            "technical": ["microstructure", "ensemble"],
            "microstructure": ["sentiment", "ensemble"],
            "sentiment": ["ensemble"],
        },
        failure_sources=payload.get("simulate_failures", []),
        latency_ms=0.0,
    )


@app.route("/api/v1/tot/predict", methods=["POST"])
def tot_predict() -> tuple:
    """Predice ask/bid del siguiente tick con ReAct Híbrido + Tree of Thoughts."""
    payload = flask_request.get_json(silent=True) or {}
    symbol = payload.get("symbol")
    ticks_raw = payload.get("ticks", [])
    if not symbol:
        return _err("symbol is required", 400)
    if not ticks_raw:
        return _err("ticks are required", 400)
    try:
        ticks = _ticks_from_json(ticks_raw)
        news = _news_from_json(payload.get("news", []))
    except Exception as exc:
        return _err(f"Invalid payload: {exc}", 400)

    predictors = payload.get("predictors", ["world_model", "technical", "microstructure"])
    use_brain = bool(payload.get("use_brain", False))
    confidence_threshold = float(payload.get("confidence_threshold", 0.5))
    max_depth = int(payload.get("max_depth", 2))

    env = _tot_environment(payload, use_brain)
    brain_tot = ReActReasonactToTBrain(
        env,
        confidence_threshold=confidence_threshold,
        max_depth=max_depth,
    )
    try:
        result = brain_tot.predict(
            symbol=symbol,
            ticks=ticks,
            news=news,
            predictors=predictors,
        )
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(result)


TOT_DOCS_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>UC-295 — ReAct Híbrido + Tree of Thoughts API Docs</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; background: #f6f8fa; color: #1f2328; }
    h1 { font-size: 1.6rem; }
    .endpoint { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background: #eef; padding: .15rem .35rem; border-radius: .25rem; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1rem; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    .card { background: #fff; border: 1px solid #d0d7de; border-radius: .75rem; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
    .card h2 { margin-top: 0; font-size: 1.1rem; color: #0969da; }
    table { width: 100%; border-collapse: collapse; margin-top: .75rem; font-size: .9rem; }
    th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #eee; }
    th { color: #57606a; font-weight: 600; background: #f6f8fa; }
    code { background: #f3f4f6; padding: .1rem .3rem; border-radius: .25rem; font-size: .85em; }
    .badge { display: inline-block; padding: .1rem .4rem; border-radius: .35rem; font-size: .75rem; font-weight: 600; }
    .required { background: #ffebe9; color: #cf222e; }
    .optional { background: #ddf4ff; color: #0969da; }
    .json { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: .5rem; padding: .75rem; overflow-x: auto; font-size: .8rem; }
  </style>
</head>
<body>
  <h1>UC-295 — ReAct Híbrido con Árbol de Pensamientos (ToT)</h1>
  <p>Endpoint: <span class="endpoint">POST /api/v1/tot/predict</span></p>
  <p>Resuelve la limitación del ReAct lineal expandiendo múltiples hipótesis de predicción ask/bid en paralelo, podando las ramas fallidas y retrocediendo a predictores de contingencia antes de sintetizar un veredicto consensuado.</p>

  <div class="grid">
    <div class="card">
      <h2>Input Card View</h2>
      <table>
        <tr><th>Parámetro</th><th>Tipo</th><th>Requerido</th><th>Descripción / Ejemplo</th></tr>
        <tr><td><code>symbol</code></td><td>string</td><td><span class="badge required">Sí</span></td><td>"AAPL"</td></tr>
        <tr><td><code>ticks</code></td><td>list[object]</td><td><span class="badge required">Sí</span></td><td>Lista de ticks con timestamp, bid, ask, last_price, volume, bid_size, ask_size</td></tr>
        <tr><td><code>news</code></td><td>list[object]</td><td><span class="badge optional">No</span></td><td>[{text, source}]</td></tr>
        <tr><td><code>predictors</code></td><td>list[string]</td><td><span class="badge optional">No</span></td><td>["world_model", "technical", "microstructure"]</td></tr>
        <tr><td><code>use_brain</code></td><td>boolean</td><td><span class="badge optional">No</span></td><td>true activa CentralBrain como predictor real</td></tr>
        <tr><td><code>confidence_threshold</code></td><td>number</td><td><span class="badge optional">No</span></td><td>0.5 — mínima confianza para aceptar una hoja</td></tr>
        <tr><td><code>max_depth</code></td><td>integer</td><td><span class="badge optional">No</span></td><td>2 — profundidad máxima de backtracking</td></tr>
        <tr><td><code>simulate_failures</code></td><td>list[string]</td><td><span class="badge optional">No</span></td><td>["technical"] fuerza fallos para pruebas</td></tr>
      </table>
      <h3 style="margin-top:1rem">Ejemplo</h3>
      <div class="json">{
  "symbol": "AAPL",
  "ticks": [
    {"timestamp":"2026-09-03T10:00:00Z","symbol":"AAPL","bid":150.10,"ask":150.12,"last_price":150.11,"volume":1000,"bid_size":2000,"ask_size":1500}
  ],
  "predictors": ["world_model","technical","microstructure"],
  "simulate_failures": ["technical"],
  "max_depth": 2
}</div>
    </div>

    <div class="card">
      <h2>Output Card View</h2>
      <table>
        <tr><th>Campo</th><th>Tipo</th><th>Descripción</th></tr>
        <tr><td><code>status</code></td><td>string</td><td>ok | error</td></tr>
        <tr><td><code>request_id</code></td><td>string</td><td>Identificador de la ejecución</td></tr>
        <tr><td><code>final_prediction</code></td><td>object</td><td>predicted_ask, predicted_bid, predicted_mid, spread, confidence, source_strategy</td></tr>
        <tr><td><code>selected_leaf</code></td><td>object</td><td>Mejor hoja individual según score</td></tr>
        <tr><td><code>consensus</code></td><td>object</td><td>Promedio ponderado por confianza de las hojas exitosas</td></tr>
        <tr><td><code>tree_summary</code></td><td>object</td><td>total_nodes, success_leaves, pruned_leaves, backtracked_nodes</td></tr>
        <tr><td><code>leaves</code></td><td>list[object]</td><td>Hojas exitosas con source, ask, bid, confidence</td></tr>
        <tr><td><code>tree</code></td><td>object</td><td>Árbol de pensamientos serializado</td></tr>
        <tr><td><code>trace</code></td><td>list[object]</td><td>Traza ReAct: thought, action, observation, backtrack, synthesis</td></tr>
      </table>
      <h3 style="margin-top:1rem">Ejemplo</h3>
      <div class="json">{
  "status": "ok",
  "request_id": "abc123",
  "final_prediction": {
    "predicted_ask": 150.135,
    "predicted_bid": 150.105,
    "predicted_mid": 150.120,
    "spread": 0.030,
    "confidence": 0.78,
    "source_strategy": "consensus_weighted"
  },
  "tree_summary": {"total_nodes": 7, "success_leaves": 3, "pruned_leaves": 1, "backtracked_nodes": 1}
}</div>
    </div>
  </div>
</body>
</html>
"""


@app.route("/api/v1/tot/docs", methods=["GET"])
def tot_docs() -> Any:
    """Muestra card views HTML de entrada y salida del endpoint /tot/predict."""
    return render_template_string(TOT_DOCS_HTML)


@app.errorhandler(404)
def not_found(_e: Any) -> tuple:
    return _err("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_e: Any) -> tuple:
    return _err("Method not allowed", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC292_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
