"""
Codificando.AI - UC-127
API Flask que expone el pipeline de orquestación de respuesta a incidentes
de LLMOps: ingesta de alertas/telemetría, ejecución de playbooks
codificados, aprobación humana (HITL), reversión (rollback), cierre con
post-mortem, simulacros de Game Day y salud de los SOP.

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/incidents  (parámetros de ENTRADA)
────────────────────────────────────────────────────────────────────────
┌───────────────────────┬──────────┬───────────┬────────────────────────┐
│ Campo                 │ Tipo     │ Requerido │ Descripción            │
├───────────────────────┼──────────┼───────────┼────────────────────────┤
│ model                 │ string   │ sí        │ Nombre del modelo LLM  │
│ model_version         │ string   │ no        │ Versión desplegada     │
│ hallucination_rate    │ float    │ no        │ 0.0 - 1.0              │
│ guardrail_blocked_ratio│ float   │ no        │ 0.0 - 1.0              │
│ evasion_attempts_per_min│ float  │ no        │ Intentos/min           │
│ pii_leak_events       │ int      │ no        │ Nº de eventos de PII   │
│ quality_score         │ float    │ no        │ 0.0 - 1.0              │
│ tool_error_rate       │ float    │ no        │ 0.0 - 1.0              │
│ latency_p99_s         │ float    │ no        │ Segundos               │
│ error_rate            │ float    │ no        │ 0.0 - 1.0              │
│ cost_increase_ratio   │ float    │ no        │ 0.0 - N (vs. baseline) │
│ toxicity_score        │ float    │ no        │ 0.0 - 1.0              │
│ correlation_id        │ string   │ no        │ ID de traza/request    │
│ incident_type         │ string   │ no*       │ Fuerza el tipo (bypass)│
│ severity              │ string   │ no*       │ Fuerza la severidad    │
└───────────────────────┴──────────┴───────────┴────────────────────────┘
* Si se proveen `incident_type` y `severity` explícitos, se omite la
  clasificación automática por métricas. Debe enviarse al menos una
  métrica o el par (`incident_type`, `severity`).

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/incidents  (parámetros de SALIDA)
────────────────────────────────────────────────────────────────────────
┌───────────────────────┬──────────┬────────────────────────────────────┐
│ Campo                 │ Tipo     │ Descripción                        │
├───────────────────────┼──────────┼────────────────────────────────────┤
│ incident_id           │ string   │ ID único del incidente (UUID)      │
│ status                │ string   │ DETECTED/RUNNING_PLAYBOOK/         │
│                       │          │ PENDING_APPROVAL/REMEDIATED/       │
│                       │          │ ROLLED_BACK/FAILED/CLOSED          │
│ playbook_name         │ string   │ Playbook codificado seleccionado   │
│ alert                 │ object   │ Alerta clasificada (tipo/severidad)│
│ actions               │ array    │ Pasos ejecutados y su resultado    │
│ mttr_seconds          │ float    │ Tiempo medio de remediación        │
│ recurrence_count_7d   │ int      │ Recurrencia del tipo en 7 días     │
│ rolled_back           │ bool     │ Si se aplicó reversión             │
│ created_at/updated_at │ string   │ Timestamps ISO-8601 UTC            │
└───────────────────────┴──────────┴────────────────────────────────────┘
"""

import logging
from typing import Any, Dict

from flask import Flask, jsonify, request, Response

from chaos_engineering import CHAOS_SCENARIOS, ChaosDrillRunner
from classifier import IncidentClassifier
from config import CONFIG, PREDEFINED_ROOT_CAUSES
from incident_types import IncidentAlert, IncidentType, Severity
from logging_utils import configure_logging
from orchestrator import IncidentResponseOrchestrator
import prometheus_metrics as pm
from sop_registry import SOP_REGISTRY

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

classifier = IncidentClassifier()
orchestrator = IncidentResponseOrchestrator()
chaos_runner = ChaosDrillRunner(orchestrator)


@app.route("/health", methods=["GET"])
def health() -> Response:
    return jsonify({
        "status": "ok",
        "playbooks_loaded": [p.name for p in orchestrator.playbook_loader.list_playbooks()],
        "hitl_enabled": CONFIG.hitl.enabled,
        "integrations_dry_run": CONFIG.integrations.dry_run,
    }), 200


@app.route("/api/v1/incidents", methods=["POST"])
def create_incident() -> Response:
    """Ingesta una alerta/telemetría y ejecuta el pipeline completo de
    respuesta a incidentes (clasificación -> playbook -> integraciones)."""
    data: Dict[str, Any] = request.get_json(silent=True) or {}

    if data.get("incident_type") and data.get("severity"):
        try:
            alert = IncidentAlert(
                incident_type=IncidentType(data["incident_type"]),
                severity=Severity(data["severity"]),
                model=data.get("model", "unknown"),
                model_version=data.get("model_version"),
                summary=data.get("summary", ""),
                source=data.get("source", "manual"),
                metrics=data.get("metrics", {}),
                correlation_id=data.get("correlation_id"),
            )
        except ValueError as e:
            return jsonify({"error": f"incident_type/severity inválidos: {e}"}), 400
    else:
        alert = classifier.classify_from_metrics(
            model=data.get("model", "unknown"),
            model_version=data.get("model_version"),
            hallucination_rate=data.get("hallucination_rate"),
            guardrail_blocked_ratio=data.get("guardrail_blocked_ratio"),
            evasion_attempts_per_min=data.get("evasion_attempts_per_min"),
            pii_leak_events=data.get("pii_leak_events"),
            quality_score=data.get("quality_score"),
            tool_error_rate=data.get("tool_error_rate"),
            latency_p99_s=data.get("latency_p99_s"),
            error_rate=data.get("error_rate"),
            cost_increase_ratio=data.get("cost_increase_ratio"),
            toxicity_score=data.get("toxicity_score"),
            correlation_id=data.get("correlation_id"),
        )
        if alert is None:
            return jsonify({"error": "Ninguna métrica superó los umbrales de detección de incidente"}), 400

    incident = orchestrator.handle_alert(alert)
    return jsonify(incident.to_dict()), 201


