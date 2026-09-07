"""
UC-329 — API REST Flask para GraphRAG-GoT.

Expone el motor de razonamiento sobre grafos como servicio REST.
Puerto por defecto: 5329
"""

from flask import Flask, request, jsonify
from typing import Dict, Any

from orchestrator_329 import GraphRAGGoTEngine
from graph_models import GraphRAGGoTConfig, GraphRAGGoTResult

app = Flask(__name__)
engine = GraphRAGGoTEngine()

# ─── INPUT/OUTPUT CARDS ────────────────────────────────────────────────────────

INPUT_CARDS = {
    "POST /api/v1/graphrag-got/ingest": {
        "description": "Ingesta evidencia textual al grafo de conocimiento.",
        "parameters": {
            "text": {"type": "string", "required": True, "description": "Texto con evidencia."},
            "source_id": {"type": "string", "required": False, "description": "Identificador de fuente."},
            "domain": {"type": "string", "required": False, "default": "default", "description": "Dominio temático."},
        },
    },
    "POST /api/v1/graphrag-got/reason": {
        "description": "Ejecuta GraphRAG-GoT sobre el conocimiento almacenado.",
        "parameters": {
            "query": {"type": "string", "required": True, "description": "Consulta compleja."},
            "context": {"type": "string", "required": False, "default": "", "description": "Contexto adicional."},
            "domain": {"type": "string", "required": False, "default": "default", "description": "Dominio temático."},
            "start_nodes": {"type": "array", "required": False, "description": "IDs de nodos semilla opcionales."},
            "end_nodes": {"type": "array", "required": False, "description": "IDs de nodos destino opcionales."},
        },
    },
    "POST /api/v1/graphrag-got/feedback": {
        "description": "Envía retroalimentación sobre un resultado.",
        "parameters": {
            "trace_id": {"type": "string", "required": True, "description": "ID de traza."},
            "outcome": {"type": "string", "required": True, "description": "success | partial | failure"},
            "intensity": {"type": "float", "required": False, "default": 1.0, "description": "Intensidad del refuerzo/penalización."},
        },
    },
    "GET /api/v1/graphrag-got/stats": {
        "description": "Estadísticas del motor.",
        "parameters": {},
    },
    "GET /api/v1/graphrag-got/logs": {
        "description": "Logs estructurados.",
        "parameters": {
            "level": {"type": "string", "required": False},
            "trace_id": {"type": "string", "required": False},
            "limit": {"type": "integer", "required": False, "default": 100},
        },
    },
    "GET /api/v1/graphrag-got/spans": {
        "description": "Trazas.",
        "parameters": {
            "trace_id": {"type": "string", "required": False},
        },
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/graphrag-got/ingest": {
        "description": "Resultado de la ingesta.",
        "fields": {
            "entities_added": "int — Entidades extraídas.",
            "relations_added": "int — Relaciones extraídas.",
            "source_id": "string — Fuente.",
            "domain": "string — Dominio.",
        },
    },
    "POST /api/v1/graphrag-got/reason": {
        "description": "Resultado del razonamiento GraphRAG-GoT.",
        "fields": {
            "trace_id": "string — UUID de traza.",
            "query": "string — Query original.",
            "answer": "string — Respuesta sintetizada.",
            "narrative": "string — Narrativa del razonamiento.",
            "metrics": "object — Métricas del razonamiento.",
            "reasoning_paths": "array — Caminos de razonamiento.",
            "contradictions": "array — Inconsistencias detectadas.",
            "recommendations": "array — Recomendaciones.",
            "uncertainties": "array — Dimensiones no exploradas.",
            "thought_graph": "object — Grafo del pensamiento.",
            "visualization_data": "object — Datos para visualización.",
            "duration_ms": "float — Duración total.",
        },
    },
    "POST /api/v1/graphrag-got/feedback": {
        "description": "Confirmación de retroalimentación.",
        "fields": {
            "status": "string — feedback recorded.",
            "outcome": "string — Outcome recibido.",
            "trace_id": "string — Traza asociada.",
        },
    },
    "GET /api/v1/graphrag-got/stats": {
        "description": "Estadísticas del motor.",
        "fields": {
            "knowledge_graph": "object — Métricas del KG.",
            "thought_graph": "object — Métricas del GoT.",
            "memory": "object — Memoria.",
            "plasticity": "object — Plasticidad.",
            "observability": "object — Observabilidad.",
        },
    },
}


# ─── ENDPOINTS ─────────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-329 GraphRAG-GoT"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-329 — GraphRAG-GoT: Razonamiento sobre Grafos de Conocimiento",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/graphrag-got/ingest"},
            {"method": "POST", "path": "/api/v1/graphrag-got/reason"},
            {"method": "POST", "path": "/api/v1/graphrag-got/feedback"},
            {"method": "GET", "path": "/api/v1/graphrag-got/stats"},
            {"method": "GET", "path": "/api/v1/graphrag-got/logs"},
            {"method": "GET", "path": "/api/v1/graphrag-got/spans"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/graphrag-got/ingest", methods=["POST"])
def ingest():
    data = request.get_json(force=True)
    text = data.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400
    result = engine.ingest(
        text=text,
        source_id=data.get("source_id"),
        domain=data.get("domain", "default"),
    )
    return jsonify(result)


@app.route("/api/v1/graphrag-got/reason", methods=["POST"])
def reason():
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify({"error": "query is required"}), 400
    result = engine.reason(
        query=query,
        context=data.get("context", ""),
        domain=data.get("domain", "default"),
        start_nodes=data.get("start_nodes"),
        end_nodes=data.get("end_nodes"),
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/graphrag-got/feedback", methods=["POST"])
def feedback():
    data = request.get_json(force=True)
    trace_id = data.get("trace_id")
    outcome = data.get("outcome")
    if not trace_id or not outcome:
        return jsonify({"error": "trace_id and outcome are required"}), 400
    result = engine.feedback(
        trace_id=trace_id,
        outcome=outcome,
        intensity=float(data.get("intensity", 1.0)),
    )
    return jsonify(result)


@app.route("/api/v1/graphrag-got/stats", methods=["GET"])
def stats():
    return jsonify(engine.get_statistics())


@app.route("/api/v1/graphrag-got/logs", methods=["GET"])
def logs():
    level = request.args.get("level")
    trace_id = request.args.get("trace_id")
    limit = request.args.get("limit", 100, type=int)
    return jsonify({
        "logs": engine.observability.get_logs(level=level, trace_id=trace_id, limit=limit)
    })


@app.route("/api/v1/graphrag-got/spans", methods=["GET"])
def spans():
    trace_id = request.args.get("trace_id")
    return jsonify({
        "spans": engine.observability.get_spans(trace_id=trace_id)
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    return engine.observability.export_prometheus(), 200, {"Content-Type": "text/plain"}


# ─── SERVER ──────────────────────────────────────────────────────────────────

def run_server(port: int = 5329) -> None:
    print(f"UC-329 GraphRAG-GoT API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
