"""
UC-328 — API REST Flask para ORQUESTA-R.

Expone el orquestador resiliente de RAG empresarial como servicio REST.
Puerto por defecto: 5328
"""

from flask import Flask, request, jsonify
from typing import Dict, Any

from orchestrator import OrquestaREngine
from orquesta_models import OrquestaConfig, OrquestaResult, Budget, PrivacyPolicy

app = Flask(__name__)
engine = OrquestaREngine()

# ─── INPUT/OUTPUT CARDS ────────────────────────────────────────────────────────

INPUT_CARDS = {
    "POST /api/v1/orquesta/execute": {
        "description": "Ejecuta una orquestación ORQUESTA-R completa.",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Consulta empresarial original.",
                "example": "Recomendar acciones tecnológicas para hoy",
            },
            "context": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Contexto adicional de la tarea.",
            },
            "user_region": {
                "type": "string",
                "required": False,
                "default": "global",
                "description": "Región del usuario para cumplimiento normativo.",
            },
            "budget": {
                "type": "object",
                "required": False,
                "description": "Presupuesto: {max_cost, max_latency_ms, max_concurrent_calls, max_retries}",
            },
            "privacy_policies": {
                "type": "array",
                "required": False,
                "default": [],
                "description": "Lista de políticas: GDPR, HIPAA, CCPA, NONE.",
            },
        },
    },
    "POST /api/v1/orquesta/sources": {
        "description": "Registra una fuente externa.",
        "parameters": {
            "source": {
                "type": "object",
                "required": True,
                "description": "Metadata de la fuente (name, source_type, cost_per_call, etc.)",
            },
        },
    },
    "POST /api/v1/orquesta/cache/invalidate": {
        "description": "Invalida entradas de caché.",
        "parameters": {
            "subquery_text": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "Texto de subconsulta.",
            },
            "source_id": {
                "type": "string",
                "required": False,
                "default": "",
                "description": "ID de fuente.",
            },
        },
    },
    "GET /api/v1/orquesta/stats": {
        "description": "Estadísticas consolidadas del orquestador.",
        "parameters": {},
    },
    "GET /api/v1/orquesta/logs": {
        "description": "Logs estructurados.",
        "parameters": {
            "level": {"type": "string", "required": False},
            "trace_id": {"type": "string", "required": False},
            "limit": {"type": "integer", "required": False, "default": 100},
        },
    },
    "GET /api/v1/orquesta/spans": {
        "description": "Trazas (spans).",
        "parameters": {
            "trace_id": {"type": "string", "required": False},
        },
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/orquesta/execute": {
        "description": "Resultado de la orquestación.",
        "fields": {
            "trace_id": "string — UUID de traza.",
            "query": "string — Query original.",
            "verdict": "string — success | partial_success | fallback_used | budget_exceeded | latency_exceeded | failed.",
            "confidence": "float — Confianza global (0-1).",
            "answer": "string — Respuesta sintetizada.",
            "subqueries_count": "int — Número de subconsultas.",
            "resolved_facts_count": "int — Hechos resueltos.",
            "partial_results_count": "int — Resultados parciales.",
            "duration_ms": "float — Duración total en ms.",
            "context_version_id": "string — ID de versión de contexto.",
            "metrics": "object — Métricas de ejecución.",
            "warnings": "array — Advertencias.",
            "recommendations": "array — Recomendaciones.",
            "subqueries": "array — Detalle de subconsultas.",
            "resolved_facts": "array — Hechos resueltos.",
            "partial_results": "array — Top resultados parciales.",
        },
    },
    "POST /api/v1/orquesta/sources": {
        "description": "Fuente registrada.",
        "fields": {
            "source_id": "string — ID asignado.",
            "name": "string — Nombre de la fuente.",
            "source_type": "string — Tipo.",
            "cost_per_call": "float — Costo por llamada.",
            "reliability": "float — Confiabilidad.",
        },
    },
    "POST /api/v1/orquesta/cache/invalidate": {
        "description": "Entradas invalidadas.",
        "fields": {
            "invalidated": "int — Número de entradas invalidadas.",
        },
    },
    "GET /api/v1/orquesta/stats": {
        "description": "Estadísticas.",
        "fields": {
            "sources": "object — Fuentes.",
            "cache": "object — Caché.",
            "cost_latency": "object — Presupuesto.",
            "fault_tolerance": "object — Tolerancia a fallos.",
            "load_balancer": "object — Carga.",
            "context": "object — Contexto.",
            "privacy": "object — Privacidad.",
            "observability": "object — Observabilidad.",
        },
    },
}