@app.route("/api/v1/alertmanager/webhook", methods=["POST"])
def alertmanager_webhook() -> Response:
    """Webhook estándar de Prometheus Alertmanager / Grafana. Traduce las
    alertas reconocidas (ver `config.ALERT_NAME_TO_INCIDENT_TYPE`) en
    incidentes y ejecuta el pipeline de respuesta."""
    payload = request.get_json(silent=True) or {}
    alert = classifier.classify_from_alertmanager(payload)
    if alert is None:
        return jsonify({"status": "ignored", "reason": "alerta no reconocida por UC-127"}), 202

    incident = orchestrator.handle_alert(alert)
    return jsonify(incident.to_dict()), 201


@app.route("/api/v1/incidents", methods=["GET"])
def list_incidents() -> Response:
    incident_type_param = request.args.get("incident_type")
    incident_type = IncidentType(incident_type_param) if incident_type_param else None
    incidents = orchestrator.list_incidents(incident_type=incident_type)
    return jsonify([i.to_dict() for i in incidents]), 200


@app.route("/api/v1/incidents/<incident_id>", methods=["GET"])
def get_incident(incident_id: str) -> Response:
    incident = orchestrator.get_incident(incident_id)
    if incident is None:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(incident.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/approve", methods=["POST"])
def approve_incident(incident_id: str) -> Response:
    """Aprueba o rechaza la acción de alto impacto pendiente (HITL)."""
    data = request.get_json(silent=True) or {}
    approved = bool(data.get("approved", False))
    approver = data.get("approver", "unknown")
    comment = data.get("comment")

    try:
        incident = orchestrator.approve_pending_action(incident_id, approved, approver, comment)
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    return jsonify(incident.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/rollback", methods=["POST"])
def rollback_incident(incident_id: str) -> Response:
    data = request.get_json(silent=True) or {}
    try:
        incident = orchestrator.rollback_incident(incident_id, reason=data.get("reason", ""))
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(incident.to_dict()), 200


@app.route("/api/v1/incidents/<incident_id>/close", methods=["POST"])
def close_incident(incident_id: str) -> Response:
    """Cierre con post-mortem: causa raíz, efectividad del playbook y
    notas — alimenta el ciclo de actualización continua de SOPs."""
    data = request.get_json(silent=True) or {}
    root_cause = data.get("root_cause", "unknown")
    if root_cause not in PREDEFINED_ROOT_CAUSES:
        return jsonify({"error": f"root_cause inválida. Use una de: {PREDEFINED_ROOT_CAUSES}"}), 400

    try:
        incident = orchestrator.close_incident(
            incident_id,
            root_cause=root_cause,
            playbook_effective=bool(data.get("playbook_effective", True)),
            postmortem_notes=data.get("postmortem_notes"),
        )
    except KeyError:
        return jsonify({"error": "Incidente no encontrado"}), 404
    return jsonify(incident.to_dict()), 200


@app.route("/api/v1/playbooks", methods=["GET"])
def list_playbooks() -> Response:
    playbooks = orchestrator.playbook_loader.list_playbooks()
    return jsonify([
        {
            "name": p.name,
            "incident_type": p.incident_type.value,
            "description": p.description,
            "trigger_description": p.trigger_description,
            "steps": [s.name for s in p.steps],
        }
        for p in playbooks
    ]), 200


@app.route("/api/v1/sops", methods=["GET"])
def list_sops() -> Response:
    """Salud de los SOP (panel 'Salud del SOP (Wiki.js)' del dashboard)."""
    sops = SOP_REGISTRY.list_sops()
    return jsonify([
        {**s.to_dict(), "days_since_update": s.days_since_update(),
         "stale": (s.days_since_update() or 0) > CONFIG.thresholds.sop_stale_days if s.last_updated_at else None}
        for s in sops
    ]), 200


@app.route("/api/v1/chaos/scenarios", methods=["GET"])
def list_chaos_scenarios() -> Response:
    return jsonify(list(CHAOS_SCENARIOS.keys())), 200


@app.route("/api/v1/chaos/run", methods=["POST"])
def run_chaos_drill() -> Response:
    """Ejecuta uno o todos los simulacros de Game Day (ver
    `chaos_engineering.py`)."""
    data = request.get_json(silent=True) or {}
    scenario = data.get("scenario")

    try:
        if scenario:
            results = [chaos_runner.run_scenario(scenario)]
        else:
            results = chaos_runner.run_all()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify([r.to_dict() for r in results]), 200


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
    port = int(os.getenv("APP_PORT", "8001"))
    app.run(host="0.0.0.0", port=port, debug=False)
