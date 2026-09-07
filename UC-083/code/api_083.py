"""
UC-083 — API REST Flask para Respuesta a Incidentes de Inferencia Batch.

Expone el motor de respuesta a incidentes como servicio REST.
Puerto por defecto: 5083
"""

from flask import Flask, request, jsonify
from typing import Dict, Any, List

from incident_models import MetricSnapshot, IncidentResponseConfig, IncidentResponseResult
from incident_engine import IncidentResponseEngine

app = Flask(__name__)

_engine: IncidentResponseEngine = IncidentResponseEngine(pipeline_id="trackprice_default")

INPUT_CARDS = {
    "POST /api/v1/incident/declare": {
        "description": "Declara un nuevo incidente.",
        "parameters": {
            "title": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "severity": {"type": "string", "required": False, "default": "P1", "description": "P1 | P2 | P3"},
            "affected_partitions": {"type": "array", "required": False, "description": "Lista de IDs de particiones afectadas."},
        },
    },
    "POST /api/v1/incident/logs": {
        "description": "Ingesta logs crudos estructurados.",
        "parameters": {
            "raw_logs": {"type": "string", "required": True},
            "source": {"type": "string", "required": False, "default": "orchestrator"},
        },
    },
    "POST /api/v1/incident/metrics": {
        "description": "Ingesta métricas de infraestructura.",
        "parameters": {
            "metrics": {"type": "array", "required": True, "description": "Lista de {metric_name, value, timestamp, unit, source}."},
        },
    },
    "POST /api/v1/incident/validate": {
        "description": "Ejecuta validación temprana de datos batch.",
        "parameters": {
            "file_path": {"type": "string", "required": True},
            "expected_columns": {"type": "array", "required": False},
            "historical_counts": {"type": "array", "required": False},
        },
    },
    "POST /api/v1/incident/triage": {
        "description": "Delimita el impacto del incidente.",
        "parameters": {},
    },
    "POST /api/v1/incident/diagnose": {
        "description": "Identifica causas raíz.",
        "parameters": {},
    },
    "POST /api/v1/incident/mitigate": {
        "description": "Aplica mitigaciones y envía alertas.",
        "parameters": {},
    },
    "POST /api/v1/incident/reprocess": {
        "description": "Reprocesa archivo batch con chunking y checkpoints.",
        "parameters": {
            "file_path": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/incident/postmortem": {
        "description": "Genera reporte post-incidente con mejoras.",
        "parameters": {},
    },
    "POST /api/v1/incident/full-response": {
        "description": "Ejecuta ciclo completo de respuesta.",
        "parameters": {
            "title": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "severity": {"type": "string", "required": False, "default": "P1"},
            "raw_logs": {"type": "string", "required": True},
            "metrics": {"type": "array", "required": True},
            "file_path": {"type": "string", "required": True},
            "expected_columns": {"type": "array", "required": False},
            "historical_counts": {"type": "array", "required": False},
            "affected_partitions": {"type": "array", "required": False},
        },
    },
    "GET /api/v1/incident/status": {
        "description": "Estadísticas del motor.",
        "parameters": {},
    },
    "POST /api/v1/incident/reset": {
        "description": "Reinicia el motor con pipeline_id.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "config": {"type": "object", "required": False},
        },
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/incident/declare": {"fields": {"incident_id": "string", "severity": "string", "status": "string", "title": "string"}},
    "POST /api/v1/incident/logs": {"fields": {"ingested": "int", "total_logs": "int"}},
    "POST /api/v1/incident/metrics": {"fields": {"ingested": "int", "summary": "object"}},
    "POST /api/v1/incident/validate": {"fields": {"reports": "array", "all_passed": "boolean"}},
    "POST /api/v1/incident/triage": {"fields": {"incident_id": "string", "affected_partitions": "array", "error_logs": "int", "resource_findings": "array"}},
    "POST /api/v1/incident/diagnose": {"fields": {"incident_id": "string", "root_causes": "array"}},
    "POST /api/v1/incident/mitigate": {"fields": {"incident_id": "string", "mitigations": "array", "runbook_steps": "array"}},
    "POST /api/v1/incident/reprocess": {"fields": {"total_chunks": "int", "completed": "int", "failed": "int", "stats": "object"}},
    "POST /api/v1/incident/postmortem": {"fields": {"incident_id": "string", "postmortem": "object", "ansible_playbook": "string", "monitoring_config": "object"}},
    "POST /api/v1/incident/full-response": {"fields": {"trace_id": "string", "incident": "object", "postmortem": "object", "ansible_playbook": "string", "monitoring_config": "object", "duration_ms": "float"}},
    "GET /api/v1/incident/status": {"fields": {"pipeline_id": "string", "status": "string", "summary": "object"}},
    "POST /api/v1/incident/reset": {"fields": {"status": "string", "pipeline_id": "string"}},
}


def _to_metric_snapshots(metrics_data: List[Dict[str, Any]]) -> List[MetricSnapshot]:
    return [
        MetricSnapshot(
            timestamp=m.get("timestamp") or __import__("time").time(),
            metric_name=m["metric_name"],
            value=m["value"],
            unit=m.get("unit", ""),
            source=m.get("source", ""),
        )
        for m in metrics_data
    ]


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-083 Incident Response"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-083 — Incident Response & Resilient Batch Inference",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/incident/declare"},
            {"method": "POST", "path": "/api/v1/incident/logs"},
            {"method": "POST", "path": "/api/v1/incident/metrics"},
            {"method": "POST", "path": "/api/v1/incident/validate"},
            {"method": "POST", "path": "/api/v1/incident/triage"},
            {"method": "POST", "path": "/api/v1/incident/diagnose"},
            {"method": "POST", "path": "/api/v1/incident/mitigate"},
            {"method": "POST", "path": "/api/v1/incident/reprocess"},
            {"method": "POST", "path": "/api/v1/incident/postmortem"},
            {"method": "POST", "path": "/api/v1/incident/full-response"},
            {"method": "GET", "path": "/api/v1/incident/status"},
            {"method": "POST", "path": "/api/v1/incident/reset"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/incident/declare", methods=["POST"])
def declare():
    data = request.get_json(force=True)
    incident = _engine.declare_incident(
        title=data["title"],
        description=data["description"],
        severity=data.get("severity", "P1"),
        affected_partitions=data.get("affected_partitions"),
    )
    return jsonify(incident.to_dict())


@app.route("/api/v1/incident/logs", methods=["POST"])
def logs():
    data = request.get_json(force=True)
    _engine.ingest_logs(data.get("raw_logs", ""), source=data.get("source", "orchestrator"))
    return jsonify({"ingested": len(_engine.incident.logs) if _engine.incident else 0})


@app.route("/api/v1/incident/metrics", methods=["POST"])
def metrics():
    data = request.get_json(force=True)
    snapshots = _to_metric_snapshots(data.get("metrics", []))
    _engine.ingest_metrics(snapshots)
    return jsonify({"ingested": len(snapshots), "summary": _engine.metrics_analyzer.summary()})


@app.route("/api/v1/incident/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True)
    reports = _engine.validate_data(
        file_path=data["file_path"],
        expected_columns=data.get("expected_columns"),
        historical_counts=data.get("historical_counts"),
    )
    return jsonify({
        "reports": [r.to_dict() for r in reports],
        "all_passed": all(r.passed for r in reports),
    })


@app.route("/api/v1/incident/triage", methods=["POST"])
def triage():
    if not _engine.incident:
        return jsonify({"error": "no incident declared"}), 400
    return jsonify(_engine.triage())


@app.route("/api/v1/incident/diagnose", methods=["POST"])
def diagnose():
    if not _engine.incident:
        return jsonify({"error": "no incident declared"}), 400
    root_causes = _engine.diagnose()
    return jsonify({"incident_id": _engine.incident.incident_id, "root_causes": [r.to_dict() for r in root_causes]})


@app.route("/api/v1/incident/mitigate", methods=["POST"])
def mitigate():
    if not _engine.incident:
        return jsonify({"error": "no incident declared"}), 400
    mitigations = _engine.mitigate()
    return jsonify({
        "incident_id": _engine.incident.incident_id,
        "mitigations": [m.to_dict() for m in mitigations],
        "runbook_steps": _engine.incident.runbook_steps,
    })


@app.route("/api/v1/incident/reprocess", methods=["POST"])
def reprocess():
    if not _engine.incident:
        return jsonify({"error": "no incident declared"}), 400
    data = request.get_json(force=True)
    result = _engine.reprocess(data["file_path"])
    return jsonify(result)


@app.route("/api/v1/incident/postmortem", methods=["POST"])
def postmortem():
    if not _engine.incident:
        return jsonify({"error": "no incident declared"}), 400
    pm = _engine.generate_postmortem()
    return jsonify({
        "incident_id": _engine.incident.incident_id,
        "postmortem": pm.to_dict(),
        "ansible_playbook": _engine.ansible_generator.generate(
            _engine.incident.root_causes[0].category,
            _engine.pipeline_id,
            scale_memory_gb=8,
            scale_workers=6,
        ),
        "monitoring_config": _engine.monitoring_generator.generate_all(_engine.pipeline_id),
    })


@app.route("/api/v1/incident/full-response", methods=["POST"])
def full_response():
    data = request.get_json(force=True)
    required = ["title", "description", "raw_logs", "metrics", "file_path"]
    for r in required:
        if r not in data:
            return jsonify({"error": f"{r} is required"}), 400
    result = _engine.run_full_response(
        title=data["title"],
        description=data["description"],
        severity=data.get("severity", "P1"),
        raw_logs=data["raw_logs"],
        metrics=_to_metric_snapshots(data["metrics"]),
        file_path=data["file_path"],
        expected_columns=data.get("expected_columns"),
        historical_counts=data.get("historical_counts"),
        affected_partitions=data.get("affected_partitions"),
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/incident/status", methods=["GET"])
def status():
    return jsonify(_engine.get_statistics())


@app.route("/api/v1/incident/reset", methods=["POST"])
def reset():
    global _engine
    data = request.get_json(force=True)
    pipeline_id = data.get("pipeline_id", "trackprice_default")
    config = None
    if data.get("config"):
        config = IncidentResponseConfig(**data["config"])
    _engine = IncidentResponseEngine(pipeline_id=pipeline_id, config=config)
    return jsonify({"status": "reset", "pipeline_id": pipeline_id})


@app.route("/metrics", methods=["GET"])
def prometheus_metrics():
    return _engine.observability.export_prometheus(), 200, {"Content-Type": "text/plain"}


def run_server(port: int = 5083) -> None:
    print(f"UC-083 Incident Response API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