# ─── ENDPOINTS ─────────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-328 ORQUESTA-R"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-328 — ORQUESTA-R: Orquestador Resiliente de RAG Empresarial",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/orquesta/execute"},
            {"method": "POST", "path": "/api/v1/orquesta/sources"},
            {"method": "POST", "path": "/api/v1/orquesta/cache/invalidate"},
            {"method": "GET", "path": "/api/v1/orquesta/stats"},
            {"method": "GET", "path": "/api/v1/orquesta/logs"},
            {"method": "GET", "path": "/api/v1/orquesta/spans"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/orquesta/execute", methods=["POST"])
def execute():
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400

    context = data.get("context", "")
    user_region = data.get("user_region", "global")
    budget_data = data.get("budget", {})
    privacy_policies = data.get("privacy_policies", [])

    config = OrquestaConfig(
        budget=Budget(
            max_cost=float(budget_data.get("max_cost", 10.0)),
            max_latency_ms=float(budget_data.get("max_latency_ms", 5000.0)),
            max_concurrent_calls=int(budget_data.get("max_concurrent_calls", 10)),
            max_retries=int(budget_data.get("max_retries", 2)),
        ),
        privacy_policies=[PrivacyPolicy(p) for p in privacy_policies if p] or [PrivacyPolicy.NONE],
    )

    # Reuse engine but update config for this request
    local_engine = OrquestaREngine(config=config)
    # Optionally copy registered sources from global engine
    for source in engine.sources.list_sources(enabled_only=False):
        local_engine.sources.register(source)
        conn = engine.sources.get_connector(source.source_id)
        if conn:
            local_engine.sources.register_connector(source.source_id, conn)

    result = local_engine.execute(query=query, context=context, user_region=user_region)
    return jsonify(result.to_dict())


@app.route("/api/v1/orquesta/sources", methods=["POST"])
def register_source():
    data = request.get_json(force=True)
    source_data = data.get("source")
    if not source_data:
        return jsonify({"error": "source is required"}), 400
    source = engine.sources.register_from_dict(source_data)
    return jsonify(source.to_dict())


@app.route("/api/v1/orquesta/cache/invalidate", methods=["POST"])
def invalidate_cache():
    data = request.get_json(force=True)
    subquery_text = data.get("subquery_text", "")
    source_id = data.get("source_id", "")
    count = engine.cache.invalidate(subquery_text, source_id)
    return jsonify({"invalidated": count})


@app.route("/api/v1/orquesta/stats", methods=["GET"])
def stats():
    return jsonify(engine.get_statistics())


@app.route("/api/v1/orquesta/logs", methods=["GET"])
def logs():
    level = request.args.get("level")
    trace_id = request.args.get("trace_id")
    limit = request.args.get("limit", 100, type=int)
    return jsonify({
        "logs": engine.observability.get_logs(level=level, trace_id=trace_id, limit=limit)
    })


@app.route("/api/v1/orquesta/spans", methods=["GET"])
def spans():
    trace_id = request.args.get("trace_id")
    return jsonify({
        "spans": engine.observability.get_spans(trace_id=trace_id)
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    return engine.observability.export_prometheus(), 200, {"Content-Type": "text/plain"}


# ─── SERVER ──────────────────────────────────────────────────────────────────

def run_server(port: int = 5328) -> None:
    print(f"UC-328 ORQUESTA-R API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
