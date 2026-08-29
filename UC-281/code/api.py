"""Flask API and card views for the federated TrackPrice pipeline."""
from __future__ import annotations

from flask import Flask, jsonify, request

from models import ExecutionMode, MarketState
from orchestrator import TrackPriceFederatedOrchestrator
from store import RunStore

app = Flask(__name__)
pipelines = {}
store = RunStore()

INPUT_CARDS = [
    {"endpoint": "POST /api/v1/pipelines", "description": "Create synchronized TrackPrice pipeline", "parameters": [
        {"name": "sku", "type": "string", "required": True}, {"name": "current_price", "type": "number", "required": True},
        {"name": "unit_cost", "type": "number", "required": True}, {"name": "competitor_price", "type": "number", "required": True},
        {"name": "demand", "type": "number", "required": True}, {"name": "inventory", "type": "number", "required": False},
        {"name": "headlines", "type": "array<string>", "required": False},
        {"name": "mode", "type": "string", "required": False, "enum": ["simulation", "native", "auto"]}]},
    {"endpoint": "POST /api/v1/pipelines/{sku}/run", "description": "Run all framework adapters behind a synchronization barrier", "parameters": [
        {"name": "task", "type": "string", "required": False}, {"name": "execute", "type": "boolean", "required": False},
        {"name": "idempotency_key", "type": "string", "required": False}]},
]
OUTPUT_CARDS = [
    {"endpoint": "POST /api/v1/pipelines/{sku}/run", "fields": [
        {"name": "responses", "type": "array", "description": "Framework responses and native/fallback status"},
        {"name": "decision", "type": "object", "description": "Weighted consensus and guardrails"},
        {"name": "state_after", "type": "object"}, {"name": "audit_hash", "type": "sha256"}]},
    {"endpoint": "GET /api/v1/pipelines/{sku}", "fields": [
        {"name": "state", "type": "object"}, {"name": "frameworks", "type": "object"}, {"name": "runs", "type": "integer"}]},
]


def ok(data, status=200): return jsonify({"status": "ok", "data": data}), status
def error(message, status=400): return jsonify({"status": "error", "message": message}), status


@app.errorhandler(ValueError)
def value_error(exc): return error(str(exc))
@app.errorhandler(KeyError)
def key_error(exc): return error(str(exc).strip("'"), 404)
@app.errorhandler(RuntimeError)
def runtime_error(exc): return error(str(exc), 503)


@app.get("/health")
def health(): return ok({"service": "uc281-federated-agent-orchestrator", "ready": True, "pipelines": len(pipelines)})
@app.get("/api/v1/schema")
def schema(): return ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.post("/api/v1/pipelines")
def create_pipeline():
    data = request.get_json(silent=True) or {}
    required = ["sku", "current_price", "unit_cost", "competitor_price", "demand"]
    missing = [key for key in required if key not in data]
    if missing: return error(f"Missing required fields: {', '.join(missing)}")
    if data["sku"] in pipelines: return error("pipeline already exists")
    state = MarketState(str(data["sku"]), float(data["current_price"]), float(data["unit_cost"]),
                        float(data["competitor_price"]), float(data["demand"]), float(data.get("inventory", 10000)),
                        float(data.get("elasticity", -1.5)), list(data.get("headlines", [])))
    pipeline = TrackPriceFederatedOrchestrator(state, ExecutionMode(data.get("mode", "auto")),
                                                float(data.get("assimilation_rate", .3)),
                                                float(data.get("timeout_seconds", 10)))
    pipelines[state.sku] = pipeline
    return ok(pipeline.status(), 201)


@app.get("/api/v1/pipelines")
def list_pipelines(): return ok([{"sku": sku, **pipeline.status()} for sku, pipeline in pipelines.items()])
@app.get("/api/v1/pipelines/<sku>")
def get_pipeline(sku): return ok(pipelines[sku].status())


@app.post("/api/v1/pipelines/<sku>/run")
def run_pipeline(sku):
    data = request.get_json(silent=True) or {}
    run = pipelines[sku].run(data.get("task", "Optimize TrackPrice price"), bool(data.get("execute", False)), data.get("idempotency_key"))
    store.save(run)
    result = run.public_dict(); result["audit_hash"] = run.audit_hash()
    return ok(result)


@app.get("/api/v1/pipelines/<sku>/events")
def events(sku): return ok(pipelines[sku].bus.events(request.args.get("run_id")))
@app.get("/api/v1/runs")
def runs(): return ok(store.list(min(100, max(1, int(request.args.get("limit", 50))))))
@app.get("/api/v1/runs/<run_id>")
def get_run(run_id): return ok(store.get(run_id))


if __name__ == "__main__": app.run(host="0.0.0.0", port=5281, debug=False)