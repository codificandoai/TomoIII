"""API REST Flask para el pipeline RAG híbrido de UC-251.

Endpoints:
  GET  /health
  GET  /api/v1/schema           -> card views de entrada/salida
  POST /api/v1/ingest           -> archivo o texto plano
  POST /api/v1/query            -> consulta RAG
  POST /api/v1/evaluate         -> evaluación RAGAS
  GET  /api/v1/stats            -> estadísticas del índice
  GET  /api/v1/audit            -> trazas de auditoría
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from config import RAGConfig
from models import EvaluationSample
from rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc251-api")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB

# Pipeline global configurado al arrancar
pipeline = RAGPipeline(RAGConfig())


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
# Card views de esquema de API (entrada / salida)
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/ingest",
        "description": "Ingesta un documento empresarial (archivo o texto). Extrae texto, tablas, metadatos y estructura jerárquica.",
        "parameters": [
            {
                "name": "file",
                "type": "multipart/file",
                "required": False,
                "example": "informe_anual.pdf",
                "note": "Obligatorio si no se envía 'text'.",
            },
            {
                "name": "text",
                "type": "string",
                "required": False,
                "example": "El sistema RAG procesa documentos...",
            },
            {
                "name": "title",
                "type": "string",
                "required": False,
                "example": "Informe Anual 2025",
            },
            {
                "name": "doc_type",
                "type": "string",
                "required": False,
                "example": "pdf",
                "enum": ["pdf", "docx", "pptx", "html", "txt", "md", "png", "jpg"],
            },
            {
                "name": "metadata",
                "type": "object",
                "required": False,
                "example": {
                    "tenant_id": "acme",
                    "doc_type": "contract",
                    "confidentiality": "internal",
                    "department": "legal",
                },
            },
        ],
    },
    {
        "endpoint": "POST /api/v1/query",
        "description": "Ejecuta una consulta RAG: recuperación híbrida, re-ranking y generación con citas.",
        "parameters": [
            {
                "name": "question",
                "type": "string",
                "required": True,
                "example": "¿Cuál es el procedimiento de aprobación de gastos?",
            },
            {
                "name": "tenant_id",
                "type": "string",
                "required": False,
                "example": "acme",
            },
            {
                "name": "user_id",
                "type": "string",
                "required": False,
                "example": "user-42",
            },
            {
                "name": "user_clearance",
                "type": "string",
                "required": False,
                "example": "internal",
                "enum": ["public", "internal", "confidential", "restricted"],
            },
            {
                "name": "filters",
                "type": "object",
                "required": False,
                "example": {
                    "doc_type": ["contract", "policy"],
                    "date_from": "2025-01-01",
                    "date_to": "2025-12-31",
                },
            },
            {
                "name": "top_k",
                "type": "integer",
                "required": False,
                "example": 5,
                "note": "Número final de fragmentos en el contexto",
            },
        ],
    },
    {
        "endpoint": "POST /api/v1/evaluate",
        "description": "Evalúa el pipeline con métricas RAGAS sobre un conjunto de muestras.",
        "parameters": [
            {
                "name": "samples",
                "type": "list[object]",
                "required": True,
                "example": [
                    {
                        "query": "¿Capital de Francia?",
                        "ground_truth": "París",
                        "reference_contexts": ["París es la capital de Francia."],
                        "expected_doc_ids": ["doc-001"],
                    }
                ],
            },
            {
                "name": "tenant_id",
                "type": "string",
                "required": False,
                "example": "acme",
            },
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/ingest",
        "description": "Resultado de la ingesta y fragmentación.",
        "fields": [
            {"name": "doc_id", "type": "string"},
            {"name": "num_chunks", "type": "integer"},
            {"name": "document", "type": "object", "note": "metadata, source, checksum, content_length"},
        ],
    },
    {
        "endpoint": "POST /api/v1/query",
        "description": "Respuesta generada con contexto, citas y metadatos de recuperación.",
        "fields": [
            {"name": "trace_id", "type": "string"},
            {"name": "query", "type": "string"},
            {"name": "answer", "type": "string"},
            {"name": "citations", "type": "list[object]", "note": "chunk_id, doc_id, source, excerpt, score"},
            {"name": "retrieved_chunks", "type": "list[object]", "note": "chunk, vector_score, lexical_score, hybrid_score, rerank_score"},
            {"name": "context", "type": "string", "note": "Texto enviado al LLM"},
            {"name": "generation_model", "type": "string"},
            {"name": "latency_ms", "type": "float"},
            {"name": "insufficient_info", "type": "boolean"},
            {"name": "security_flags", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/evaluate",
        "description": "Métricas RAGAS por muestra y promedio.",
        "fields": [
            {"name": "samples", "type": "list[object]"},
            {"name": "average_metrics", "type": "object", "note": "context_precision, context_recall, faithfulness, answer_relevance"},
            {"name": "total_samples", "type": "integer"},
        ],
    },
    {
        "endpoint": "GET /api/v1/stats",
        "description": "Estadísticas del índice y componentes activos.",
        "fields": [
            {"name": "documents_indexed", "type": "integer"},
            {"name": "chunks_indexed", "type": "integer"},
            {"name": "vector_backend", "type": "string"},
            {"name": "embedder_model", "type": "string"},
            {"name": "generator_provider", "type": "string"},
            {"name": "audit_logs_in_memory", "type": "integer"},
        ],
    },
    {
        "endpoint": "GET /api/v1/audit",
        "description": "Traza de auditoría de consultas procesadas.",
        "fields": [
            {"name": "logs", "type": "list[object]", "note": "trace_id, query, retrieved_chunk_ids, response_text, latency_ms, security_flags, metrics"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc251-rag", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/ingest", methods=["POST"])
def ingest():
    file = request.files.get("file")
    data = request.form.to_dict() if request.form else {}
    metadata = {}
    try:
        metadata = json.loads(data.get("metadata", "{}"))
    except json.JSONDecodeError:
        return _err("metadata debe ser JSON válido", 400)

    if file:
        suffix = os.path.splitext(file.filename or "")[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        try:
            result = pipeline.ingest_document(
                tmp_path,
                doc_type=data.get("doc_type") or None,
                title=data.get("title") or file.filename,
                metadata=metadata,
            )
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return _ok(result)

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        text = payload.get("text")
        if not text:
            return _err("Debe proporcionar 'file' o JSON con 'text'", 400)
        result = pipeline.ingest_text(
            text,
            title=payload.get("title", "inline"),
            metadata=payload.get("metadata", {}),
        )
        return _ok(result)

    return _err("Debe enviar un archivo multipart o un JSON con 'text'", 400)


@app.route("/api/v1/query", methods=["POST"])
def query():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question")
    if not question:
        return _err("'question' es requerido", 400)
    response = pipeline.query(
        question=question,
        filters=payload.get("filters"),
        top_k=payload.get("top_k"),
        user_clearance=payload.get("user_clearance"),
        tenant_id=payload.get("tenant_id"),
        user_id=payload.get("user_id"),
    )
    return _ok(response.to_dict())


@app.route("/api/v1/evaluate", methods=["POST"])
def evaluate():
    payload = request.get_json(silent=True) or {}
    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list) or not raw_samples:
        return _err("'samples' debe ser una lista no vacía", 400)
    samples = []
    for item in raw_samples:
        if not item.get("query") or not item.get("ground_truth"):
            return _err("Cada sample requiere 'query' y 'ground_truth'", 400)
        samples.append(
            EvaluationSample(
                query=item["query"],
                ground_truth=item["ground_truth"],
                reference_contexts=item.get("reference_contexts", []),
                expected_doc_ids=item.get("expected_doc_ids", []),
                metadata=item.get("metadata", {}),
            )
        )
    result = pipeline.evaluate(samples, tenant_id=payload.get("tenant_id"))
    return _ok(result)


@app.route("/api/v1/stats", methods=["GET"])
def stats():
    return _ok(pipeline.get_stats())


@app.route("/api/v1/audit", methods=["GET"])
def audit():
    logs = pipeline.audit.list_logs(
        trace_id=request.args.get("trace_id"),
        tenant_id=request.args.get("tenant_id"),
        limit=int(request.args.get("limit", 100)),
    )
    return _ok({"logs": [log.to_dict() for log in logs], "count": len(logs)})


@app.errorhandler(404)
def not_found(_e):
    return _err("Recurso no encontrado", 404)


@app.errorhandler(405)
def method_not_allowed(_e):
    return _err("Método no permitido", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC251_PORT", "5251"))
    app.run(host="0.0.0.0", port=port, debug=False)
