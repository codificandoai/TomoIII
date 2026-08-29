"""Flask API for the TrackPrice.ai pricing digital-twin pipeline."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file

from core import TwinRegistry
from models import MarketState, PricingPolicy, ScenarioType

app = Flask(__name__)
registry = TwinRegistry()

INPUT_CARDS = [
    {"endpoint": "POST /api/v1/twins", "description": "Create a SKU pricing twin", "parameters": [
        {"name": "sku", "type": "string", "required": True}, {"name": "current_price", "type": "number", "required": True},
        {"name": "unit_cost", "type": "number", "required": True}, {"name": "competitor_price", "type": "number", "required": True},
        {"name": "current_demand", "type": "number", "required": True}, {"name": "inventory", "type": "number", "required": False, "default": 10000},
        {"name": "elasticity", "type": "number", "required": False, "default": -1.5}, {"name": "policy", "type": "object", "required": False}]},
    {"endpoint": "POST /api/v1/twins/{sku}/observations", "description": "Ingest live market observation", "parameters": [
        {"name": "price", "type": "number", "required": True}, {"name": "demand", "type": "number", "required": True},
        {"name": "competitor_price", "type": "number", "required": True}, {"name": "inventory", "type": "number", "required": False},
        {"name": "expected_version", "type": "integer", "required": False}]},
    {"endpoint": "POST /api/v1/twins/{sku}/optimize", "description": "Run the six-agent decision pipeline", "parameters": [
        {"name": "scenario", "type": "string", "required": False, "enum": [s.value for s in ScenarioType]},
        {"name": "objective", "type": "string", "required": False, "enum": ["profit", "revenue"]},
        {"name": "execute", "type": "boolean", "required": False, "default": False}]},
    {"endpoint": "POST /api/v1/twins/{sku}/forecast", "description": "Forecast demand and profit", "parameters": [
        {"name": "days", "type": "integer", "required": False, "default": 30},
        {"name": "scenario", "type": "string", "required": False}, {"name": "price", "type": "number", "required": False}]},
    {"endpoint": "POST /api/v1/twins/{sku}/simulate", "description": "Run deterministic market cycles", "parameters": [
        {"name": "steps", "type": "integer", "required": False, "default": 10},
        {"name": "scenario", "type": "string", "required": False}, {"name": "auto_execute", "type": "boolean", "required": False, "default": True}]},
]
OUTPUT_CARDS = [
    {"endpoint": "POST /api/v1/twins/{sku}/optimize", "fields": [
        {"name": "cycle_id", "type": "string"}, {"name": "signals", "type": "array", "description": "Six typed agent signals"},
        {"name": "recommendation", "type": "object"}, {"name": "executed", "type": "boolean"},
        {"name": "audit_hash", "type": "sha256"}]},
    {"endpoint": "POST /api/v1/twins/{sku}/forecast", "fields": [
        {"name": "forecast", "type": "array", "description": "Price, demand bands and expected profit by horizon"}]},
    {"endpoint": "GET /api/v1/twins/{sku}", "fields": [
        {"name": "state", "type": "object"}, {"name": "policy", "type": "object"}, {"name": "cycle_count", "type": "integer"}]},
]


def ok(data: Any, status: int = 200):
    return jsonify({"status": "ok", "data": data}), status


def error(message: str, status: int = 400):
    return jsonify({"status": "error", "message": message}), status


def body() -> dict:
    return request.get_json(silent=True) or {}


def cycle_dict(result):
    data = asdict(result)
    data["audit_hash"] = result.audit_hash()
    return data


@app.errorhandler(ValueError)
def handle_value_error(exc):
    return error(str(exc), 400)


@app.errorhandler(KeyError)
def handle_key_error(exc):
    return error(str(exc).strip("'"), 404)


@app.get("/")
def dashboard():
    return send_file(Path(__file__).with_name("view.html"))


@app.get("/health")
def health():
    return ok({"service": "trackprice-digital-twin", "ready": True, "twins": len(registry.list())})


@app.get("/api/v1/schema")
def schema():
    return ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.post("/api/v1/twins")
def create_twin():
    data = body()
    required = ["sku", "current_price", "unit_cost", "competitor_price", "current_demand"]
    missing = [key for key in required if key not in data]
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}")
    policy = PricingPolicy(**data.get("policy", {}))
    state = MarketState(sku=str(data["sku"]), current_price=float(data["current_price"]),
                        unit_cost=float(data["unit_cost"]), competitor_price=float(data["competitor_price"]),
                        current_demand=float(data["current_demand"]), inventory=float(data.get("inventory", 10000)),
                        elasticity=float(data.get("elasticity", -1.5)))
    twin = registry.create(state, policy, int(data.get("seed", 42)))
    return ok({"twin_id": twin.twin_id, "state": twin.state.public_dict(), "policy": asdict(policy)}, 201)


@app.get("/api/v1/twins")
def list_twins():
    return ok([{"twin_id": t.twin_id, "sku": t.state.sku, "version": t.state.version,
                "price": t.state.current_price, "cycles": len(t.cycles)} for t in registry.list()])


@app.get("/api/v1/twins/<sku>")
def get_twin(sku):
    twin = registry.get(sku)
    return ok({"twin_id": twin.twin_id, "state": twin.state.public_dict(),
               "policy": asdict(twin.policy), "cycle_count": len(twin.cycles)})


@app.post("/api/v1/twins/<sku>/observations")
def ingest(sku):
    data, twin = body(), registry.get(sku)
    for key in ["price", "demand", "competitor_price"]:
        if key not in data:
            return error(f"{key} is required")
    state = twin.ingest(float(data["price"]), float(data["demand"]), float(data["competitor_price"]),
                        float(data["inventory"]) if "inventory" in data else None, data.get("expected_version"))
    return ok(state)


@app.post("/api/v1/twins/<sku>/optimize")
def optimize(sku):
    data, twin = body(), registry.get(sku)
    result = twin.analyze(ScenarioType(data.get("scenario", "baseline")), data.get("objective", "profit"), bool(data.get("execute", False)))
    return ok(cycle_dict(result))


@app.post("/api/v1/twins/<sku>/forecast")
def project(sku):
    data, twin = body(), registry.get(sku)
    return ok({"sku": sku, "scenario": data.get("scenario", "baseline"),
               "forecast": twin.project(int(data.get("days", 30)), ScenarioType(data.get("scenario", "baseline")), data.get("price"))})


@app.post("/api/v1/twins/<sku>/simulate")
def simulate(sku):
    data, twin = body(), registry.get(sku)
    results = twin.simulate(int(data.get("steps", 10)), ScenarioType(data.get("scenario", "baseline")), bool(data.get("auto_execute", True)))
    return ok({"cycles": [cycle_dict(r) for r in results], "final_state": twin.state.public_dict()})


@app.get("/api/v1/twins/<sku>/cycles")
def cycles(sku):
    twin = registry.get(sku)
    limit = min(100, max(1, int(request.args.get("limit", 20))))
    return ok([cycle_dict(r) for r in twin.cycles[-limit:]])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5279, debug=False)