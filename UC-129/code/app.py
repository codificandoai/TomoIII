"""
Codificando.AI - UC-129
API Flask que expone el sistema de métricas de resiliencia LLMOps:
ciclo de vida de incidentes (MTTD/MTTR/resolución/falsos
positivos/escalamiento HITL), analítica agregada, e interfaces de ingesta
de telemetría de Langfuse, LangSmith y LangGraph.

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/incidents  (parámetros de ENTRADA)
────────────────────────────────────────────────────────────────────────
┌───────────────────┬──────────┬───────────┬──────────────────────────────┐
│ Campo              │ Tipo     │ Requerido │ Descripción                  │
├───────────────────┼──────────┼───────────┼──────────────────────────────┤
│ incident_type      │ string   │ sí        │ HALLUCINATION | JAILBREAK |  │
│                    │          │           │ PROMPT_INJECTION | BIAS |    │
│                    │          │           │ TOXICITY | TOOL_FAILURE |    │
│                    │          │           │ SYSTEM_OVERLOAD |            │
│                    │          │           │ LATENCY_SPIKE                │
│ severity           │ string   │ no        │ LOW|MEDIUM|HIGH|CRITICAL     │
│ source             │ string   │ no        │ auto_guardrail|user_feedback │
│                    │          │           │ |monitoring_alert|manual|... │
│ model              │ string   │ no        │ Nombre del modelo LLM        │
│ summary            │ string   │ no        │ Descripción del incidente    │
│ trace_id           │ string   │ no        │ ID de traza de origen        │
│ event_time         │ float    │ no        │ Epoch (s) del evento real;   │
│                    │          │           │ por defecto, ahora           │
└───────────────────┴──────────┴───────────┴──────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/incidents  (parámetros de SALIDA)
────────────────────────────────────────────────────────────────────────
┌───────────────────┬──────────┬────────────────────────────────────────┐
│ Campo              │ Tipo     │ Descripción                             │
├───────────────────┼──────────┼────────────────────────────────────────┤
│ incident_id        │ string   │ ID único (UUID) del incidente          │
│ status             │ string   │ DETECTED | RESOLVED | FALSE_POSITIVE   │
│ mttd_seconds       │ float    │ Tiempo medio de detección (si aplica)  │
│ mttr_seconds       │ float    │ Tiempo medio de recuperación (si aplica)│
│ hitl_escalated     │ bool     │ Si fue escalado a revisión humana      │
│ is_false_positive  │ bool     │ Si fue marcado como falso positivo     │
│ created_at/updated_at │ string│ Timestamps ISO-8601 UTC                │
└───────────────────┴──────────┴────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/telemetry/{langfuse|langsmith|langgraph}
────────────────────────────────────────────────────────────────────────
ENTRADA: payload nativo de cada plataforma (ver `connectors/*.py` para el
esquema esperado de cada una).
SALIDA:
┌───────────────────┬──────────┬────────────────────────────────────────┐
│ Campo              │ Tipo     │ Descripción                             │
├───────────────────┼──────────┼────────────────────────────────────────┤
│ ingested           │ bool     │ Si la traza fue procesada correctamente│
│ trace              │ object   │ Traza normalizada (`IngestedTrace`)    │
│ incident_created   │ bool     │ Si se abrió un incidente automático    │
│ incident           │ object|null │ Incidente creado, si corresponde    │
└───────────────────┴──────────┴────────────────────────────────────────┘
"""

import logging
from typing import Any, Dict

from flask import Flask, jsonify, request, Response

from config import CONFIG, PREDEFINED_ROOT_CAUSES
from connectors import parse_langfuse_webhook, parse_langgraph_event, parse_langsmith_webhook
from incident_metrics_types import DetectionSource, IncidentStatus, IncidentType, ResolutionType, Severity
from incident_service import IncidentMetricsService
from logging_utils import configure_logging
import prometheus_metrics as pm

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

service = IncidentMetricsService()


@app.route("/health", methods=["GET"])
def health() -> Response:
    return jsonify({
        "status": "ok",
        "auto_create_incidents": CONFIG.telemetry.auto_create_incidents,
    }), 200


# ---------------------------------------------------------------------------
# Ciclo de vida de incidentes
# ---------------------------------------------------------------------------
@app.route("/api/v1/incidents", methods=["POST"])
def report_incident() -> Response:
    data: Dict[str, Any] = request.get_json(silent=True) or {}

    incident_type_raw = data.get("incident_type")
    if not incident_type_raw:
        return jsonify({"error": "El campo 'incident_type' es requerido"}), 400

    try:
        incident_type = IncidentType(incident_type_raw)
        severity = Severity(data.get("severity", "MEDIUM"))
        source = DetectionSource(data.get("source", "monitoring_alert"))
    except ValueError as e:
        return jsonify({"error": f"Valor inválido: {e}"}), 400

    record = service.report_event(
        incident_type=incident_type, severity=severity, source=source,
        model=data.get("model", "unknown"), summary=data.get("summary", ""),
        trace_id=data.get("trace_id"), event_time=data.get("event_time"),
    )
    return jsonify(record.to_dict()), 201


