"""API REST Flask para UC-292 - Sistema Multi-Agente de Trading."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request as flask_request

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
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc292-multi-agent-trading", "status": "ready"})


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


@app.errorhandler(404)
def not_found(_e: Any) -> tuple:
    return _err("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_e: Any) -> tuple:
    return _err("Method not allowed", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC292_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
