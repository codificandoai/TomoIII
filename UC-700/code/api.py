"""UC-700 — API REST Flask para el pipeline de autosanación avanzada.

Endpoints:
  GET  /health
  GET  /api/v1/agents
  POST /api/v1/telemetry/ingest
  POST /api/v1/diagnose
  POST /api/v1/remediate
  GET  /api/v1/incidents
  GET  /api/v1/incidents/<id>
  POST /api/v1/simulate
  GET  /api/v1/metrics
  GET  /api/v1/dashboards
  GET  /api/v1/schema
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

from config import AgentConfig
from grafana_dashboards import build_dashboard, write_dashboards
from models import Device, Node, TrainingJob
from orchestrator import SelfHealingOrchestrator
from prometheus_metrics import CONTENT_TYPE_LATEST, UC700Metrics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc700-api")

app = Flask(__name__)

# Instancia singleton del orquestador
orchestrator = SelfHealingOrchestrator(config=AgentConfig(), dry_run=True)
orchestrator.build_default_cluster()
metrics = UC700Metrics()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _ok(data: Any, status: int = 200):
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat(), "data": data}), status


def _err(message: str, status: int = 400):
    return jsonify({"status": "error", "message": message}), status


def _incident_to_dict(incident: Any) -> Dict[str, Any]:
    d = asdict(incident)
    d["created_at"] = d["created_at"].isoformat() if hasattr(d["created_at"], "isoformat") else d["created_at"]
    d["resolved_at"] = d["resolved_at"].isoformat() if d.get("resolved_at") else None
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Card Views de esquema de API
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/telemetry/ingest",
        "description": "Ingesta telemetría de nodo/dispositivo.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "N-R-A-1"},
            {"name": "device_id", "type": "string", "required": False, "example": "N-R-A-1-gpu-0"},
            {"name": "metrics", "type": "object", "required": True, "example": {"DCGM_FI_DEV_GPU_TEMP": 92.0, "DCGM_FI_DEV_XID_ERRORS": 8.0}},
            {"name": "events", "type": "list[string]", "required": False, "example": ["dcgm_xid_memory_error"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/diagnose",
        "description": "Ejecuta detección y diagnóstico sobre un nodo.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "N-R-A-1"},
            {"name": "inject_failure", "type": "boolean", "required": False, "example": True},
            {"name": "device_id", "type": "string", "required": False, "example": "N-R-A-1-gpu-0"},
        ],
    },
    {
        "endpoint": "POST /api/v1/remediate",
        "description": "Ejecuta el pipeline completo de autosanación.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "N-R-A-1"},
            {"name": "device_id", "type": "string", "required": False, "example": "N-R-A-1-gpu-0"},
            {"name": "inject_failure", "type": "boolean", "required": False, "example": True},
            {"name": "operator_id", "type": "string", "required": False, "example": "sre-001"},
        ],
    },
    {
        "endpoint": "POST /api/v1/simulate",
        "description": "Simula un escenario de fallo de memoria GPU y retorna incidente.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "N-R-A-1"},
            {"name": "operator_id", "type": "string", "required": False, "example": "sre-001"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "GET /api/v1/incidents/<id>",
        "description": "Detalle de un incidente de autosanación.",
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "node_id", "type": "string"},
            {"name": "severity", "type": "string", "enum": ["S0", "S1", "S2", "S3", "S4"]},
            {"name": "failure_class", "type": "string"},
            {"name": "state", "type": "string"},
            {"name": "diagnosis", "type": "object"},
            {"name": "impact", "type": "object"},
            {"name": "plan", "type": "object"},
            {"name": "validation", "type": "object"},
            {"name": "efficiency", "type": "object"},
            {"name": "escalated", "type": "boolean"},
            {"name": "trace", "type": "list"},
        ],
    },
    {
        "endpoint": "POST /api/v1/diagnose",
        "description": "Resultado de diagnóstico.",
        "fields": [
            {"name": "anomaly_score", "type": "float"},
            {"name": "severity", "type": "string"},
            {"name": "failure_class", "type": "string"},
            {"name": "confidence", "type": "float"},
            {"name": "evidence", "type": "list"},
            {"name": "suspected_devices", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus para scraping.",
        "fields": [
            {"name": "content", "type": "text/plain", "note": "Expone uc700_* metrics"},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc700-self-healing", "mode": "dry-run"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/agents", methods=["GET"])
def list_agents():
    return _ok({
        "agents": [
            "TelemetryCollector",
            "AnomalyDetectionAgent",
            "DiagnosticAgent",
            "ImpactAnalysisAgent",
            "IsolationAgent",
            "CheckpointManager",
            "RemediationOrchestrator",
            "ValidationAgent",
            "EfficiencyAgent",
            "EscalationAgent",
            "GovernanceAgent",
        ]
    })


@app.route("/api/v1/telemetry/ingest", methods=["POST"])
def ingest_telemetry():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id")
    if not node_id:
        return _err("node_id is required")
    node = orchestrator.topology.nodes.get(node_id)
    if not node:
        return _err(f"node {node_id} not found", 404)

    from models import TelemetrySnapshot
    snapshot = TelemetrySnapshot(
        node_id=node_id,
        device_id=payload.get("device_id"),
        timestamp=datetime.utcnow(),
        metrics=payload.get("metrics", {}),
        events=payload.get("events", []),
        source=payload.get("source", "api"),
    )
    orchestrator.anomaly.ingest(snapshot)
    signal = orchestrator.anomaly.detect(snapshot)
    return _ok({"ingested": True, "anomaly": signal.__dict__ if signal else None})


@app.route("/api/v1/diagnose", methods=["POST"])
def diagnose():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id")
    if not node_id:
        return _err("node_id is required")
    node = orchestrator.topology.nodes.get(node_id)
    if not node:
        return _err(f"node {node_id} not found", 404)

    device_id = payload.get("device_id")
    device = next((d for d in node.devices if d.id == device_id), None) if device_id else None
    inject = bool(payload.get("inject_failure", False))
    snapshot = orchestrator.telemetry.collect_node(node, device=device, inject_failure=inject)
    if inject:
        snapshot = orchestrator.telemetry.inject_memory_failure_signature(snapshot)
    signal = orchestrator.anomaly.detect(snapshot)
    if not signal:
        return _ok({"anomaly_score": None, "severity": None, "failure_class": None, "message": "no anomaly detected"})

    diagnosis = orchestrator.diagnostic.diagnose(node, snapshot, signal)
    severity = orchestrator.anomaly.classify_severity(signal)
    return _ok({
        "anomaly_score": signal.score,
        "severity": severity,
        "failure_class": diagnosis.failure_class,
        "confidence": diagnosis.confidence,
        "evidence": diagnosis.evidence,
        "suspected_devices": diagnosis.suspected_devices,
    })


@app.route("/api/v1/remediate", methods=["POST"])
def remediate():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id")
    if not node_id:
        return _err("node_id is required")
    device_id = payload.get("device_id")
    inject = bool(payload.get("inject_failure", False))
    operator_id = payload.get("operator_id")

    incident = orchestrator.run_pipeline(
        node_id=node_id,
        device_id=device_id,
        inject_failure=inject,
        operator_id=operator_id,
    )
    metrics.record_incident(incident.severity, incident.failure_class, incident.impact.scope if incident.impact else "unknown")
    metrics.record_incident_state(incident.id, incident.node_id, incident.severity, active=incident.state not in ("CLOSED", "ESCALATED"))
    if incident.efficiency:
        job_id = orchestrator.topology.jobs.get(incident.plan.affected_jobs[0]).id if incident.plan and incident.plan.affected_jobs else "unknown"
        metrics.record_efficiency(job_id, incident.efficiency.get("efficiency_pct", 0.0))
    return _ok(_incident_to_dict(incident))


@app.route("/api/v1/incidents", methods=["GET"])
def list_incidents():
    return _ok([_incident_to_dict(i) for i in orchestrator.list_incidents()])


@app.route("/api/v1/incidents/<incident_id>", methods=["GET"])
def get_incident(incident_id: str):
    incident = orchestrator.get_incident(incident_id)
    if not incident:
        return _err(f"incident {incident_id} not found", 404)
    return _ok(_incident_to_dict(incident))


@app.route("/api/v1/simulate", methods=["POST"])
def simulate():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id", "N-R-A-1")
    operator_id = payload.get("operator_id")
    incident = orchestrator.run_pipeline(
        node_id=node_id,
        device_id=f"{node_id}-gpu-0",
        inject_failure=True,
        operator_id=operator_id,
    )
    metrics.record_incident(incident.severity, incident.failure_class, incident.impact.scope if incident.impact else "unknown")
    if incident.efficiency:
        job_id = orchestrator.topology.jobs.get(incident.plan.affected_jobs[0]).id if incident.plan and incident.plan.affected_jobs else "unknown"
        metrics.record_efficiency(job_id, incident.efficiency.get("efficiency_pct", 0.0))
    return _ok({"scenario": "gpu_memory_failure", "incident": _incident_to_dict(incident)})


@app.route("/api/v1/metrics", methods=["GET"])
def prometheus_metrics():
    return metrics.render(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/api/v1/dashboards", methods=["GET"])
def list_dashboards():
    return _ok({
        "dashboards": [
            {"name": "uc700-overview", "title": "UC-700 Self-Healing Training Overview"},
            {"name": "uc700-training-health", "title": "UC-700 Training Health & Checkpoints"},
        ],
        "rendered_paths": write_dashboards(os.path.join(os.path.dirname(__file__), "dashboards")),
    })


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    port = int(os.environ.get("UC700_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
