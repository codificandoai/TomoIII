"""Flask API and card views for governed self-correction."""
from __future__ import annotations

from flask import Flask, jsonify, request

from memory import LessonMemory
from models import MarketContext, PricingPolicy
from self_correction import GovernedPricingLoop

app = Flask(__name__)
memory = LessonMemory()
idempotency_cache = {}

INPUT_CARDS = [{"endpoint": "POST /api/v1/correct", "description": "Run Observe→Analyze→Fix→Verify→Learn", "parameters": [
    {"name": "product_id", "type": "string", "required": True}, {"name": "current_price", "type": "number", "required": True},
    {"name": "cost", "type": "number", "required": True}, {"name": "competitor_price", "type": "number", "required": True},
    {"name": "historical_volatility", "type": "number", "required": True}, {"name": "elasticity", "type": "number", "required": False},
    {"name": "base_demand", "type": "number", "required": False}, {"name": "max_attempts", "type": "integer", "required": False},
    {"name": "apply", "type": "boolean", "required": False}, {"name": "approved", "type": "boolean", "required": False},
    {"name": "idempotency_key", "type": "string", "required": False}]}]
OUTPUT_CARDS = [{"endpoint": "POST /api/v1/correct", "fields": [
    {"name": "attempts", "type": "array", "description": "Proposals, deterministic critiques and challenge gates"},
    {"name": "final_price", "type": "number|null"}, {"name": "status", "type": "string"},
    {"name": "lessons", "type": "array<string>"}, {"name": "audit_hash", "type": "sha256"}]}]

def ok(data, status=200): return jsonify({"status": "ok", "data": data}), status
def error(message, status=400): return jsonify({"status": "error", "message": message}), status
@app.errorhandler(ValueError)
def value_error(exc): return error(str(exc))

@app.get("/health")
def health(): return ok({"service": "uc283-governed-self-correction", "ready": True})
@app.get("/api/v1/schema")
def schema(): return ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})
@app.get("/api/v1/tools")
def tools():
    sample = MarketContext("schema", 100, 60, 95, 5)
    loop = GovernedPricingLoop(memory); loop.execute(sample)
    return ok(loop.server.list_tools())

@app.post("/api/v1/correct")
def correct():
    data = request.get_json(silent=True) or {}
    required = ["product_id", "current_price", "cost", "competitor_price", "historical_volatility"]
    missing = [key for key in required if key not in data]
    if missing: return error(f"Missing required fields: {', '.join(missing)}")
    cache_key = data.get("idempotency_key")
    if cache_key and cache_key in idempotency_cache:
        return ok(idempotency_cache[cache_key])
    context = MarketContext(str(data["product_id"]), float(data["current_price"]), float(data["cost"]),
                            float(data["competitor_price"]), float(data["historical_volatility"]),
                            float(data.get("elasticity", -1.5)), float(data.get("base_demand", 5000)))
    loop = GovernedPricingLoop(memory, PricingPolicy(), int(data.get("max_attempts", 4)))
    result = loop.execute(context, bool(data.get("apply", False)), bool(data.get("approved", False)))
    output = result.public_dict(); output["audit_hash"] = result.audit_hash()
    if cache_key:
        idempotency_cache[cache_key] = output
    return ok(output)

@app.get("/api/v1/memory/<product_id>")
def get_memory(product_id): return ok({"lessons": memory.recall(product_id, 50), "stats": memory.stats(product_id)})

if __name__ == "__main__": app.run(host="0.0.0.0", port=5283, debug=False)