@app.route("/api/v1/incidents", methods=["GET"])
def list_incidents() -> Response:
    incident_type_param = request.args.get("incident_type")
    status_param = request.args.get("status")
    incident_type = IncidentType(incident_type_param) if incident_type_param else None
    status = IncidentStatus(status_param) if status_param else None
    records = service.list(incident_type=incident_type, status=status)
    return jsonify([r.to_dict() for r in records]), 200


@app.route("/api/v1/incidents/<incident_id>", methods=["GET"])
def get_incident(incident_id: str) -> Response:
    record = service.get(incident_id)
    if record is None:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(record.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/detect", methods=["POST"])
def detect_incident(incident_id: str) -> Response:
    data = request.get_json(silent=True) or {}
    try:
        record = service.record_detection(incident_id, data.get("detection_method", "manual"))
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(record.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/resolve", methods=["POST"])
def resolve_incident(incident_id: str) -> Response:
    data = request.get_json(silent=True) or {}
    try:
        resolution_type = ResolutionType(data.get("resolution_type", "auto_remediation"))
    except ValueError as e:
        return jsonify({"error": f"resolution_type inválido: {e}"}), 400

    try:
        record = service.record_resolution(
            incident_id, resolution_type, bool(data.get("success", True)),
            tokens_during_incident=int(data.get("tokens_during_incident", 0)),
            latency_during_incident_s=data.get("latency_during_incident_s"),
        )
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(record.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/false-positive", methods=["POST"])
def mark_false_positive(incident_id: str) -> Response:
    try:
        record = service.record_false_positive(incident_id)
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(record.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/escalate", methods=["POST"])
def escalate_incident(incident_id: str) -> Response:
    data = request.get_json(silent=True) or {}
    try:
        record = service.record_hitl_escalation(
            incident_id, data.get("reason", "unspecified"), data.get("reviewer_role", "on_call"),
        )
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(record.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/close", methods=["POST"])
def close_incident(incident_id: str) -> Response:
    data = request.get_json(silent=True) or {}
    root_cause = data.get("root_cause", "unknown")
    if root_cause not in PREDEFINED_ROOT_CAUSES:
        return jsonify({"error": f"root_cause inválida. Use una de: {PREDEFINED_ROOT_CAUSES}"}), 400
    try:
        record = service.close_incident(incident_id, root_cause)
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(record.to_dict()), 200


@app.route("/api/v1/analytics/summary", methods=["GET"])
def analytics_summary() -> Response:
    window_hours = request.args.get("window_hours", type=int)
    return jsonify(service.summary(window_hours=window_hours)), 200


# ---------------------------------------------------------------------------
# Interfaces de ingesta de telemetría: Langfuse / LangSmith / LangGraph
# ---------------------------------------------------------------------------
def _handle_ingestion(parse_fn) -> Response:
    payload = request.get_json(silent=True) or {}
    try:
        trace = parse_fn(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    incident = service.ingest_trace(trace)
    return jsonify({
        "ingested": True,
        "trace": trace.to_dict(),
        "incident_created": incident is not None,
        "incident": incident.to_dict() if incident else None,
    }), 201


@app.route("/api/v1/telemetry/langfuse", methods=["POST"])
def ingest_langfuse() -> Response:
    return _handle_ingestion(parse_langfuse_webhook)


@app.route("/api/v1/telemetry/langsmith", methods=["POST"])
def ingest_langsmith() -> Response:
    return _handle_ingestion(parse_langsmith_webhook)


@app.route("/api/v1/telemetry/langgraph", methods=["POST"])
def ingest_langgraph() -> Response:
    return _handle_ingestion(parse_langgraph_event)


@app.route("/metrics", methods=["GET"])
def metrics() -> Response:
    return Response(pm.export_latest(), mimetype="text/plain; version=0.0.4; charset=utf-8")


@app.errorhandler(404)
def not_found(_e) -> Response:
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.errorhandler(405)
def method_not_allowed(_e) -> Response:
    return jsonify({"error": "Método no permitido"}), 405


if __name__ == "__main__":
    import os
    port = int(os.getenv("APP_PORT", "8002"))
    app.run(host="0.0.0.0", port=port, debug=False)
