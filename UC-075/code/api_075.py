"""
UC-075 — API REST Flask: Continuous Training Orchestrator.

Expone el orquestador como servicio REST con card views declarativas de
entrada/salida por endpoint (contrato auto-documentado).

Puerto por defecto: 5075
"""
from __future__ import annotations

import argparse
from typing import Any, Dict

from flask import Flask, jsonify, request

from continuous_training_orchestrator import ContinuousTrainingOrchestrator
from observability_075 import Observability075
from online_incremental_learner import OnlineLearnerPolicy

app = Flask(__name__)

_orchestrator: ContinuousTrainingOrchestrator = ContinuousTrainingOrchestrator(
    mlflow_enabled=False,  # JSONL fallback por defecto; activar con --mlflow-uri
)

# ==========================================================================
# CARD VIEW DE ENTRADA (parámetros del API REST)
# ==========================================================================
INPUT_CARDS: Dict[str, Any] = {
    "POST /api/v1/ct/scheduled": {
        "description": "Ejecuta la estrategia SCHEDULED si el ciclo está cumplido.",
        "parameters": {
            "agent_id": {"type": "string", "required": True},
            "interval_hours": {"type": "number", "required": False, "default": 168.0},
        },
    },
    "POST /api/v1/ct/event": {
        "description": "Evalúa métricas y, si superan umbrales, dispara EVENT_DRIVEN.",
        "parameters": {
            "agent_id": {"type": "string", "required": True},
            "metrics": {
                "type": "object",
                "required": True,
                "description": "drift_score, error_rate, latency_degradation_pct, "
                               "calibration_error, user_satisfaction, business_kpi_breach",
            },
            "domain": {"type": "string", "required": False, "default": "default"},
        },
    },
    "POST /api/v1/ct/on-demand": {
        "description": "Reentrenamiento bajo demanda ante cambio de negocio/política/datos.",
        "parameters": {
            "agent_id": {"type": "string", "required": True},
            "change_type": {"type": "string", "required": True,
                            "description": "product_change | policy_change | data_source_change | incident"},
            "detail": {"type": "string", "required": True},
            "new_data": {"type": "array", "required": False},
            "domain": {"type": "string", "required": False, "default": "default"},
            "estimated_cost_usd": {"type": "number", "required": False, "default": 0.0},
        },
    },
    "POST /api/v1/ct/incremental": {
        "description": "Mini-batch incremental con replay buffer anti-olvido.",
        "parameters": {
            "agent_id": {"type": "string", "required": True},
            "batch": {"type": "array", "required": True},
            "replay_buffer": {"type": "array", "required": True},
            "domain": {"type": "string", "required": False, "default": "default"},
        },
    },
    "POST /api/v1/ct/runs/<run_id>/resolve-hitl": {
        "description": "Resuelve un run PENDING_HITL con decisión humana (UC-290).",
        "parameters": {
            "approved": {"type": "boolean", "required": True},
            "approver": {"type": "string", "required": True},
            "review_notes": {"type": "string", "required": False},
        },
    },
    "GET /api/v1/ct/runs": {
        "description": "Lista runs (filtro opcional ?status=).",
        "parameters": {},
    },
    "GET /api/v1/ct/runs/<run_id>": {
        "description": "Detalle auditable de un run.",
        "parameters": {},
    },
    "GET /api/v1/ct/pending-hitl": {
        "description": "Runs esperando decisión humana.",
        "parameters": {},
    },
    "GET /api/v1/ct/status": {
        "description": "Estado global: presupuesto, campeones, auditoría, MLflow backend.",
        "parameters": {},
    },
    "GET /api/v1/ct/audit": {
        "description": "Cadena de auditoría inmutable (hash-chain).",
        "parameters": {},
    },
    "GET /api/v1/ct/metrics": {
        "description": "Métricas Prometheus (text exposition).",
        "parameters": {},
    },
    "GET /api/v1/ct/dashboard": {
        "description": "Dashboard JSON provisionable para Grafana.",
        "parameters": {},
    },
    "GET /api/v1/ct/loki": {
        "description": "Líneas JSON listas para push a Loki.",
        "parameters": {},
    },
    "POST /api/v1/ct/online-fit": {
        "description": "Aplica un micro-lote a un OnlineIncrementalLearner con Circuit Breaker.",
        "parameters": {
            "learner_id": {"type": "string", "required": True},
            "X": {"type": "array", "required": True, "description": "features del micro-lote"},
            "y": {"type": "array", "required": True, "description": "labels del micro-lote"},
            "model_type": {"type": "string", "required": False, "default": "mock",
                           "description": "mock | passthrough (para pruebas)"},
            "metadata": {"type": "object", "required": False},
        },
    },
    "GET /api/v1/ct/online-learners": {
        "description": "Estado de todos los OnlineIncrementalLearners.",
        "parameters": {},
    },
    "GET /api/v1/ct/online-learners/<learner_id>": {
        "description": "Detalle y cuarentena de un OnlineIncrementalLearner.",
        "parameters": {},
    },
    "regulated_model_selection": {
        "selected_model_id": "string",
        "selected_model_type": "interpretable|black_box|hybrid",
        "baseline_model_id": "string",
        "reason": "string",
        "regulatory_controls": "array<string>",
        "hitl_required": "boolean",
        "shadow_deployment_required": "boolean",
        "stakeholder_violations": "array<string>",
    },
    "explainability_report": {
        "passed": "boolean",
        "method": "lime|shap|permutation_surrogate|built-in",
        "requires_explanation": "boolean",
        "stability_score": "number",
        "coverage": "number",
        "faithfulness_score": "number",
        "top_features": "array",
        "violations": "array<string>",
    },
    "regulatory_policy": {
        "domain": "string",
        "required_controls": "array<string>",
        "min_auc": "number",
        "max_fpr": "number",
        "max_latency_ms": "number",
        "min_availability": "number",
    },
    "POST /api/v1/ct/regulatory/domain": {
        "description": "Configura dominio regulatorio (sector) y controles automáticos.",
        "parameters": {
            "domain": {"type": "string", "required": True,
                       "description": "healthcare|finance|insurance|critical_infrastructure_*|nuclear|industrial|general"},
            "custom_controls": {"type": "array", "required": False,
                                "description": "lista de RegulatoryControl opcional"},
        },
    },
    "POST /api/v1/ct/regulatory/stakeholder-requirement": {
        "description": "Registra un requisito innegociable de stakeholder.",
        "parameters": {
            "stakeholder": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "domain": {"type": "string", "required": False, "default": "general"},
            "category": {"type": "string", "required": False, "default": "explainability"},
            "constraints": {"type": "object", "required": False},
        },
    },
    "POST /api/v1/ct/regulatory/sign-off": {
        "description": "Firma un requisito de stakeholder.",
        "parameters": {
            "requirement_id": {"type": "string", "required": True},
            "signed_by": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/ct/regulatory/select-model": {
        "description": "Selecciona el modelo regulado adecuado (baseline interpretable first).",
        "parameters": {
            "candidates": {"type": "array", "required": True, "description": "lista de ModelCard"},
            "baseline": {"type": "object", "required": True, "description": "ModelCard baseline"},
        },
    },
    "POST /api/v1/ct/regulatory/explainability": {
        "description": "Evalúa explicabilidad de un ModelCard.",
        "parameters": {
            "model_card": {"type": "object", "required": True},
            "X_sample": {"type": "array", "required": False},
        },
    },
    "GET /api/v1/ct/regulatory/requirements": {
        "description": "Lista requisitos de stakeholders.",
        "parameters": {},
    },
    "POST /api/v1/ct/global/register-artifact": {
        "description": "Registra un artefacto en el GlobalMetadataStore.",
        "parameters": {
            "name": {"type": "string", "required": True},
            "artifact_type": {"type": "string", "required": True, "description": "model|dataset|checkpoint|metrics|config"},
            "region": {"type": "string", "required": True},
            "content": {"type": "string", "required": True, "description": "bytes en base64"},
            "jurisdictions": {"type": "array", "required": False},
            "replicate_to": {"type": "array", "required": False},
            "parent_artifact_ids": {"type": "array", "required": False},
        },
    },
    "GET /api/v1/ct/global/artifacts": {
        "description": "Lista artefactos globales; filtra por ?region= &type=.",
        "parameters": {},
    },
    "POST /api/v1/ct/global/replicate": {
        "description": "Replica un artefacto entre regiones.",
        "parameters": {
            "artifact_id": {"type": "string", "required": True},
            "source_region": {"type": "string", "required": True},
            "target_region": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/ct/global/detect-conflicts": {
        "description": "Detecta conflictos entre réplicas regionales.",
        "parameters": {},
    },
    "POST /api/v1/ct/global/resolve-conflict": {
        "description": "Resuelve un conflicto de réplica.",
        "parameters": {
            "artifact_id": {"type": "string", "required": True},
            "strategy": {"type": "string", "required": False, "default": "quorum"},
        },
    },
    "POST /api/v1/ct/global/lifecycle/gc": {
        "description": "Ejecuta garbage collection y tiering de artefactos.",
        "parameters": {},
    },
    "POST /api/v1/ct/global/lifecycle/legal-hold": {
        "description": "Aplica o libera legal hold sobre un artefacto.",
        "parameters": {
            "artifact_id": {"type": "string", "required": True},
            "region": {"type": "string", "required": True},
            "action": {"type": "string", "required": True, "description": "apply|release"},
        },
    },
    "POST /api/v1/ct/global/dr/backup": {
        "description": "Crea snapshot de backup del metadata store primario.",
        "parameters": {},
    },
    "POST /api/v1/ct/global/dr/failover": {
        "description": "Ejecuta failover al region secundaria.",
        "parameters": {},
    },
    "GET /api/v1/ct/global/dr/status": {
        "description": "Estado de recuperación ante desastres (RPO/RTO).",
        "parameters": {},
    },
    "GET /api/v1/ct/global/status": {
        "description": "Estadísticas del GlobalMetadataStore.",
        "parameters": {},
    },
    "POST /api/v1/ct/risk/register": {
        "description": "Registra un riesgo en el RiskRegister.",
        "parameters": {
            "category": {"type": "string", "required": True, "description": "data|model|agent|infrastructure|organizational|regulatory|security|business"},
            "subcategory": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "probability": {"type": "number", "required": True},
            "impact": {"type": "number", "required": True},
            "exposure": {"type": "number", "required": False, "default": 1.0},
            "control_effectiveness": {"type": "number", "required": False, "default": 0.0},
            "owner": {"type": "string", "required": False},
            "linked_run_ids": {"type": "array", "required": False},
            "linked_artifact_ids": {"type": "array", "required": False},
            "linked_agent_ids": {"type": "array", "required": False},
        },
    },
    "GET /api/v1/ct/risks": {
        "description": "Lista riesgos; filtros ?category= &status= &severity=.",
        "parameters": {},
    },
    "GET /api/v1/ct/risks/<risk_id>": {
        "description": "Detalle de un riesgo.",
        "parameters": {},
    },
    "POST /api/v1/ct/risks/<risk_id>/update": {
        "description": "Actualiza mitigaciones, efectividad y estado de un riesgo.",
        "parameters": {
            "mitigations": {"type": "array", "required": False},
            "control_effectiveness": {"type": "number", "required": False},
            "status": {"type": "string", "required": False, "description": "open|mitigated|accepted|transferred|closed|escalated"},
            "notes": {"type": "string", "required": False},
        },
    },
    "GET /api/v1/ct/risks/summary": {
        "description": "Resumen de riesgos por severidad y HITL requerido.",
        "parameters": {},
    },
    "GET /api/v1/ct/risks/proactive": {
        "description": "Próximos pasos proactivos y revisiones pendientes.",
        "parameters": {},
    },
    "GET /api/v1/ct/risks/runbook/<category>": {
        "description": "Runbook de respuesta para una categoría de riesgo.",
        "parameters": {},
    },
}

# ==========================================================================
# CARD VIEW DE SALIDA (respuesta del API REST)
# ==========================================================================
OUTPUT_CARDS: Dict[str, Any] = {
    "run": {
        "run_id": "string",
        "agent_id": "string",
        "status": "running|promoted|rejected|rolled_back|pending_hitl|blocked|failed",
        "strategy_used": "scheduled|event_driven|on_demand|incremental",
        "drift_score": "number",
        "trigger": {
            "strategy": "string", "reason": "string", "business_trigger": "string",
            "metrics": "object", "domain": "string", "estimated_cost_usd": "number",
        },
        "freeze": {
            "dataset_version": "string", "dataset_hash": "string",
            "n_records": "integer", "n_replay": "integer",
        },
        "gates": [
            {
                "gate": "drift_gate|champion_challenger_gate|security_fairness_gate|explainability_gate|hitl_gate|canary_gate",
                "verdict": "pass|fail|requires_hitl",
                "score": "number", "reason": "string", "evidence": "object",
            }
        ],
        "matchup": {
            "champion_version": "string", "candidate_version": "string",
            "champion_metrics": "object", "candidate_metrics": "object",
            "out_of_sample": "boolean", "candidate_wins": "boolean", "margin": "number",
        },
        "security_fairness": {
            "bias_detected": "boolean", "fairness_score": "number",
            "robustness_gap": "number", "backdoor_suspected": "boolean",
            "pii_in_training_data": "boolean", "violations": "array", "passed": "boolean",
        },
        "canary": {
            "candidate_version": "string", "traffic_ratio": "number",
            "duration_sec": "number", "error_rate": "number",
            "latency_p95_ms": "number", "baseline_latency_p95_ms": "number",
            "user_satisfaction": "number", "healthy": "boolean",
        },
        "approval": {
            "approved": "boolean", "approver": "string",
            "review_notes": "string", "approved_at": "number",
        },
        "decision": "promote|reject|rollback|escalate",
        "decision_reason": "string",
        "rollback_version": "string|null",
        "mlflow_run_id": "string",
        "actual_cost_usd": "number",
        "started_at": "number", "finished_at": "number|null", "error": "string",
    },
    "status": {
        "strategy_support": "array<string>",
        "budget": {
            "day": "string", "retrains_used": "integer", "retrains_cap": "integer",
            "cost_used_usd": "number", "cost_cap_usd": "number",
            "incremental_used": "integer", "incremental_cap": "integer",
        },
        "champions": "object",
        "mlflow": {"enabled": "boolean", "backend": "mlflow|jsonl"},
        "audit_records": "integer",
        "audit_chain_valid": "boolean",
        "runs_total": "integer",
        "pending_hitl": "integer",
        "online_learners": "object",
    },
    "online_microbatch": {
        "batch_id": "string",
        "learner_id": "string",
        "timestamp": "number",
        "integrity": {"passed": "boolean", "schema_errors": "array", "null_errors": "array",
                      "range_errors": "array", "n_rows": "integer"},
        "circuit_state_before": "closed|open|half_open",
        "circuit_state_after": "closed|open|half_open",
        "drift": {"accuracy_pre": "number", "accuracy_post": "number|null",
                  "drift_score": "number", "breached": "boolean"},
        "applied": "boolean",
        "reverted": "boolean",
        "quarantined": "boolean",
        "quarantine_reason": "string",
    },
    "regulated_model_selection": {
        "selected_model_id": "string",
        "selected_model_type": "interpretable|black_box|hybrid",
        "baseline_model_id": "string",
        "reason": "string",
        "regulatory_controls": "array<string>",
        "hitl_required": "boolean",
        "shadow_deployment_required": "boolean",
        "stakeholder_violations": "array<string>",
    },
    "explainability_report": {
        "passed": "boolean",
        "method": "lime|shap|permutation_surrogate|built-in",
        "requires_explanation": "boolean",
        "stability_score": "number",
        "coverage": "number",
        "faithfulness_score": "number",
        "top_features": "array",
        "violations": "array<string>",
    },
    "regulated_policy": {
        "domain": "string",
        "required_controls": "array<string>",
        "min_auc": "number",
        "max_fpr": "number",
        "max_latency_ms": "number",
        "min_availability": "number",
    },
    "global_artifact": {
        "artifact_id": "string",
        "artifact_type": "model|dataset|checkpoint|metrics|config",
        "name": "string",
        "version": "string",
        "region": "string",
        "checksum": "string",
        "status": "active|archived|deleted|legal_hold",
        "tier": "hot|warm|cold|glacier",
        "replication_regions": "array<string>",
        "lineage": "object",
    },
    "conflict_resolution": {
        "strategy": "string",
        "winner_region": "string|null",
        "winner_artifact": "global_artifact|null",
        "reason": "string",
        "requires_hitl": "boolean",
    },
    "dr_status": {
        "primary_region": "string",
        "failover_region": "string",
        "rpo_seconds": "number",
        "rto_seconds": "number",
        "rpo_ok": "boolean",
        "rpo_lag_seconds": "number",
        "failed_over": "boolean",
        "snapshots": "integer",
    },
    "risk": {
        "risk_id": "string",
        "category": "data|model|agent|infrastructure|organizational|regulatory|security|business",
        "subcategory": "string",
        "description": "string",
        "probability": "number",
        "impact": "number",
        "exposure": "number",
        "control_effectiveness": "number",
        "inherent_risk": "number",
        "residual_risk": "number",
        "severity": "critical|high|medium|low|negligible",
        "status": "open|mitigated|accepted|transferred|closed|escalated",
        "trend": "increasing|decreasing|stable",
        "owner": "string",
        "detected_at": "number",
        "review_due_at": "number",
        "linked_artifact_ids": "array<string>",
        "linked_run_ids": "array<string>",
        "linked_agent_ids": "array<string>",
        "trigger_event": "string",
        "trigger_details": "object",
        "mitigations": "array<string>",
        "auto_controls": "array<string>",
        "requires_hitl": "boolean",
        "requires_freeze": "boolean",
        "notes": "string",
    },
    "risk_summary": {
        "total_risks": "integer",
        "classification": {
            "total_risks": "integer",
            "by_severity": "object",
            "aggregate_residual_risk": "number",
            "max_residual_risk": "number",
        },
        "open_high_critical": "integer",
        "requires_hitl": "array<string>",
    },
    "proactive_risk_action": {
        "risk_id": "string",
        "category": "string",
        "severity": "string",
        "residual_risk": "number",
        "recommendation": "string",
        "review_due": "boolean",
        "owner": "string",
    },
    "runbook": {
        "name": "string",
        "steps": "array<string>",
        "auto_controls": "array<string>",
    },
}


# ==========================================================================
# Helpers
# ==========================================================================

def _body() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _ok(payload: Any, code: int = 200):
    return jsonify(payload), code


def _err(message: str, code: int = 400):
    return jsonify({"error": message}), code


# ==========================================================================
# Endpoints
# ==========================================================================

@app.get("/api/v1/health")
def health():
    return jsonify({"status": "ok", "service": "UC-075 Continuous Training Orchestrator"})


@app.get("/api/v1/cards")
def cards():
    """Card view de entrada y salida (contrato auto-documentado)."""
    return jsonify({
        "input_cards": INPUT_CARDS,
        "output_cards": OUTPUT_CARDS,
    })


@app.post("/api/v1/ct/scheduled")
def ct_scheduled():
    data = _body()
    agent_id = data.get("agent_id")
    if not agent_id:
        return _err("agent_id requerido")
    interval = float(data.get("interval_hours", 168.0))
    run = _orchestrator.check_scheduled(agent_id, interval)
    if run is None:
        return _ok({"status": "not_due", "reason": "Intervalo programado aún no cumplido."})
    return _ok(run.to_dict())


@app.post("/api/v1/ct/event")
def ct_event():
    data = _body()
    agent_id = data.get("agent_id")
    metrics = data.get("metrics")
    if not agent_id or not isinstance(metrics, dict):
        return _err("agent_id y metrics requeridos")
    run = _orchestrator.evaluate_metrics(
        agent_id, {k: float(v) for k, v in metrics.items()},
        domain=data.get("domain", "default"),
    )
    if run is None:
        return _ok({"status": "no_trigger", "reason": "Métricas dentro de umbrales."})
    return _ok(run.to_dict())


@app.post("/api/v1/ct/on-demand")
def ct_on_demand():
    data = _body()
    agent_id = data.get("agent_id")
    change_type = data.get("change_type")
    detail = data.get("detail")
    if not all([agent_id, change_type, detail]):
        return _err("agent_id, change_type y detail requeridos")
    run = _orchestrator.on_demand(
        agent_id,
        change_type,
        detail,
        new_data=data.get("new_data") or [],
        domain=data.get("domain", "default"),
        estimated_cost_usd=float(data.get("estimated_cost_usd", 0.0)),
    )
    return _ok(run.to_dict())


@app.post("/api/v1/ct/incremental")
def ct_incremental():
    data = _body()
    agent_id = data.get("agent_id")
    batch = data.get("batch") or []
    replay = data.get("replay_buffer") or []
    if not agent_id or not batch:
        return _err("agent_id y batch requeridos")
    run = _orchestrator.incremental_step(
        agent_id, batch, replay, domain=data.get("domain", "default"),
    )
    if run is None:
        return _ok({"status": "no_trigger", "reason": "Sin datos nuevos."})
    return _ok(run.to_dict())


@app.post("/api/v1/ct/runs/<run_id>/resolve-hitl")
def ct_resolve_hitl(run_id: str):
    data = _body()
    approved = bool(data.get("approved"))
    approver = data.get("approver")
    if not approver:
        return _err("approver requerido")
    run = _orchestrator.resolve_hitl(
        run_id, approved, approver, data.get("review_notes", ""),
    )
    if run is None:
        return _err("run no encontrado o no está pending_hitl", 404)
    return _ok(run.to_dict())


@app.get("/api/v1/ct/runs")
def ct_runs():
    status = request.args.get("status")
    return _ok({"runs": _orchestrator.list_runs(status=status)})


@app.get("/api/v1/ct/runs/<run_id>")
def ct_run_detail(run_id: str):
    run = _orchestrator.get_run(run_id)
    if run is None:
        return _err("run no encontrado", 404)
    return _ok(run)


@app.get("/api/v1/ct/pending-hitl")
def ct_pending_hitl():
    return _ok({"pending": _orchestrator.pending_hitl()})


@app.get("/api/v1/ct/status")
def ct_status():
    return _ok(_orchestrator.dashboard_state())


@app.get("/api/v1/ct/audit")
def ct_audit():
    return _ok({
        "records": _orchestrator.audit.list(),
        "chain_valid": _orchestrator.audit.verify_chain(),
    })


@app.get("/api/v1/ct/metrics")
def ct_metrics():
    text = _orchestrator.observability.export_prometheus()
    return text, 200, {"Content-Type": "text/plain; version=0.0.4"}


@app.get("/api/v1/ct/dashboard")
def ct_dashboard():
    return jsonify(Observability075.render_grafana_dashboard())


@app.get("/api/v1/ct/loki")
def ct_loki():
    return jsonify({"lines": _orchestrator.observability.to_loki_lines()})


# ---------------------------------------------------------------------------
# Online incremental learner endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ct/online-fit")
def ct_online_fit():
    data = _body()
    learner_id = data.get("learner_id")
    X = data.get("X")
    y = data.get("y")
    if not learner_id or X is None or y is None:
        return _err("learner_id, X e y requeridos")

    model_type = data.get("model_type", "mock")
    # Para tests/demo: modelos sintéticos in-memory.
    if model_type == "mock":
        from tests_075.test_online_incremental_learner import MockOnlineModel
        model = MockOnlineModel()
    elif model_type == "passthrough":
        from tests_075.test_online_incremental_learner import PassthroughModel
        model = PassthroughModel()
    else:
        return _err(f"model_type no soportado: {model_type}")

    policy_dict = data.get("policy") or {}
    policy = OnlineLearnerPolicy(**policy_dict)

    result = _orchestrator.online_fit(
        learner_id=learner_id,
        model=model,
        X=X,
        y=y,
        metadata=data.get("metadata"),
        policy=policy,
    )
    return _ok(result)


@app.get("/api/v1/ct/online-learners")
def ct_online_learners():
    return _ok({
        "learners": [
            learner.status() for learner in _orchestrator._online_learners.values()
        ]
    })


@app.get("/api/v1/ct/online-learners/<learner_id>")
def ct_online_learner_detail(learner_id: str):
    learner = _orchestrator.get_online_learner(learner_id)
    if learner is None:
        return _err("learner no encontrado", 404)
    return _ok({
        "status": learner.status(),
        "history": learner.get_history(),
        "quarantine": learner.get_quarantine(),
    })


# ---------------------------------------------------------------------------
# Regulatory governance endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ct/regulatory/domain")
def ct_regulatory_domain():
    data = _body()
    domain = data.get("domain")
    if not domain:
        return _err("domain requerido")
    try:
        from regulated_model_governance import RegulatoryDomain
        reg_domain = RegulatoryDomain(domain)
    except ValueError:
        return _err(f"dominio no válido: {domain}")
    custom = data.get("custom_controls") or []
    policy = _orchestrator.set_regulatory_domain(reg_domain, custom_controls=custom)
    return _ok(policy.to_dict())


@app.post("/api/v1/ct/regulatory/stakeholder-requirement")
def ct_stakeholder_requirement():
    data = _body()
    stakeholder = data.get("stakeholder")
    description = data.get("description")
    if not stakeholder or not description:
        return _err("stakeholder y description requeridos")
    req = _orchestrator.add_stakeholder_requirement(
        stakeholder=stakeholder,
        description=description,
        domain=data.get("domain", "general"),
        category=data.get("category", "explainability"),
        constraints=data.get("constraints") or {},
    )
    return _ok(req.to_dict())


@app.post("/api/v1/ct/regulatory/sign-off")
def ct_sign_off():
    data = _body()
    req_id = data.get("requirement_id")
    signed_by = data.get("signed_by")
    if not req_id or not signed_by:
        return _err("requirement_id y signed_by requeridos")
    for req in _orchestrator.stakeholder_requirements._reqs:
        if req.requirement_id == req_id:
            req.sign_off(signed_by)
            return _ok(req.to_dict())
    return _err("requirement_id no encontrado", 404)


@app.post("/api/v1/ct/regulatory/select-model")
def ct_select_model():
    data = _body()
    candidates = data.get("candidates") or []
    baseline = data.get("baseline")
    if not candidates or not baseline:
        return _err("candidates y baseline requeridos")
    return _ok(_orchestrator.select_regulated_model(candidates, baseline))


@app.post("/api/v1/ct/regulatory/explainability")
def ct_explainability():
    data = _body()
    card = data.get("model_card")
    X_sample = data.get("X_sample", [])
    if not card:
        return _err("model_card requerido")
    if _orchestrator.regulatory_policy is None:
        return _err("regulatory_domain no configurado")
    from regulated_model_governance import ExplainabilityGate, ModelCard, ModelType
    gate = ExplainabilityGate(policy=_orchestrator.regulatory_policy)
    model_card = ModelCard(
        model_id=card.get("model_id", "unknown"),
        model_type=ModelType(card.get("model_type", "black_box")),
        algorithm=card.get("algorithm", "unknown"),
        features=card.get("features", []),
        complexity_score=card.get("complexity_score", 0.9),
        metrics=card.get("metrics", {}),
        explanation_method=card.get("explanation_method", ""),
        explanation_report=card.get("explanation_report", {}),
    )
    report = gate.evaluate(model_card, X_sample)
    return _ok(report.to_dict())


@app.get("/api/v1/ct/regulatory/requirements")
def ct_regulatory_requirements():
    return _ok({"requirements": _orchestrator.stakeholder_requirements.list()})


# ---------------------------------------------------------------------------
# Global MLOps governance endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ct/global/register-artifact")
def ct_global_register_artifact():
    data = _body()
    name = data.get("name")
    atype = data.get("artifact_type")
    region = data.get("region")
    content_b64 = data.get("content")
    if not name or not atype or not region or content_b64 is None:
        return _err("name, artifact_type, region y content requeridos")
    import base64
    try:
        content = base64.b64decode(content_b64)
    except Exception:
        return _err("content debe ser base64 válido")
    from global_mlops_governance import ArtifactType
    try:
        artifact_type = ArtifactType(atype)
        reg = Region(region)
    except ValueError as exc:
        return _err(str(exc))
    result = _orchestrator.register_global_artifact(
        name=name,
        artifact_type=artifact_type,
        region=reg,
        content=content,
        jurisdictions=data.get("jurisdictions") or [],
        replicate_to=data.get("replicate_to") or [],
        parent_artifact_ids=data.get("parent_artifact_ids") or [],
    )
    return _ok(result)


@app.get("/api/v1/ct/global/artifacts")
def ct_global_artifacts():
    from global_mlops_governance import ArtifactType
    region = request.args.get("region")
    atype = request.args.get("type")
    region_obj = Region(region) if region else None
    atype_obj = ArtifactType(atype) if atype else None
    return _ok({"artifacts": _orchestrator.global_metadata.list_artifacts(region_obj, atype_obj)})


@app.post("/api/v1/ct/global/replicate")
def ct_global_replicate():
    data = _body()
    aid = data.get("artifact_id")
    src = data.get("source_region")
    tgt = data.get("target_region")
    if not aid or not src or not tgt:
        return _err("artifact_id, source_region y target_region requeridos")
    return _ok(_orchestrator.replicate_artifact(aid, src, tgt))


@app.post("/api/v1/ct/global/detect-conflicts")
def ct_global_detect_conflicts():
    return _ok({"conflicts": _orchestrator.detect_global_conflicts()})


@app.post("/api/v1/ct/global/resolve-conflict")
def ct_global_resolve_conflict():
    data = _body()
    aid = data.get("artifact_id")
    strategy = data.get("strategy", "quorum")
    if not aid:
        return _err("artifact_id requerido")
    return _ok(_orchestrator.resolve_global_conflict(aid, strategy))


@app.post("/api/v1/ct/global/lifecycle/gc")
def ct_global_lifecycle_gc():
    return _ok(_orchestrator.run_lifecycle_gc())


@app.post("/api/v1/ct/global/lifecycle/legal-hold")
def ct_global_legal_hold():
    data = _body()
    aid = data.get("artifact_id")
    region = data.get("region")
    action = data.get("action")
    if not aid or not region or action not in ("apply", "release"):
        return _err("artifact_id, region y action (apply|release) requeridos")
    store = _orchestrator.global_metadata._regions.get(Region(region))
    if store is None:
        return _err("region no encontrada", 404)
    ok = (
        _orchestrator.lifecycle_manager.apply_legal_hold(store, aid)
        if action == "apply"
        else _orchestrator.lifecycle_manager.release_legal_hold(store, aid)
    )
    return _ok({"applied": ok})


@app.post("/api/v1/ct/global/dr/backup")
def ct_global_dr_backup():
    return _ok(_orchestrator.backup_global_metadata())


@app.post("/api/v1/ct/global/dr/failover")
def ct_global_dr_failover():
    return _ok(_orchestrator.failover_global_metadata())


@app.get("/api/v1/ct/global/dr/status")
def ct_global_dr_status():
    return _ok(_orchestrator.dr_status())


@app.get("/api/v1/ct/global/status")
def ct_global_status():
    return _ok(_orchestrator.global_mlops_status())


# ---------------------------------------------------------------------------
# Risk management endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ct/risk/register")
def ct_risk_register():
    data = _body()
    required = ["category", "subcategory", "description", "probability", "impact"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    return _ok(_orchestrator.register_risk(
        category=data["category"],
        subcategory=data["subcategory"],
        description=data["description"],
        probability=float(data["probability"]),
        impact=float(data["impact"]),
        exposure=float(data.get("exposure", 1.0)),
        control_effectiveness=float(data.get("control_effectiveness", 0.0)),
        owner=data.get("owner", ""),
        linked_run_ids=data.get("linked_run_ids"),
        linked_artifact_ids=data.get("linked_artifact_ids"),
        linked_agent_ids=data.get("linked_agent_ids"),
    ))


@app.get("/api/v1/ct/risks")
def ct_risks():
    return _ok({"risks": _orchestrator.list_risks(
        category=request.args.get("category"),
        status=request.args.get("status"),
        severity=request.args.get("severity"),
    )})


@app.get("/api/v1/ct/risks/<risk_id>")
def ct_risk_detail(risk_id: str):
    risk = _orchestrator.get_risk(risk_id)
    if risk is None:
        return _err("riesgo no encontrado", 404)
    return _ok(risk)


@app.post("/api/v1/ct/risks/<risk_id>/update")
def ct_risk_update(risk_id: str):
    data = _body()
    risk = _orchestrator.update_risk(
        risk_id=risk_id,
        mitigations=data.get("mitigations"),
        control_effectiveness=data.get("control_effectiveness"),
        status=data.get("status"),
        notes=data.get("notes", ""),
    )
    if risk is None:
        return _err("riesgo no encontrado", 404)
    return _ok(risk)


@app.get("/api/v1/ct/risks/summary")
def ct_risk_summary():
    return _ok(_orchestrator.risk_summary())


@app.get("/api/v1/ct/risks/proactive")
def ct_risk_proactive():
    return _ok({"actions": _orchestrator.proactive_risk_actions()})


@app.get("/api/v1/ct/risks/runbook/<category>")
def ct_risk_runbook(category: str):
    return _ok(_orchestrator.risk_runbook(category))


def main() -> None:
    parser = argparse.ArgumentParser(description="UC-075 Continuous Training Orchestrator API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5075)
    parser.add_argument("--mlflow-uri", default=None,
                        help="Si se pasa e mlflow está instalado, usa MLflow real.")
    args = parser.parse_args()

    global _orchestrator
    if args.mlflow_uri:
        _orchestrator = ContinuousTrainingOrchestrator(
            mlflow_tracking_uri=args.mlflow_uri, mlflow_enabled=True,
        )
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
