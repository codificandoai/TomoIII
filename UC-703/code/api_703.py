"""
UC-703 — API REST Flask con card views de entrada/salida.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_runtime_orchestrator import AgentRuntimeOrchestrator
from fine_tuning.controller import FineTuningController
from fine_tuning.models_ft import FeedbackItem
from fine_tuning.privacy.models_privacy import DataContract, DPTrainingConfig, NetworkPolicy
from fine_tuning.privacy.privacy_controller import PrivacyPreservingLLMOpsController
from fine_tuning.quality_gate.models_quality import QualitativeReview
from fine_tuning.quality_gate.quality_gate_controller import QualityGateController
from fine_tuning.extrinsic_metrics.extrinsic_metrics_controller import ExtrinsicMetricsController
from fine_tuning.evaluation_matrix.evaluation_matrix_controller import EvaluationMatrixController
from fine_tuning.evaluation_matrix.models_cem import HumanReview
from resilience.recovery_orchestrator import RecoveryOrchestrator
from compliance_as_code.compliance_controller import ComplianceController
from continuous_improvement.continuous_improvement_controller import ContinuousImprovementController
from enterprise_qa.models_qa import TestCase
from enterprise_qa.qa_driver import EnterpriseQADriver
from incident_management.incident_management_controller import IncidentManagementController

# Preferir Flask local si existe, sino mock mínimo.
try:
    from flask import Flask, jsonify, request
except Exception as exc:  # pragma: no cover
    print(f"Flask no disponible: {exc}")
    sys.exit(1)


app = Flask(__name__)
_orchestrator: Optional[AgentRuntimeOrchestrator] = None
_ft_controller: Optional[FineTuningController] = None
_em_controller: Optional[ExtrinsicMetricsController] = None
_cem_controller: Optional[EvaluationMatrixController] = None
_recovery_controller: Optional[RecoveryOrchestrator] = None
_cac_controller: Optional[ComplianceController] = None
_ci_controller: Optional[ContinuousImprovementController] = None
_qa_driver: Optional[EnterpriseQADriver] = None
_incident_controller: Optional[IncidentManagementController] = None


def _body() -> Dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return {}


def _ok(payload: Any, status: int = 200):
    return jsonify({"status": "ok", "data": payload}), status


def _err(message: str, status: int = 400):
    return jsonify({"status": "error", "error": message}), status


# ---------------------------------------------------------------------------
# Card views
# ---------------------------------------------------------------------------

INPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/objective": {
        "description": "Crea un nuevo objetivo para el runtime AGI.",
        "parameters": {
            "description": {"type": "string", "required": True},
            "agent_id": {"type": "string", "required": False, "default": ""},
            "tenant_id": {"type": "string", "required": False, "default": ""},
            "requested_by": {"type": "string", "required": False, "default": ""},
            "context": {"type": "object", "required": False, "default": {}},
        },
    },
    "POST /api/v1/objective/<task_id>/plan": {
        "description": "Genera un plan para el objetivo (pensar + recordar).",
        "parameters": {},
    },
    "POST /api/v1/objective/<task_id>/approve": {
        "description": "Aprueba todos los pasos del plan según política.",
        "parameters": {},
    },
    "POST /api/v1/objective/<task_id>/approve/<step_id>": {
        "description": "Aprueba un paso concreto (scope: auto|hitl).",
        "parameters": {
            "scope": {"type": "string", "required": False, "default": "auto"},
        },
    },
    "POST /api/v1/objective/<task_id>/execute": {
        "description": "Ejecuta el plan aprobado en el backend correspondiente.",
        "parameters": {},
    },
    "POST /api/v1/objective/<task_id>/pause": {
        "description": "Pausa la ejecución de la tarea.",
        "parameters": {},
    },
    "POST /api/v1/objective/<task_id>/resume": {
        "description": "Reanuda una tarea pausada.",
        "parameters": {},
    },
    "POST /api/v1/objective/<task_id>/cancel": {
        "description": "Cancela la tarea.",
        "parameters": {},
    },
    "POST /api/v1/temporal/workflow": {
        "description": "Crea un workflow Temporal directamente.",
        "parameters": {
            "activities": {"type": "array", "required": True},
            "workflow_id": {"type": "string", "required": False},
            "task_queue": {"type": "string", "required": False, "default": "uc703-default"},
            "context": {"type": "object", "required": False, "default": {}},
        },
    },
    "POST /api/v1/temporal/workflow/<workflow_id>/run": {
        "description": "Ejecuta un workflow Temporal.",
        "parameters": {},
    },
    "POST /api/v1/temporal/workflow/<workflow_id>/signal": {
        "description": "Envía señal a un workflow Temporal.",
        "parameters": {
            "signal": {"type": "string", "required": True},
            "payload": {"type": "any", "required": False},
        },
    },
    "POST /api/v1/stackstorm/execute": {
        "description": "Ejecuta un playbook de StackStorm con approval_ref.",
        "parameters": {
            "playbook": {"type": "string", "required": True},
            "params": {"type": "object", "required": False, "default": {}},
            "approval_ref": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/n8n/execute": {
        "description": "Ejecuta un workflow de n8n con approval_ref.",
        "parameters": {
            "workflow_id": {"type": "string", "required": True},
            "payload": {"type": "object", "required": False, "default": {}},
            "approval_ref": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/ft/curate-and-register": {
        "description": "Curación y versionado atómico de dataset.",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "raw_samples": {"type": "array", "required": True},
            "prompt_template": {"type": "string", "required": True},
            "seed": {"type": "integer", "required": False, "default": 42},
            "train_eval_samples": {"type": "object", "required": False},
        },
    },
    "POST /api/v1/ft/plan-resources": {
        "description": "Planificación de recursos GPU.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "model_size_b": {"type": "number", "required": True},
            "budget_usd": {"type": "number", "required": True},
            "deadline_hours": {"type": "number", "required": True},
            "prefer_reliability": {"type": "boolean", "required": False, "default": False},
        },
    },
    "POST /api/v1/ft/run-hp-search": {
        "description": "Búsqueda de hiperparámetros.",
        "parameters": {"pipeline_id": {"type": "string", "required": True}},
    },
    "POST /api/v1/ft/create-training-config": {
        "description": "Crea configuración de entrenamiento.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "base_model": {"type": "string", "required": True},
            "hyperparams": {"type": "object", "required": False},
        },
    },
    "POST /api/v1/ft/simulate-training-step": {
        "description": "Envía métricas de entrenamiento y aplica política SRE.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "metrics": {"type": "object", "required": True},
        },
    },
    "POST /api/v1/ft/evaluate": {
        "description": "Evaluación multi-juez.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "domain_results": {"type": "array", "required": True},
            "general_results": {"type": "array", "required": True},
            "baseline_general_score": {"type": "number", "required": False, "default": 0.80},
        },
    },
    "POST /api/v1/ft/alignment-recommendation": {
        "description": "Recomendación de técnica de alineación.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "domain": {"type": "string", "required": True},
            "risk_profile": {"type": "string", "required": True},
            "has_human_preferences": {"type": "boolean", "required": True},
        },
    },
    "POST /api/v1/ft/deploy-canary": {
        "description": "Crea bundle y despliegue canary.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "adapter_uri": {"type": "string", "required": True},
            "generation_params": {"type": "object", "required": False, "default": {}},
            "traffic_percent": {"type": "number", "required": False, "default": 10},
            "serving_mode": {"type": "string", "required": False, "default": "lora_fused"},
        },
    },
    "POST /api/v1/ft/assess-canary": {
        "description": "Decide promover o rollback del canary.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "canary_metrics": {"type": "object", "required": True},
            "baseline_metrics": {"type": "object", "required": True},
        },
    },
    "POST /api/v1/ft/detect-drift": {
        "description": "Detecta drift y alucinaciones en despliegue.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "recent_inputs": {"type": "array", "required": True},
            "recent_outputs": {"type": "array", "required": True},
            "reference_contexts": {"type": "array", "required": True},
        },
    },
    "POST /api/v1/ft/feedback": {
        "description": "Ingesta feedback de producción.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "deployment_id": {"type": "string", "required": True},
            "input_text": {"type": "string", "required": True},
            "output_text": {"type": "string", "required": True},
            "label": {"type": "string", "required": True},
            "corrected_output": {"type": "string", "required": False, "default": ""},
            "source": {"type": "string", "required": False, "default": "user"},
        },
    },
    "GET /api/v1/ft/pipelines/<pipeline_id>": {
        "description": "Estado de un pipeline.",
        "parameters": {},
    },
    "GET /api/v1/ft/pipelines": {
        "description": "Lista pipelines por status.",
        "parameters": {"status": {"type": "string", "required": False}},
    },
    "POST /api/v1/ft/privacy/apply-contract": {
        "description": "Aplica contrato de datos y minimización.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "samples": {"type": "array", "required": True},
            "contract": {"type": "object", "required": True},
        },
    },
    "POST /api/v1/ft/privacy/deidentify": {
        "description": "Desidentifica muestras de entrenamiento.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "samples": {"type": "array", "required": True},
            "text_fields": {"type": "array", "required": False, "default": ["instruction", "output"]},
        },
    },
    "POST /api/v1/ft/privacy/dp-config": {
        "description": "Configura privacidad diferencial para entrenamiento.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "epsilon": {"type": "number", "required": False, "default": 1.0},
            "delta": {"type": "number", "required": False, "default": 1e-5},
            "noise_multiplier": {"type": "number", "required": False, "default": 1.0},
            "max_grad_norm": {"type": "number", "required": False, "default": 1.0},
        },
    },
    "POST /api/v1/ft/privacy/apply-dp": {
        "description": "Aplica DP y calcula presupuesto gastado.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "dataset_size": {"type": "integer", "required": True},
            "steps": {"type": "integer", "required": True},
        },
    },
    "POST /api/v1/ft/privacy/membership-inference": {
        "description": "Ataque de membership inference post-entrenamiento.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "members": {"type": "array", "required": True},
            "non_members": {"type": "array", "required": True},
        },
    },
    "POST /api/v1/ft/privacy/network-policy": {
        "description": "Valida política de red Zero Trust.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "policy": {"type": "object", "required": False},
        },
    },
    "POST /api/v1/ft/privacy/encryption-lease": {
        "description": "Emite lease de cifrado vía KMS/Vault.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "resource": {"type": "string", "required": True},
            "ttl_seconds": {"type": "number", "required": False, "default": 3600},
        },
    },
    "POST /api/v1/ft/privacy/inference-preflight": {
        "description": "Guardrail pre-vuelo de privacidad en inferencia.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "request_id": {"type": "string", "required": True},
            "prompt": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/ft/privacy/inference-postflight": {
        "description": "Guardrail post-vuelo de privacidad en inferencia.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "request_id": {"type": "string", "required": True},
            "prompt": {"type": "string", "required": True},
            "output": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/ft/privacy/artifacts": {
        "description": "Genera Model Card y Data Sheet.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "model_name": {"type": "string", "required": True},
            "intended_use": {"type": "string", "required": True},
            "privacy_controls": {"type": "array", "required": True},
            "limitations": {"type": "array", "required": True},
            "compliance_frameworks": {"type": "array", "required": True},
            "data_source": {"type": "string", "required": True},
            "sensitive_attributes": {"type": "array", "required": True},
            "anonymization_method": {"type": "string", "required": True},
            "retention_hours": {"type": "number", "required": True},
            "purpose": {"type": "string", "required": True},
        },
    },
    "GET /api/v1/ft/privacy/pipelines/<pipeline_id>": {
        "description": "Estado de un privacy pipeline.",
        "parameters": {},
    },
    "POST /api/v1/ft/quality-gate/run": {
        "description": "Ejecuta la puerta de calidad pre-producción completa.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "eval_records": {"type": "array", "required": True},
            "baseline_metrics": {"type": "object", "required": True},
            "previous_metrics": {"type": "object", "required": True},
            "qualitative_reviews": {"type": "array", "required": False, "default": []},
            "request_approval": {"type": "boolean", "required": False, "default": True},
        },
    },
    "POST /api/v1/ft/quality-gate/approve": {
        "description": "Firma de aprobación interdisciplinaria.",
        "parameters": {
            "pipeline_id": {"type": "string", "required": True},
            "team": {"type": "string", "required": True},
            "signed_by": {"type": "string", "required": True},
            "comment": {"type": "string", "required": False, "default": ""},
        },
    },
    "GET /api/v1/ft/quality-gate/reports/<report_id>": {
        "description": "Obtener reporte de quality gate.",
        "parameters": {},
    },
    "GET /api/v1/ft/quality-gate/reports": {
        "description": "Listar reportes de quality gate por status.",
        "parameters": {"status": {"type": "string", "required": False}},
    },
    "POST /api/v1/ft/extrinsic-metrics/app-event": {
        "description": "Ingesta evento de aplicación (negocio).",
        "parameters": {
            "session_id": {"type": "string", "required": True},
            "event_type": {"type": "string", "required": True},
            "timestamp": {"type": "number", "required": False},
            "success": {"type": "boolean", "required": False},
            "revenue_usd": {"type": "number", "required": False, "default": 0},
            "metadata": {"type": "object", "required": False, "default": {}},
        },
    },
    "POST /api/v1/ft/extrinsic-metrics/inf-event": {
        "description": "Ingesta evento de inferencia LLM (técnico).",
        "parameters": {
            "trace_id": {"type": "string", "required": True},
            "session_id": {"type": "string", "required": True},
            "model": {"type": "string", "required": False},
            "tokens_input": {"type": "integer", "required": False, "default": 0},
            "tokens_output": {"type": "integer", "required": False, "default": 0},
            "latency_ms": {"type": "number", "required": False, "default": 0},
            "cost_usd": {"type": "number", "required": False, "default": 0},
            "context_chunks_used": {"type": "integer", "required": False, "default": 0},
            "context_references": {"type": "array", "required": False, "default": []},
            "llm_judge_context_score": {"type": "number", "required": False},
        },
    },
    "POST /api/v1/ft/extrinsic-metrics/compute": {
        "description": "Computa métricas extrínsecas y contextuales.",
        "parameters": {
            "window_start": {"type": "number", "required": False},
            "window_end": {"type": "number", "required": False},
            "baseline_retention_rate": {"type": "number", "required": False},
        },
    },
    "GET /api/v1/ft/extrinsic-metrics/prometheus": {
        "description": "Render de métricas Prometheus.",
        "parameters": {},
    },
    "GET /api/v1/ft/extrinsic-metrics/logs": {
        "description": "Logs estructurados tipo Loki.",
        "parameters": {},
    },
    "GET /api/v1/ft/extrinsic-metrics/sessions/<session_id>": {
        "description": "Sesión unificada por session_id.",
        "parameters": {},
    },
    "POST /api/v1/ft/evaluation-matrix/checkpoint": {
        "description": "Crea un checkpoint de evaluación.",
        "parameters": {
            "name": {"type": "string", "required": True},
            "prompt_ids": {"type": "array", "required": False},
            "golden_set_ids": {"type": "array", "required": False},
            "cell_ids": {"type": "array", "required": False},
            "risk_signals": {"type": "array", "required": False},
            "version": {"type": "string", "required": False, "default": "1.0.0"},
        },
    },
    "GET /api/v1/ft/evaluation-matrix/checkpoints": {
        "description": "Lista checkpoints.",
        "parameters": {},
    },
    "POST /api/v1/ft/evaluation-matrix/prompt": {
        "description": "Crea un prompt estático.",
        "parameters": {
            "name": {"type": "string", "required": True},
            "prompt": {"type": "string", "required": True},
            "category": {"type": "string", "required": True},
            "risk_level": {"type": "string", "required": False, "default": "medium"},
            "tags": {"type": "array", "required": False, "default": []},
        },
    },
    "POST /api/v1/ft/evaluation-matrix/golden-set": {
        "description": "Crea un golden set.",
        "parameters": {
            "name": {"type": "string", "required": True},
            "records": {"type": "array", "required": True},
            "version": {"type": "string", "required": False, "default": "1.0.0"},
        },
    },
    "POST /api/v1/ft/evaluation-matrix/evaluate": {
        "description": "Ejecuta evaluación híbrida del checkpoint.",
        "parameters": {
            "run_id": {"type": "string", "required": True},
            "checkpoint_id": {"type": "string", "required": True},
            "model_version": {"type": "string", "required": True},
            "trigger_evolution": {"type": "boolean", "required": False, "default": False},
        },
    },
    "POST /api/v1/ft/evaluation-matrix/human-review": {
        "description": "Agrega revisión humana.",
        "parameters": {
            "sample_id": {"type": "string", "required": True},
            "reviewer_role": {"type": "string", "required": True},
            "correctness": {"type": "integer", "required": True},
            "helpfulness": {"type": "integer", "required": True},
            "safety": {"type": "integer", "required": True},
            "fairness": {"type": "integer", "required": False, "default": 0},
            "comments": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/ft/evaluation-matrix/user-feedback": {
        "description": "Ingesta feedback implícito de usuario.",
        "parameters": {
            "session_id": {"type": "string", "required": True},
            "feedback_type": {"type": "string", "required": True},
            "reason": {"type": "string", "required": False, "default": ""},
        },
    },
    "GET /api/v1/ft/evaluation-matrix/reports/<report_id>": {
        "description": "Obtener reporte CEM.",
        "parameters": {},
    },
    "GET /api/v1/ft/evaluation-matrix/prometheus": {
        "description": "Métricas Prometheus de CEM.",
        "parameters": {},
    },
    "GET /api/v1/ft/evaluation-matrix/logs": {
        "description": "Logs estructurados de CEM.",
        "parameters": {},
    },
    "POST /api/v1/runtime/recovery/register-tool": {
        "description": "Registra esquema de entrada/salida de una herramienta.",
        "parameters": {
            "tool_name": {"type": "string", "required": True},
            "input_schema": {"type": "object", "required": False},
            "output_schema": {"type": "object", "required": False},
        },
    },
    "POST /api/v1/runtime/recovery/invoke": {
        "description": "Invoca herramienta con recuperación ante fallos.",
        "parameters": {
            "run_id": {"type": "string", "required": True},
            "step_id": {"type": "string", "required": True},
            "tool_name": {"type": "string", "required": True},
            "params": {"type": "object", "required": True},
            "completed_steps": {"type": "array", "required": False, "default": []},
            "partial_state": {"type": "object", "required": False, "default": {}},
        },
    },
    "GET /api/v1/runtime/recovery/reports/<report_id>": {
        "description": "Obtener reporte de recuperación.",
        "parameters": {},
    },
    "GET /api/v1/runtime/recovery/reports": {
        "description": "Listar reportes de recuperación.",
        "parameters": {},
    },
    "GET /api/v1/runtime/recovery/prometheus": {
        "description": "Métricas Prometheus de recuperación.",
        "parameters": {},
    },
    "GET /api/v1/runtime/recovery/logs": {
        "description": "Logs estructurados de recuperación.",
        "parameters": {},
    },
    "POST /api/v1/runtime/recovery/hitl-decide": {
        "description": "Decisión HITL sobre escalación.",
        "parameters": {
            "escalation_id": {"type": "string", "required": True},
            "operator_decision": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/compliance/prompt/commit": {
        "description": "Commit de versión de prompt con trazabilidad regulatoria.",
        "parameters": {
            "prompt_name": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
            "author": {"type": "string", "required": True},
            "regulatory_change": {"type": "boolean", "required": False, "default": False},
            "approved_by": {"type": "array", "required": False, "default": []},
            "commit_message": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/compliance/prompt/approve": {
        "description": "Aprueba una versión de prompt.",
        "parameters": {
            "prompt_name": {"type": "string", "required": True},
            "version_id": {"type": "string", "required": True},
            "approver": {"type": "string", "required": True},
        },
    },
    "GET /api/v1/compliance/prompt/history/<prompt_name>": {
        "description": "Historial de versiones de un prompt.",
        "parameters": {},
    },
    "POST /api/v1/compliance/dataset/register": {
        "description": "Registra linaje de dataset.",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "source": {"type": "string", "required": True},
            "transformations": {"type": "array", "required": False, "default": []},
            "consent_tags": {"type": "array", "required": False, "default": []},
            "retention_hours": {"type": "number", "required": False, "default": 168},
            "purpose": {"type": "string", "required": False, "default": ""},
            "privacy_controls": {"type": "array", "required": False, "default": []},
        },
    },
    "POST /api/v1/compliance/dataset/transformation": {
        "description": "Añade transformación a un dataset.",
        "parameters": {
            "dataset_id": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "tool": {"type": "string", "required": False, "default": ""},
            "params": {"type": "object", "required": False, "default": {}},
        },
    },
    "GET /api/v1/compliance/dataset/<dataset_id>": {
        "description": "Obtiene linaje de dataset.",
        "parameters": {},
    },
    "POST /api/v1/compliance/access/grant": {
        "description": "Concede permiso RBAC/ABAC.",
        "parameters": {
            "role": {"type": "string", "required": True},
            "resource": {"type": "string", "required": True},
            "action": {"type": "string", "required": True},
            "environments": {"type": "array", "required": False, "default": []},
        },
    },
    "POST /api/v1/compliance/access/evaluate": {
        "description": "Evalúa decisión de acceso.",
        "parameters": {
            "requester_id": {"type": "string", "required": True},
            "roles": {"type": "array", "required": True},
            "resource": {"type": "string", "required": True},
            "action": {"type": "string", "required": True},
            "environment": {"type": "string", "required": True},
            "oidc_claims": {"type": "object", "required": False, "default": {}},
            "tenant": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/compliance/inference/record": {
        "description": "Registra inferencia en ledger WORM.",
        "parameters": {
            "request_id": {"type": "string", "required": True},
            "session_id": {"type": "string", "required": True},
            "requester_id": {"type": "string", "required": True},
            "requester_roles": {"type": "array", "required": True},
            "artifact_bundle": {"type": "object", "required": True},
            "input_text": {"type": "string", "required": True},
            "output_text": {"type": "string", "required": True},
            "access_decision": {"type": "string", "required": True},
            "policies_applied": {"type": "array", "required": True},
            "pii_detected": {"type": "boolean", "required": False, "default": False},
            "guardrail_violations": {"type": "array", "required": False, "default": []},
            "e_discovery_tag": {"type": "string", "required": False, "default": ""},
        },
    },
    "GET /api/v1/compliance/inference/query": {
        "description": "Consulta ledger de inferencia.",
        "parameters": {},
    },
    "GET /api/v1/compliance/ledger/verify": {
        "description": "Verifica integridad de hash chain.",
        "parameters": {},
    },
    "POST /api/v1/compliance/metrics/ingest": {
        "description": "Ingesta métrica técnica para evaluación regulatoria.",
        "parameters": {
            "metric_name": {"type": "string", "required": True},
            "value": {"type": "number", "required": True},
        },
    },
    "POST /api/v1/compliance/alerts/acknowledge": {
        "description": "Acknowledge de alerta de cumplimiento.",
        "parameters": {
            "alert_id": {"type": "string", "required": True},
        },
    },
    "GET /api/v1/compliance/report": {
        "description": "Reporte de cumplimiento.",
        "parameters": {},
    },
    "GET /api/v1/compliance/dashboard": {
        "description": "Dashboard de cumplimiento.",
        "parameters": {},
    },
    "GET /api/v1/compliance/rules": {
        "description": "Reglas de mapeo regulatorio.",
        "parameters": {},
    },
    "POST /api/v1/ci/feedback": {
        "description": "Ingesta feedback explícito o implícito.",
        "parameters": {
            "source": {"type": "string", "required": True},
            "category": {"type": "string", "required": True},
            "severity": {"type": "string", "required": False, "default": "medium"},
            "message": {"type": "string", "required": False, "default": ""},
            "model_version": {"type": "string", "required": False, "default": ""},
            "prompt_version_id": {"type": "string", "required": False, "default": ""},
            "session_id": {"type": "string", "required": False, "default": ""},
            "trace_id": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/ci/analyze": {
        "description": "Analiza clusters y genera recomendaciones.",
        "parameters": {
            "log_refs": {"type": "array", "required": False, "default": []},
            "incident_refs": {"type": "array", "required": False, "default": []},
        },
    },
    "POST /api/v1/ci/recommendations/approve": {
        "description": "Aprueba recomendación de mejora continua.",
        "parameters": {
            "queue_item_id": {"type": "string", "required": True},
            "reviewer": {"type": "string", "required": True},
            "notes": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/ci/recommendations/reject": {
        "description": "Rechaza recomendación de mejora continua.",
        "parameters": {
            "queue_item_id": {"type": "string", "required": True},
            "reviewer": {"type": "string", "required": True},
            "notes": {"type": "string", "required": False, "default": ""},
        },
    },
    "GET /api/v1/ci/recommendations": {
        "description": "Lista recomendaciones de mejora continua.",
        "parameters": {},
    },
    "GET /api/v1/ci/recommendations/pending": {
        "description": "Lista recomendaciones pendientes de aprobación.",
        "parameters": {},
    },
    "POST /api/v1/ci/baseline": {
        "description": "Registra baseline de métrica para medir efectividad.",
        "parameters": {
            "metric_name": {"type": "string", "required": True},
            "value": {"type": "number", "required": True},
        },
    },
    "POST /api/v1/ci/measure": {
        "description": "Mide efectividad post-mejora.",
        "parameters": {
            "recommendation_id": {"type": "string", "required": True},
            "metric_name": {"type": "string", "required": True},
            "value": {"type": "number", "required": True},
        },
    },
    "GET /api/v1/ci/dashboard": {
        "description": "Dashboard de mejora continua.",
        "parameters": {},
    },
    "POST /api/v1/qa/run": {
        "description": "Ejecuta el Enterprise QA Driver sobre un batch de casos de prueba.",
        "parameters": {
            "test_cases": {"type": "array", "required": True, "items": {
                "id": "string",
                "pillar": "string",
                "prompt": "string",
                "expected_keywords": "array",
                "forbidden_keywords": "array",
                "required_sequence": "array",
                "llm_response": "string",
            }},
        },
    },
    "POST /api/v1/incidents": {
        "description": "Crea un incidente LLMOps.",
        "parameters": {
            "title": {"type": "string", "required": True},
            "category": {"type": "string", "required": True},
            "description": {"type": "string", "required": False, "default": ""},
            "urgency": {"type": "string", "required": False, "default": "normal"},
            "affected_users": {"type": "integer", "required": False, "default": 0},
            "regulatory_criticality": {"type": "string", "required": False, "default": "none"},
            "tags": {"type": "array", "required": False, "default": []},
        },
    },
    "GET /api/v1/incidents": {
        "description": "Lista incidentes.",
        "parameters": {},
    },
    "GET /api/v1/incidents/<incident_id>": {
        "description": "Obtener incidente.",
        "parameters": {},
    },
    "POST /api/v1/incidents/<incident_id>/triage": {
        "description": "Triaje: clasifica severidad y asigna equipo/commander.",
        "parameters": {},
    },
    "POST /api/v1/incidents/<incident_id>/contain": {
        "description": "Aplica acciones de contención.",
        "parameters": {
            "actions": {"type": "array", "required": True},
        },
    },
    "POST /api/v1/incidents/<incident_id>/resolve": {
        "description": "Resuelve incidente.",
        "parameters": {},
    },
    "POST /api/v1/incidents/<incident_id>/alerts": {
        "description": "Crea alerta asociada a incidente.",
        "parameters": {
            "metric": {"type": "string", "required": True},
            "value": {"type": "number", "required": True},
            "threshold": {"type": "number", "required": True},
        },
    },
    "POST /api/v1/incidents/oncall": {
        "description": "Registra persona de guardia.",
        "parameters": {
            "name": {"type": "string", "required": True},
            "team": {"type": "string", "required": True},
            "phone": {"type": "string", "required": False, "default": ""},
            "email": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/incidents/<incident_id>/communicate": {
        "description": "Envía comunicación automatizada.",
        "parameters": {
            "channel": {"type": "string", "required": True},
            "recipient_team": {"type": "string", "required": True},
            "template_name": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/incidents/<incident_id>/runbook": {
        "description": "Ejecuta runbook del incidente.",
        "parameters": {},
    },
    "POST /api/v1/incidents/<incident_id>/post-mortem": {
        "description": "Genera post-mortem.",
        "parameters": {
            "root_cause": {"type": "string", "required": True},
            "failed_controls": {"type": "array", "required": True},
            "action_items": {"type": "array", "required": True},
            "lessons_learned": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/incidents/sli/register": {
        "description": "Registra SLI.",
        "parameters": {
            "sli_id": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
            "metric": {"type": "string", "required": True},
            "unit": {"type": "string", "required": True},
            "description": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/incidents/slos": {
        "description": "Define SLO y presupuesto de error.",
        "parameters": {
            "sli_id": {"type": "string", "required": True},
            "target": {"type": "number", "required": True},
            "window_seconds": {"type": "number", "required": True},
            "description": {"type": "string", "required": False, "default": ""},
        },
    },
    "POST /api/v1/incidents/slos/<slo_id>/sample": {
        "description": "Registra muestra de SLO y devuelve error budget.",
        "parameters": {
            "good": {"type": "boolean", "required": True},
        },
    },
    "GET /api/v1/incidents/dashboard": {
        "description": "Dashboard de incidentes.",
        "parameters": {},
    },
}

OUTPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "runtime_task": {
        "task_id": "string",
        "objective_id": "string",
        "status": "pending|planning|awaiting_approval|approved|running|paused|completed|failed|cancelled",
        "plan": "object",
        "approvals": "object",
        "results": "object",
        "completed_steps": "array<string>",
        "failed_steps": "array<string>",
        "pending_steps": "array<string>",
        "created_at": "number",
        "updated_at": "number",
    },
    "plan_step": {
        "step_id": "string",
        "capability": "think|remember|approve|execute_local|execute_temporal|execute_stackstorm|execute_n8n",
        "action": "string",
        "params": "object",
        "depends_on": "array<string>",
        "reasoning": "string",
    },
    "approval_decision": {
        "approval_ref": "string",
        "decision": "allowed|denied",
        "reason": "string",
        "scope": "auto|hitl",
        "approved_by": "string",
        "expires_at": "number",
    },
    "execution_result": {
        "result_id": "string",
        "step_id": "string",
        "status": "succeeded|failed|denied",
        "output": "object",
        "error": "string|null",
        "backend": "temporal|stackstorm|n8n|local",
        "trace_id": "string",
    },
    "temporal_workflow": {
        "workflow_id": "string",
        "status": "pending|running|completed|failed|cancelled",
        "activities": "array<object>",
        "context": "object",
    },
    "stackstorm_execution": {
        "execution_id": "string",
        "playbook": "string",
        "status": "pending|running|succeeded|failed|timeout",
        "result": "object",
        "error": "string|null",
    },
    "n8n_execution": {
        "execution_id": "string",
        "workflow_id": "string",
        "status": "pending|running|succeeded|failed",
        "result": "object",
        "error": "string|null",
    },
    "runtime_status": {
        "tasks_total": "integer",
        "by_status": "object",
        "observability_events": "integer",
        "temporal_workflows": "integer",
        "stackstorm_executions": "integer",
        "n8n_executions": "integer",
        "memory_episodes": "integer",
    },
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return _ok({"service": "uc703-agent-runtime", "status": "ok"})


@app.get("/api/v1/cards")
def cards():
    return _ok({"input": INPUT_CARDS, "output": OUTPUT_CARDS})


@app.post("/api/v1/objective")
def create_objective():
    data = _body()
    if "description" not in data:
        return _err("description requerido")
    task = _orchestrator.submit_objective(
        description=data["description"],
        agent_id=data.get("agent_id", ""),
        tenant_id=data.get("tenant_id", ""),
        requested_by=data.get("requested_by", ""),
        context=data.get("context", {}),
    )
    return _ok(task.to_dict(), 201)


@app.post("/api/v1/objective/<task_id>/plan")
def plan_objective(task_id: str):
    task = _orchestrator.plan_task(task_id)
    if not task:
        return _err("tarea no encontrada", 404)
    return _ok(task.to_dict())


@app.post("/api/v1/objective/<task_id>/approve")
def approve_all(task_id: str):
    task = _orchestrator.approve_all_steps(task_id)
    if not task:
        return _err("tarea no encontrada", 404)
    return _ok(task.to_dict())


@app.post("/api/v1/objective/<task_id>/approve/<step_id>")
def approve_step(task_id: str, step_id: str):
    data = _body()
    decision = _orchestrator.approve_step(task_id, step_id, data.get("scope", "auto"))
    if not decision:
        return _err("tarea o paso no encontrado", 404)
    return _ok(decision.to_dict())


@app.post("/api/v1/objective/<task_id>/execute")
def execute_task(task_id: str):
    task = _orchestrator.execute_task(task_id)
    if not task:
        return _err("tarea no encontrada", 404)
    return _ok(task.to_dict())


@app.post("/api/v1/objective/<task_id>/pause")
def pause_task(task_id: str):
    task = _orchestrator.pause_task(task_id)
    if not task:
        return _err("tarea no encontrada", 404)
    return _ok(task.to_dict())


@app.post("/api/v1/objective/<task_id>/resume")
def resume_task(task_id: str):
    task = _orchestrator.resume_task(task_id)
    if not task:
        return _err("tarea no encontrada o no pausada", 404)
    return _ok(task.to_dict())


@app.post("/api/v1/objective/<task_id>/cancel")
def cancel_task(task_id: str):
    task = _orchestrator.cancel_task(task_id)
    if not task:
        return _err("tarea no encontrada", 404)
    return _ok(task.to_dict())


@app.get("/api/v1/objective/<task_id>")
def get_task(task_id: str):
    task = _orchestrator.get_task(task_id)
    if not task:
        return _err("tarea no encontrada", 404)
    return _ok(task.to_dict())


@app.get("/api/v1/objectives")
def list_tasks():
    status = request.args.get("status")
    tasks = _orchestrator.list_tasks(status=status)
    return _ok([t.to_dict() for t in tasks])


@app.get("/api/v1/runtime/status")
def runtime_status():
    return _ok(_orchestrator.runtime_status())


# ---------------------------------------------------------------------------
# Adapters directos
# ---------------------------------------------------------------------------

@app.post("/api/v1/temporal/workflow")
def create_temporal_workflow():
    data = _body()
    if "activities" not in data:
        return _err("activities requerido")
    wf = _orchestrator.temporal.start_workflow(
        activities=data["activities"],
        workflow_id=data.get("workflow_id"),
        task_queue=data.get("task_queue", "uc703-default"),
        context=data.get("context", {}),
    )
    return _ok({
        "workflow_id": wf.workflow_id,
        "status": wf.status,
        "activities": [
            {"activity_id": a.activity_id, "name": a.name, "status": a.status}
            for a in wf.activities
        ],
    }, 201)


@app.post("/api/v1/temporal/workflow/<workflow_id>/run")
def run_temporal_workflow(workflow_id: str):
    wf = _orchestrator.temporal.run_workflow(workflow_id)
    if not wf:
        return _err("workflow no encontrado", 404)
    return _ok({
        "workflow_id": wf.workflow_id,
        "status": wf.status,
        "activities": [
            {"activity_id": a.activity_id, "name": a.name, "status": a.status, "result": a.result, "error": a.error}
            for a in wf.activities
        ],
    })


@app.post("/api/v1/temporal/workflow/<workflow_id>/signal")
def signal_temporal_workflow(workflow_id: str):
    data = _body()
    signal = data.get("signal")
    if not signal:
        return _err("signal requerido")
    wf = _orchestrator.temporal.signal_workflow(workflow_id, signal, data.get("payload"))
    if not wf:
        return _err("workflow no encontrado", 404)
    return _ok({"workflow_id": wf.workflow_id, "status": wf.status})


@app.post("/api/v1/stackstorm/execute")
def execute_stackstorm():
    data = _body()
    required = ["playbook", "approval_ref"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    exec_ = _orchestrator.stackstorm.execute(
        playbook=data["playbook"],
        params=data.get("params", {}),
        approval_ref=data["approval_ref"],
    )
    return _ok({
        "execution_id": exec_.execution_id,
        "playbook": exec_.playbook,
        "status": exec_.status,
        "result": exec_.result,
        "error": exec_.error,
    })


@app.post("/api/v1/n8n/execute")
def execute_n8n():
    data = _body()
    required = ["workflow_id", "approval_ref"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    exec_ = _orchestrator.n8n.execute(
        workflow_id=data["workflow_id"],
        payload=data.get("payload", {}),
        approval_ref=data["approval_ref"],
    )
    return _ok({
        "execution_id": exec_.execution_id,
        "workflow_id": exec_.workflow_id,
        "status": exec_.status,
        "result": exec_.result,
        "error": exec_.error,
    })


@app.get("/api/v1/metrics")
def prometheus_metrics():
    return _orchestrator.observability.render_prometheus_metrics(), 200, {"Content-Type": "text/plain"}


# ---------------------------------------------------------------------------
# Fine-tuning lifecycle endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ft/curate-and-register")
def ft_curate_and_register():
    data = _body()
    required = ["dataset_id", "raw_samples", "prompt_template"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    state = _ft_controller.curate_and_register(
        dataset_id=data["dataset_id"],
        raw_samples=data["raw_samples"],
        prompt_template=data["prompt_template"],
        seed=data.get("seed", 42),
        train_eval_samples=data.get("train_eval_samples"),
    )
    return _ok(state.to_dict(), 201)


@app.post("/api/v1/ft/plan-resources")
def ft_plan_resources():
    data = _body()
    required = ["pipeline_id", "model_size_b", "budget_usd", "deadline_hours"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    state = _ft_controller.plan_resources(
        pipeline_id=data["pipeline_id"],
        model_size_b=float(data["model_size_b"]),
        budget_usd=float(data["budget_usd"]),
        deadline_hours=float(data["deadline_hours"]),
        prefer_reliability=bool(data.get("prefer_reliability", False)),
    )
    return _ok(state.to_dict())


@app.post("/api/v1/ft/run-hp-search")
def ft_run_hp_search():
    data = _body()
    if "pipeline_id" not in data:
        return _err("pipeline_id requerido")
    return _ok(_ft_controller.run_hp_search(data["pipeline_id"]))


@app.post("/api/v1/ft/create-training-config")
def ft_create_training_config():
    data = _body()
    required = ["pipeline_id", "base_model"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    state = _ft_controller.create_training_config(
        pipeline_id=data["pipeline_id"],
        base_model=data["base_model"],
        hyperparams=data.get("hyperparams"),
    )
    return _ok(state.to_dict())


@app.post("/api/v1/ft/simulate-training-step")
def ft_simulate_training_step():
    data = _body()
    required = ["pipeline_id", "metrics"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    return _ok(_ft_controller.simulate_training_step(data["pipeline_id"], data["metrics"]))


@app.post("/api/v1/ft/evaluate")
def ft_evaluate():
    data = _body()
    required = ["pipeline_id", "domain_results", "general_results"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    return _ok(_ft_controller.evaluate(
        pipeline_id=data["pipeline_id"],
        domain_results=data["domain_results"],
        general_results=data["general_results"],
        baseline_general_score=float(data.get("baseline_general_score", 0.80)),
    ))


@app.post("/api/v1/ft/alignment-recommendation")
def ft_alignment_recommendation():
    data = _body()
    required = ["pipeline_id", "domain", "risk_profile", "has_human_preferences"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    return _ok(_ft_controller.recommend_alignment(
        pipeline_id=data["pipeline_id"],
        domain=data["domain"],
        risk_profile=data["risk_profile"],
        has_human_preferences=bool(data["has_human_preferences"]),
    ))


@app.post("/api/v1/ft/deploy-canary")
def ft_deploy_canary():
    data = _body()
    required = ["pipeline_id", "adapter_uri"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    state = _ft_controller.build_and_deploy_canary(
        pipeline_id=data["pipeline_id"],
        adapter_uri=data["adapter_uri"],
        generation_params=data.get("generation_params", {}),
        traffic_percent=float(data.get("traffic_percent", 10.0)),
        serving_mode=data.get("serving_mode", "lora_fused"),
    )
    return _ok(state.to_dict())


@app.post("/api/v1/ft/assess-canary")
def ft_assess_canary():
    data = _body()
    required = ["pipeline_id", "canary_metrics", "baseline_metrics"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    return _ok(_ft_controller.assess_canary(
        pipeline_id=data["pipeline_id"],
        canary_metrics=data["canary_metrics"],
        baseline_metrics=data["baseline_metrics"],
    ))


@app.post("/api/v1/ft/detect-drift")
def ft_detect_drift():
    data = _body()
    required = ["pipeline_id", "recent_inputs", "recent_outputs", "reference_contexts"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    return _ok(_ft_controller.detect_drift(
        pipeline_id=data["pipeline_id"],
        recent_inputs=data["recent_inputs"],
        recent_outputs=data["recent_outputs"],
        reference_contexts=data["reference_contexts"],
    ))


@app.post("/api/v1/ft/feedback")
def ft_feedback():
    data = _body()
    required = ["pipeline_id", "deployment_id", "input_text", "output_text", "label"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    item = FeedbackItem(
        deployment_id=data["deployment_id"],
        input_text=data["input_text"],
        output_text=data["output_text"],
        label=data["label"],
        corrected_output=data.get("corrected_output", ""),
        source=data.get("source", "user"),
    )
    return _ok(_ft_controller.ingest_feedback(data["pipeline_id"], item))


@app.get("/api/v1/ft/pipelines/<pipeline_id>")
def ft_get_pipeline(pipeline_id: str):
    state = _ft_controller.get_pipeline(pipeline_id)
    if not state:
        return _err("pipeline no encontrado", 404)
    return _ok(state.to_dict())


@app.get("/api/v1/ft/pipelines")
def ft_list_pipelines():
    status = request.args.get("status")
    return _ok([p.to_dict() for p in _ft_controller.list_pipelines(status=status)])


# ---------------------------------------------------------------------------
# Privacy-Preserving LLMOps endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ft/privacy/apply-contract")
def ft_privacy_apply_contract():
    data = _body()
    required = ["pipeline_id", "samples", "contract"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ft_controller.privacy is None:
        return _err("privacy controller no configurado", 503)
    contract = DataContract(
        required_fields=data["contract"].get("required_fields", []),
        forbidden_fields=data["contract"].get("forbidden_fields", []),
        purpose=data["contract"].get("purpose", ""),
        max_retention_hours=float(data["contract"].get("max_retention_hours", 168.0)),
        allowed_regions=data["contract"].get("allowed_regions", ["private"]),
    )
    state = _ft_controller._pipelines.get(data["pipeline_id"])
    if state is None:
        return _err("pipeline no encontrado", 404)
    if state.privacy_state is None:
        state.privacy_state = _ft_controller.privacy.create_pipeline()
    pstate = _ft_controller.privacy.apply_data_contract(data["samples"], contract)
    state.privacy_state = pstate
    return _ok(pstate.to_dict(), 201)


@app.post("/api/v1/ft/privacy/deidentify")
def ft_privacy_deidentify():
    data = _body()
    required = ["pipeline_id", "samples"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ft_controller.privacy is None:
        return _err("privacy controller no configurado", 503)
    state = _ft_controller._pipelines.get(data["pipeline_id"])
    if state is None or state.privacy_state is None:
        return _err("pipeline o privacy_state no encontrado", 404)
    result = _ft_controller.privacy.deidentify_samples(
        state.privacy_state.pipeline_id,
        data["samples"],
        text_fields=data.get("text_fields", ["instruction", "output"]),
    )
    return _ok(result)


@app.post("/api/v1/ft/privacy/dp-config")
def ft_privacy_dp_config():
    data = _body()
    required = ["pipeline_id"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ft_controller.privacy is None:
        return _err("privacy controller no configurado", 503)
    dp = DPTrainingConfig(
        enabled=bool(data.get("enabled", True)),
        epsilon=float(data.get("epsilon", 1.0)),
        delta=float(data.get("delta", 1e-5)),
        max_grad_norm=float(data.get("max_grad_norm", 1.0)),
        noise_multiplier=float(data.get("noise_multiplier", 1.0)),
        method=data.get("method", "dp-sgd"),
    )
    state = _ft_controller._pipelines.get(data["pipeline_id"])
    if state is None:
        return _err("pipeline no encontrado", 404)
    result = _ft_controller.configure_privacy_dp(data["pipeline_id"], dp)
    return _ok(result)


@app.post("/api/v1/ft/privacy/apply-dp")
def ft_privacy_apply_dp():
    data = _body()
    required = ["pipeline_id", "dataset_size", "steps"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    result = _ft_controller.apply_dp_to_training(
        data["pipeline_id"],
        int(data["dataset_size"]),
        int(data["steps"]),
    )
    return _ok(result)


@app.post("/api/v1/ft/privacy/membership-inference")
def ft_privacy_membership_inference():
    data = _body()
    required = ["pipeline_id", "members", "non_members"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    result = _ft_controller.validate_membership_inference_privacy(
        data["pipeline_id"],
        data["members"],
        data["non_members"],
    )
    return _ok(result)


@app.post("/api/v1/ft/privacy/network-policy")
def ft_privacy_network_policy():
    data = _body()
    required = ["pipeline_id"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if data["pipeline_id"] not in _ft_controller._pipelines:
        return _err("pipeline no encontrado", 404)
    policy = None
    if "policy" in data:
        policy = NetworkPolicy(
            vpc_only=bool(data["policy"].get("vpc_only", True)),
            public_exposure=bool(data["policy"].get("public_exposure", False)),
            mtls_required=bool(data["policy"].get("mtls_required", True)),
            tls_version=data["policy"].get("tls_version", "1.3"),
            allowed_endpoints=data["policy"].get("allowed_endpoints", []),
            private_link=bool(data["policy"].get("private_link", True)),
        )
    result = _ft_controller.enforce_network_policy_privacy(data["pipeline_id"], policy)
    return _ok(result)


@app.post("/api/v1/ft/privacy/encryption-lease")
def ft_privacy_encryption_lease():
    data = _body()
    required = ["pipeline_id", "resource"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ft_controller.privacy is None:
        return _err("privacy controller no configurado", 503)
    state = _ft_controller._pipelines.get(data["pipeline_id"])
    if state is None or state.privacy_state is None:
        return _err("pipeline o privacy_state no encontrado", 404)
    result = _ft_controller.privacy.issue_encryption_lease(
        state.privacy_state.pipeline_id,
        data["resource"],
        ttl_seconds=float(data.get("ttl_seconds", 3600)),
    )
    return _ok(result)


@app.post("/api/v1/ft/privacy/inference-preflight")
def ft_privacy_inference_preflight():
    data = _body()
    required = ["pipeline_id", "request_id", "prompt"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    result = _ft_controller.preflight_inference_privacy(
        data["pipeline_id"],
        data["request_id"],
        data["prompt"],
    )
    return _ok(result)


@app.post("/api/v1/ft/privacy/inference-postflight")
def ft_privacy_inference_postflight():
    data = _body()
    required = ["pipeline_id", "request_id", "prompt", "output"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    result = _ft_controller.postflight_inference_privacy(
        data["pipeline_id"],
        data["request_id"],
        data["prompt"],
        data["output"],
    )
    return _ok(result)


@app.post("/api/v1/ft/privacy/artifacts")
def ft_privacy_artifacts():
    data = _body()
    required = [
        "pipeline_id", "model_name", "intended_use", "privacy_controls",
        "limitations", "compliance_frameworks", "data_source",
        "sensitive_attributes", "anonymization_method", "retention_hours", "purpose",
    ]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    result = _ft_controller.generate_privacy_artifacts(
        data["pipeline_id"],
        data["model_name"],
        data["intended_use"],
        data["privacy_controls"],
        data["limitations"],
        data["compliance_frameworks"],
        data["data_source"],
        data["sensitive_attributes"],
        data["anonymization_method"],
        float(data["retention_hours"]),
        data["purpose"],
    )
    return _ok(result)


@app.get("/api/v1/ft/privacy/pipelines/<pipeline_id>")
def ft_privacy_get_pipeline(pipeline_id: str):
    if _ft_controller.privacy is None:
        return _err("privacy controller no configurado", 503)
    state = _ft_controller.privacy.get_pipeline(pipeline_id)
    if not state:
        return _err("privacy pipeline no encontrado", 404)
    return _ok(state.to_dict())


# ---------------------------------------------------------------------------
# PreProductionQualityGate endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ft/quality-gate/run")
def ft_quality_gate_run():
    data = _body()
    required = ["pipeline_id", "eval_records", "baseline_metrics", "previous_metrics"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ft_controller.quality_gate is None:
        return _err("quality gate controller no configurado", 503)
    reviews = []
    for r in data.get("qualitative_reviews", []):
        reviews.append(QualitativeReview(
            reviewer_role=r.get("reviewer_role", ""),
            sample_id=r.get("sample_id", ""),
            correctness=int(r.get("correctness", 0)),
            helpfulness=int(r.get("helpfulness", 0)),
            safety=int(r.get("safety", 0)),
            comments=r.get("comments", ""),
        ))
    result = _ft_controller.run_quality_gate(
        pipeline_id=data["pipeline_id"],
        eval_records=data["eval_records"],
        baseline_metrics=data["baseline_metrics"],
        previous_metrics=data["previous_metrics"],
        qualitative_reviews=reviews,
        request_approval=bool(data.get("request_approval", True)),
    )
    return _ok(result)


@app.post("/api/v1/ft/quality-gate/approve")
def ft_quality_gate_approve():
    data = _body()
    required = ["pipeline_id", "team", "signed_by"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    result = _ft_controller.submit_quality_gate_signature(
        pipeline_id=data["pipeline_id"],
        team=data["team"],
        signed_by=data["signed_by"],
        comment=data.get("comment", ""),
    )
    return _ok(result)


@app.get("/api/v1/ft/quality-gate/reports/<report_id>")
def ft_quality_gate_get_report(report_id: str):
    if _ft_controller.quality_gate is None:
        return _err("quality gate controller no configurado", 503)
    report = _ft_controller.quality_gate.get_report(report_id)
    if not report:
        return _err("report no encontrado", 404)
    return _ok(report.to_dict())


@app.get("/api/v1/ft/quality-gate/reports")
def ft_quality_gate_list_reports():
    if _ft_controller.quality_gate is None:
        return _err("quality gate controller no configurado", 503)
    status = request.args.get("status")
    return _ok([r.to_dict() for r in _ft_controller.quality_gate.list_reports(status=status)])


# ---------------------------------------------------------------------------
# Extrinsic & Contextual Metrics endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ft/extrinsic-metrics/app-event")
def ft_em_app_event():
    data = _body()
    required = ["session_id", "event_type"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _em_controller is None:
        return _err("extrinsic metrics controller no configurado", 503)
    session = _em_controller.ingest_application_event(data)
    return _ok(session.to_dict(), 201)


@app.post("/api/v1/ft/extrinsic-metrics/inf-event")
def ft_em_inf_event():
    data = _body()
    required = ["trace_id", "session_id"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _em_controller is None:
        return _err("extrinsic metrics controller no configurado", 503)
    session = _em_controller.ingest_inference_event(data)
    return _ok(session.to_dict(), 201)


@app.post("/api/v1/ft/extrinsic-metrics/compute")
def ft_em_compute():
    data = _body()
    if _em_controller is None:
        return _err("extrinsic metrics controller no configurado", 503)
    now = time.time()
    window_start = float(data.get("window_start", now - 3600))
    window_end = float(data.get("window_end", now))
    baseline_retention = data.get("baseline_retention_rate")
    if baseline_retention is not None:
        baseline_retention = float(baseline_retention)
    snapshot = _em_controller.compute_metrics(window_start, window_end, baseline_retention)
    return _ok(snapshot.to_dict())


@app.get("/api/v1/ft/extrinsic-metrics/prometheus")
def ft_em_prometheus():
    if _em_controller is None:
        return _err("extrinsic metrics controller no configurado", 503)
    return _em_controller.render_prometheus()


@app.get("/api/v1/ft/extrinsic-metrics/logs")
def ft_em_logs():
    if _em_controller is None:
        return _err("extrinsic metrics controller no configurado", 503)
    return _ok(_em_controller.get_logs())


@app.get("/api/v1/ft/extrinsic-metrics/sessions/<session_id>")
def ft_em_session(session_id: str):
    if _em_controller is None:
        return _err("extrinsic metrics controller no configurado", 503)
    session = _em_controller.get_session(session_id)
    if not session:
        return _err("session no encontrada", 404)
    return _ok(session.to_dict())


# ---------------------------------------------------------------------------
# Continuous Evaluation Matrix endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ft/evaluation-matrix/checkpoint")
def ft_cem_create_checkpoint():
    data = _body()
    required = ["name"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    cp = _cem_controller.create_checkpoint(
        name=data["name"],
        prompt_ids=data.get("prompt_ids"),
        golden_set_ids=data.get("golden_set_ids"),
        cell_ids=data.get("cell_ids"),
        risk_signals=data.get("risk_signals"),
        version=data.get("version", "1.0.0"),
    )
    return _ok(cp.to_dict(), 201)


@app.get("/api/v1/ft/evaluation-matrix/checkpoints")
def ft_cem_list_checkpoints():
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    return _ok([c.to_dict() for c in _cem_controller.test_design.list_checkpoints()])


@app.post("/api/v1/ft/evaluation-matrix/prompt")
def ft_cem_create_prompt():
    data = _body()
    required = ["name", "prompt", "category"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    sp = _cem_controller.create_static_prompt(
        name=data["name"],
        prompt=data["prompt"],
        category=data["category"],
        risk_level=data.get("risk_level", "medium"),
        tags=data.get("tags"),
        version=data.get("version", "1.0.0"),
    )
    return _ok(sp.to_dict(), 201)


@app.post("/api/v1/ft/evaluation-matrix/golden-set")
def ft_cem_create_golden_set():
    data = _body()
    required = ["name", "records"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    gs = _cem_controller.create_golden_set(
        name=data["name"],
        records=data["records"],
        version=data.get("version", "1.0.0"),
    )
    return _ok(gs.to_dict(), 201)


@app.post("/api/v1/ft/evaluation-matrix/evaluate")
def ft_cem_evaluate():
    data = _body()
    required = ["run_id", "checkpoint_id", "model_version"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    now = time.time()
    report = _cem_controller.run_evaluation(
        run_id=data["run_id"],
        checkpoint_id=data["checkpoint_id"],
        model_version=data["model_version"],
        window_start=float(data.get("window_start", now - 3600)),
        window_end=float(data.get("window_end", now)),
        trigger_evolution=bool(data.get("trigger_evolution", False)),
    )
    return _ok(report.to_dict())


@app.post("/api/v1/ft/evaluation-matrix/human-review")
def ft_cem_human_review():
    data = _body()
    required = ["sample_id", "reviewer_role", "correctness", "helpfulness", "safety"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    review = HumanReview(
        sample_id=data["sample_id"],
        reviewer_role=data["reviewer_role"],
        correctness=int(data["correctness"]),
        helpfulness=int(data["helpfulness"]),
        safety=int(data["safety"]),
        fairness=int(data.get("fairness", 0)),
        comments=data.get("comments", ""),
    )
    _cem_controller.add_human_review(review)
    return _ok(review.to_dict(), 201)


@app.post("/api/v1/ft/evaluation-matrix/user-feedback")
def ft_cem_user_feedback():
    data = _body()
    required = ["session_id", "feedback_type"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    fb = _cem_controller.ingest_user_feedback(data)
    return _ok(fb.to_dict(), 201)


@app.get("/api/v1/ft/evaluation-matrix/reports/<report_id>")
def ft_cem_get_report(report_id: str):
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    report = _cem_controller.get_report(report_id)
    if not report:
        return _err("report no encontrado", 404)
    return _ok(report.to_dict())


@app.get("/api/v1/ft/evaluation-matrix/prometheus")
def ft_cem_prometheus():
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    return _cem_controller.render_prometheus()


@app.get("/api/v1/ft/evaluation-matrix/logs")
def ft_cem_logs():
    if _cem_controller is None:
        return _err("evaluation matrix controller no configurado", 503)
    return _ok(_cem_controller.get_logs())


# ---------------------------------------------------------------------------
# Resilient Multi-Step Recovery endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/runtime/recovery/register-tool")
def ft_recovery_register_tool():
    data = _body()
    required = ["tool_name"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)
    _recovery_controller.register_tool(
        tool_name=data["tool_name"],
        input_schema=data.get("input_schema"),
        output_schema=data.get("output_schema"),
    )
    return _ok({"tool_name": data["tool_name"], "registered": True}, 201)


@app.post("/api/v1/runtime/recovery/invoke")
def ft_recovery_invoke():
    data = _body()
    required = ["run_id", "step_id", "tool_name", "params"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)

    def _fn(**kwargs: Any) -> Any:
        # Simulation hook: success if params contain 'expected_value'
        if kwargs.get("expected_value"):
            return {"result": kwargs["expected_value"]}
        raise TimeoutError("simulated tool timeout")

    report = _recovery_controller.invoke(
        run_id=data["run_id"],
        step_id=data["step_id"],
        tool_name=data["tool_name"],
        fn=_fn,
        params=data["params"],
        completed_steps=data.get("completed_steps", []),
        partial_state=data.get("partial_state", {}),
    )
    return _ok(report.to_dict())


@app.get("/api/v1/runtime/recovery/reports/<report_id>")
def ft_recovery_get_report(report_id: str):
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)
    report = _recovery_controller.get_report(report_id)
    if not report:
        return _err("report no encontrado", 404)
    return _ok(report.to_dict())


@app.get("/api/v1/runtime/recovery/reports")
def ft_recovery_list_reports():
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)
    return _ok([r.to_dict() for r in _recovery_controller.list_reports()])


@app.get("/api/v1/runtime/recovery/prometheus")
def ft_recovery_prometheus():
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)
    return _recovery_controller.render_prometheus()


@app.get("/api/v1/runtime/recovery/logs")
def ft_recovery_logs():
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)
    return _ok(_recovery_controller.get_logs())


@app.post("/api/v1/runtime/recovery/hitl-decide")
def ft_recovery_hitl_decide():
    data = _body()
    required = ["escalation_id", "operator_decision"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _recovery_controller is None:
        return _err("recovery controller no configurado", 503)
    record = _recovery_controller.decide_hitl(data["escalation_id"], data["operator_decision"])
    if not record:
        return _err("escalation no encontrada", 404)
    return _ok(record.to_dict())


# ---------------------------------------------------------------------------
# Compliance as Code endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/compliance/prompt/commit")
def ft_cac_prompt_commit():
    data = _body()
    required = ["prompt_name", "content", "author"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    pv = _cac_controller.commit_prompt(
        prompt_name=data["prompt_name"],
        content=data["content"],
        author=data["author"],
        regulatory_change=bool(data.get("regulatory_change", False)),
        approved_by=data.get("approved_by"),
        commit_message=data.get("commit_message", ""),
    )
    return _ok(pv.to_dict(), 201)


@app.post("/api/v1/compliance/prompt/approve")
def ft_cac_prompt_approve():
    data = _body()
    required = ["prompt_name", "version_id", "approver"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    pv = _cac_controller.approve_prompt(data["prompt_name"], data["version_id"], data["approver"])
    if not pv:
        return _err("version no encontrada", 404)
    return _ok(pv.to_dict())


@app.get("/api/v1/compliance/prompt/history/<prompt_name>")
def ft_cac_prompt_history(prompt_name: str):
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    return _ok([v.to_dict() for v in _cac_controller.prompt_history(prompt_name)])


@app.post("/api/v1/compliance/dataset/register")
def ft_cac_dataset_register():
    data = _body()
    required = ["dataset_id", "source"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    lineage = _cac_controller.register_dataset(
        dataset_id=data["dataset_id"],
        source=data["source"],
        transformations=data.get("transformations"),
        consent_tags=data.get("consent_tags"),
        retention_hours=float(data.get("retention_hours", 168.0)),
        purpose=data.get("purpose", ""),
        privacy_controls=data.get("privacy_controls"),
    )
    return _ok(lineage.to_dict(), 201)


@app.post("/api/v1/compliance/dataset/transformation")
def ft_cac_dataset_transformation():
    data = _body()
    required = ["dataset_id", "name", "description"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    lineage = _cac_controller.add_dataset_transformation(
        dataset_id=data["dataset_id"],
        name=data["name"],
        description=data["description"],
        tool=data.get("tool", ""),
        params=data.get("params"),
    )
    if not lineage:
        return _err("dataset no encontrado", 404)
    return _ok(lineage.to_dict())


@app.get("/api/v1/compliance/dataset/<dataset_id>")
def ft_cac_dataset_get(dataset_id: str):
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    lineage = _cac_controller.get_dataset_lineage(dataset_id)
    if not lineage:
        return _err("dataset no encontrado", 404)
    return _ok(lineage.to_dict())


@app.post("/api/v1/compliance/access/grant")
def ft_cac_access_grant():
    data = _body()
    required = ["role", "resource", "action"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    _cac_controller.grant_role(
        role=data["role"],
        resource=data["resource"],
        action=data["action"],
        environments=data.get("environments"),
    )
    return _ok({"granted": True}, 201)


@app.post("/api/v1/compliance/access/evaluate")
def ft_cac_access_evaluate():
    data = _body()
    required = ["requester_id", "roles", "resource", "action", "environment"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    decision = _cac_controller.evaluate_access(
        requester_id=data["requester_id"],
        roles=data["roles"],
        resource=data["resource"],
        action=data["action"],
        environment=data["environment"],
        oidc_claims=data.get("oidc_claims"),
        tenant=data.get("tenant", ""),
    )
    return _ok(decision.to_dict())


@app.post("/api/v1/compliance/inference/record")
def ft_cac_inference_record():
    data = _body()
    required = [
        "request_id", "session_id", "requester_id", "requester_roles",
        "artifact_bundle", "input_text", "output_text",
        "access_decision", "policies_applied",
    ]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    from compliance_as_code.models_compliance import ArtifactBundle
    bundle = ArtifactBundle(**data["artifact_bundle"])
    rec = _cac_controller.record_inference(
        request_id=data["request_id"],
        session_id=data["session_id"],
        requester_id=data["requester_id"],
        requester_roles=data["requester_roles"],
        artifact_bundle=bundle,
        input_text=data["input_text"],
        output_text=data["output_text"],
        access_decision=data["access_decision"],
        policies_applied=data["policies_applied"],
        pii_detected=bool(data.get("pii_detected", False)),
        guardrail_violations=data.get("guardrail_violations"),
        e_discovery_tag=data.get("e_discovery_tag", ""),
    )
    return _ok(rec.to_dict(), 201)


@app.get("/api/v1/compliance/inference/query")
def ft_cac_inference_query():
    args = __import__("flask").request.args
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    records = _cac_controller.query_inference_audit(
        request_id=args.get("request_id", ""),
        session_id=args.get("session_id", ""),
        requester_id=args.get("requester_id", ""),
        tag=args.get("tag", ""),
    )
    return _ok([r.to_dict() for r in records])


@app.get("/api/v1/compliance/ledger/verify")
def ft_cac_ledger_verify():
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    return _ok({"valid": _cac_controller.verify_ledger()})


@app.post("/api/v1/compliance/metrics/ingest")
def ft_cac_metrics_ingest():
    data = _body()
    required = ["metric_name", "value"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    alerts = _cac_controller.ingest_metric(data["metric_name"], float(data["value"]))
    return _ok({"alerts": [a.to_dict() for a in alerts]})


@app.post("/api/v1/compliance/alerts/acknowledge")
def ft_cac_alert_ack():
    data = _body()
    required = ["alert_id"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    alert = _cac_controller.acknowledge_alert(data["alert_id"])
    if not alert:
        return _err("alerta no encontrada", 404)
    return _ok(alert.to_dict())


@app.get("/api/v1/compliance/report")
def ft_cac_report():
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    return _ok(_cac_controller.compliance_report())


@app.get("/api/v1/compliance/dashboard")
def ft_cac_dashboard():
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    return _ok(_cac_controller.dashboard())


@app.get("/api/v1/compliance/rules")
def ft_cac_rules():
    if _cac_controller is None:
        return _err("compliance controller no configurado", 503)
    return _ok([r.to_dict() for r in _cac_controller.list_rules()])


# ---------------------------------------------------------------------------
# Continuous Improvement & Feedback Loop endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/ci/feedback")
def ft_ci_feedback():
    data = _body()
    required = ["source", "category"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    item = _ci_controller.ingest_feedback(data)
    return _ok(item.to_dict(), 201)


@app.post("/api/v1/ci/analyze")
def ft_ci_analyze():
    data = _body()
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    from continuous_improvement.models_ci import ExecutionLogRef, IncidentRef
    log_refs = [ExecutionLogRef(**r) for r in data.get("log_refs", [])]
    incident_refs = [IncidentRef(**r) for r in data.get("incident_refs", [])]
    result = _ci_controller.run_analysis(log_refs=log_refs, incident_refs=incident_refs)
    return _ok(result)


@app.post("/api/v1/ci/recommendations/approve")
def ft_ci_approve_recommendation():
    data = _body()
    required = ["queue_item_id", "reviewer"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    item = _ci_controller.approve_recommendation(
        data["queue_item_id"], data["reviewer"], data.get("notes", "")
    )
    if not item:
        return _err("item no encontrado", 404)
    return _ok(item.to_dict())


@app.post("/api/v1/ci/recommendations/reject")
def ft_ci_reject_recommendation():
    data = _body()
    required = ["queue_item_id", "reviewer"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    item = _ci_controller.reject_recommendation(
        data["queue_item_id"], data["reviewer"], data.get("notes", "")
    )
    if not item:
        return _err("item no encontrado", 404)
    return _ok(item.to_dict())


@app.get("/api/v1/ci/recommendations")
def ft_ci_recommendations():
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    return _ok(_ci_controller.list_recommendations())


@app.get("/api/v1/ci/recommendations/pending")
def ft_ci_recommendations_pending():
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    return _ok(_ci_controller.get_pending_recommendations())


@app.post("/api/v1/ci/baseline")
def ft_ci_baseline():
    data = _body()
    required = ["metric_name", "value"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    _ci_controller.register_baseline(data["metric_name"], float(data["value"]))
    return _ok({"metric_name": data["metric_name"], "baseline": data["value"]}, 201)


@app.post("/api/v1/ci/measure")
def ft_ci_measure():
    data = _body()
    required = ["recommendation_id", "metric_name", "value"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    measurement = _ci_controller.measure_effectiveness(
        data["recommendation_id"], data["metric_name"], float(data["value"])
    )
    return _ok(measurement.to_dict(), 201)


@app.get("/api/v1/ci/dashboard")
def ft_ci_dashboard():
    if _ci_controller is None:
        return _err("continuous improvement controller no configurado", 503)
    return _ok(_ci_controller.dashboard())


# ---------------------------------------------------------------------------
# Enterprise QA Driver endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/qa/run")
def ft_qa_run():
    data = _body()
    if "test_cases" not in data or not isinstance(data["test_cases"], list):
        return _err("test_cases array required")
    if _qa_driver is None:
        return _err("qa driver no configurado", 503)
    _qa_driver.reset()
    cases = [TestCase(**item) for item in data["test_cases"]]
    report = _qa_driver.run_batch(cases)
    return _ok(report.to_dict())


# ---------------------------------------------------------------------------
# Incident Management endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/incidents")
def ft_incident_create():
    data = _body()
    required = ["title", "category"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    inc = _incident_controller.create_incident(data)
    return _ok(inc.to_dict(), 201)


@app.get("/api/v1/incidents")
def ft_incident_list():
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    return _ok([i.to_dict() for i in _incident_controller.list_incidents()])


@app.get("/api/v1/incidents/<incident_id>")
def ft_incident_get(incident_id: str):
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    inc = _incident_controller.get_incident(incident_id)
    if not inc:
        return _err("incidente no encontrado", 404)
    return _ok(inc.to_dict())


@app.post("/api/v1/incidents/<incident_id>/triage")
def ft_incident_triage(incident_id: str):
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    inc = _incident_controller.triage(incident_id)
    if not inc:
        return _err("incidente no encontrado", 404)
    return _ok(inc.to_dict())


@app.post("/api/v1/incidents/<incident_id>/contain")
def ft_incident_contain(incident_id: str):
    data = _body()
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    inc = _incident_controller.contain(incident_id, data.get("actions", []))
    if not inc:
        return _err("incidente no encontrado", 404)
    return _ok(inc.to_dict())


@app.post("/api/v1/incidents/<incident_id>/resolve")
def ft_incident_resolve(incident_id: str):
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    inc = _incident_controller.resolve(incident_id)
    if not inc:
        return _err("incidente no encontrado", 404)
    return _ok(inc.to_dict())


@app.post("/api/v1/incidents/<incident_id>/alerts")
def ft_incident_alert(incident_id: str):
    data = _body()
    required = ["metric", "value", "threshold"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    alert = _incident_controller.create_alert(
        incident_id, data["metric"], float(data["value"]), float(data["threshold"])
    )
    if not alert:
        return _err("incidente no encontrado", 404)
    return _ok(alert.to_dict(), 201)


@app.post("/api/v1/incidents/oncall")
def ft_incident_oncall():
    data = _body()
    required = ["name", "team"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    _incident_controller.add_oncall(
        name=data["name"],
        team=data["team"],
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        active=data.get("active", True),
    )
    return _ok({"registered": True}, 201)


@app.post("/api/v1/incidents/<incident_id>/communicate")
def ft_incident_communicate(incident_id: str):
    data = _body()
    required = ["channel", "recipient_team", "template_name", "content"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    rec = _incident_controller.communicate(
        incident_id=incident_id,
        channel=data["channel"],
        recipient_team=data["recipient_team"],
        template_name=data["template_name"],
        content=data["content"],
    )
    return _ok(rec.to_dict(), 201)


@app.post("/api/v1/incidents/<incident_id>/runbook")
def ft_incident_runbook(incident_id: str):
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    result = _incident_controller.execute_runbook(incident_id)
    if not result:
        return _err("incidente no encontrado", 404)
    return _ok(result)


@app.post("/api/v1/incidents/<incident_id>/post-mortem")
def ft_incident_post_mortem(incident_id: str):
    data = _body()
    required = ["root_cause", "failed_controls", "action_items"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    pm = _incident_controller.generate_post_mortem(
        incident_id=incident_id,
        root_cause=data["root_cause"],
        failed_controls=data["failed_controls"],
        action_items=data["action_items"],
        lessons_learned=data.get("lessons_learned", ""),
        mitigation_time_minutes=float(data.get("mitigation_time_minutes", 0)),
        recovery_time_minutes=float(data.get("recovery_time_minutes", 0)),
    )
    if not pm:
        return _err("incidente no encontrado", 404)
    return _ok(pm.to_dict(), 201)


@app.post("/api/v1/incidents/slos")
def ft_incident_define_slo():
    data = _body()
    required = ["sli_id", "target", "window_seconds"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    slo = _incident_controller.define_slo(
        sli_id=data["sli_id"],
        target=float(data["target"]),
        window_seconds=float(data["window_seconds"]),
        description=data.get("description", ""),
    )
    if not slo:
        return _err("SLI no registrado", 400)
    return _ok(slo.to_dict(), 201)


@app.post("/api/v1/incidents/sli/register")
def ft_incident_register_sli():
    data = _body()
    required = ["sli_id", "name", "metric", "unit"]
    missing = [f for f in required if f not in data]
    if missing:
        return _err(f"campos requeridos: {', '.join(missing)}")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    sli = _incident_controller.register_sli(
        sli_id=data["sli_id"],
        name=data["name"],
        metric=data["metric"],
        unit=data["unit"],
        description=data.get("description", ""),
    )
    return _ok(sli.to_dict(), 201)


@app.post("/api/v1/incidents/slos/<slo_id>/sample")
def ft_incident_slo_sample(slo_id: str):
    data = _body()
    if "good" not in data:
        return _err("good boolean required")
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    _incident_controller.record_slo_sample(slo_id, bool(data["good"]))
    budget = _incident_controller.get_error_budget(slo_id)
    return _ok(budget if budget else {})


@app.get("/api/v1/incidents/dashboard")
def ft_incident_dashboard():
    if _incident_controller is None:
        return _err("incident controller no configurado", 503)
    return _ok(_incident_controller.dashboard())


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def create_app(
    orchestrator: Optional[AgentRuntimeOrchestrator] = None,
    ft_controller: Optional[FineTuningController] = None,
) -> Flask:
    global _orchestrator, _ft_controller
    if orchestrator is None:
        orchestrator = AgentRuntimeOrchestrator()
    if ft_controller is None:
        ft_controller = FineTuningController(
            privacy_controller=PrivacyPreservingLLMOpsController(),
            quality_gate_controller=QualityGateController(),
        )
    global _em_controller
    if _em_controller is None:
        _em_controller = ExtrinsicMetricsController()
    global _cem_controller
    if _cem_controller is None:
        _cem_controller = EvaluationMatrixController()
    global _recovery_controller
    if _recovery_controller is None:
        _recovery_controller = RecoveryOrchestrator()
    global _cac_controller
    if _cac_controller is None:
        _cac_controller = ComplianceController()
    global _ci_controller
    if _ci_controller is None:
        _ci_controller = ContinuousImprovementController()
    global _qa_driver
    if _qa_driver is None:
        _qa_driver = EnterpriseQADriver()
    global _incident_controller
    if _incident_controller is None:
        _incident_controller = IncidentManagementController()
    _orchestrator = orchestrator
    _ft_controller = ft_controller
    return app


def main() -> None:
    create_app()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5703
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
