"""
Codificando.AI - UC-119
API Flask para exponer el pipeline de monitoreo de LLMs.

Endpoints:
  GET  /health                    -> liveness/readiness probe.
  POST /api/v1/monitor            -> ejecuta el pipeline completo de
                                      monitoreo sobre un par prompt/response
                                      y devuelve el reporte de métricas.
  GET  /api/v1/reports/<id>       -> recupera un reporte previamente
                                      generado (almacenado en memoria).
  GET  /metrics                   -> métricas en formato Prometheus
                                      (scrape endpoint).

Ejecutar en desarrollo:
    python app.py

Ejecutar en producción (ejemplo):
    gunicorn -w 4 -b 0.0.0.0:8000 app:app
"""

import logging
import os
from typing import Any, Dict

from flask import Flask, jsonify, request, Response

from config import CONFIG
from logging_utils import configure_logging
from monitoring_system import LLMMonitoringSystem
import prometheus_metrics as pm

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

monitoring_system = LLMMonitoringSystem()

# Almacén en memoria de reportes recientes (demo). En producción, sustituir
# por una base de datos o almacenamiento de trazas (p.ej. Tempo/Loki).
_REPORTS_STORE: Dict[str, Dict[str, Any]] = {}
_MAX_STORED_REPORTS = 1000


def _store_report(report_id: str, payload: Dict[str, Any]) -> None:
    if len(_REPORTS_STORE) >= _MAX_STORED_REPORTS:
        oldest_key = next(iter(_REPORTS_STORE))
        _REPORTS_STORE.pop(oldest_key, None)
    _REPORTS_STORE[report_id] = payload


@app.route("/health", methods=["GET"])
def health() -> Response:
    """Endpoint de salud para orquestadores (liveness/readiness)."""
    return jsonify({
        "status": "ok",
        "model": monitoring_system.model_name,
        "provider": monitoring_system.provider,
    }), 200


@app.route("/api/v1/monitor", methods=["POST"])
def monitor() -> Response:
    """Ejecuta el pipeline completo de monitoreo sobre una interacción LLM.

    Cuerpo JSON esperado:
    {
      "prompt": "...",                      // requerido
      "response": "...",                    // requerido
      "context": "...",                     // opcional (RAG)
      "retrieved_docs": ["...", "..."],      // opcional
      "request_id": "uuid",                 // opcional
      "tokens_generated": 128,              // opcional
      "input_tokens": 32,                   // opcional
      "ttft_ms": 250.0,                     // opcional
      "generation_latency_ms": 900.0,       // opcional (latencia real del LLM)
      "cache_hit": false,                   // opcional
      "error_occurred": false,              // opcional
      "rate_limited": false,                // opcional
      "finish_reason": "stop",              // opcional
      "tool_calls": [{"tool_name": "search", "arguments": {}}], // opcional
      "agent_steps": 2,                     // opcional
      "prompt_template": "rag_v1",          // opcional
      "parameters": {"temperature": 0.7},   // opcional
      "user_rating": 4.5,                   // opcional
      "user": "user-123",                   // opcional
      "function": "chat"                    // opcional
    }
    """
    data = request.get_json(silent=True) or {}

    prompt = data.get("prompt")
    response_text = data.get("response")

    if not prompt or not response_text:
        return jsonify({"error": "Los campos 'prompt' y 'response' son requeridos"}), 400

    try:
        report = monitoring_system.monitor_request(
            prompt=prompt,
            response=response_text,
            request_id=data.get("request_id"),
            context=data.get("context", ""),
            retrieved_docs=data.get("retrieved_docs"),
            tokens_generated=int(data.get("tokens_generated", 0)),
            input_tokens=data.get("input_tokens"),
            ttft_ms=float(data.get("ttft_ms", 0.0)),
            generation_latency_ms=data.get("generation_latency_ms"),
            cache_hit=bool(data.get("cache_hit", False)),
            error_occurred=bool(data.get("error_occurred", False)),
            rate_limited=bool(data.get("rate_limited", False)),
            finish_reason=data.get("finish_reason", "stop"),
            tool_calls=data.get("tool_calls"),
            agent_steps=int(data.get("agent_steps", 0)),
            prompt_template=data.get("prompt_template"),
            parameters=data.get("parameters"),
            user_rating=data.get("user_rating"),
            user=data.get("user", "anonymous"),
            function=data.get("function", "default"),
        )
    except Exception as e:
        logger.exception("Error ejecutando el pipeline de monitoreo")
        return jsonify({"error": f"Error interno procesando la solicitud: {e}"}), 500

    payload = report.to_dict()
    _store_report(report.request_id, payload)

    return jsonify(payload), 200


@app.route("/api/v1/reports/<report_id>", methods=["GET"])
def get_report(report_id: str) -> Response:
    """Recupera un reporte de monitoreo previamente generado."""
    payload = _REPORTS_STORE.get(report_id)
    if payload is None:
        return jsonify({"error": "Reporte no encontrado"}), 404
    return jsonify(payload), 200


@app.route("/metrics", methods=["GET"])
def metrics() -> Response:
    """Expone las métricas en formato Prometheus para scraping."""
    data = pm.export_latest()
    return Response(data, mimetype="text/plain; version=0.0.4; charset=utf-8")


@app.errorhandler(404)
def not_found(_e) -> Response:
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.errorhandler(405)
def method_not_allowed(_e) -> Response:
    return jsonify({"error": "Método no permitido"}), 405


if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
