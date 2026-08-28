"""API Flask para UC-271 — Multi-Agent K8s con Seguridad y HPA.

Endpoints:
- /health
- /api/v1/schema (card views entrada/salida)
- /api/v1/task/run (ejecutar tarea con contract net + security + HPA)
- /api/v1/hpa/evaluate (evaluar métricas y obtener decisión de escalado)
- /api/v1/hpa/status (estado actual del HPA)
- /api/v1/security/generate (generar políticas de seguridad)
- /api/v1/security/validate (validar configuración de agente)
- /api/v1/manifests/generate (generar manifiestos K8s)
- /api/v1/audit (trail de auditoría de seguridad)
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from config import get_config
from hpa_manager import HPAManager
from manifest_generator import ManifestGenerator
from models import AgentProfile, AgentRole, PodMetrics, TaskRequest
from security import SecurityManager
from supervisor import SupervisorAgent, WorkerAgent

app = Flask(__name__)

_config = get_config()

# Workers por defecto
_default_profiles = [
    AgentProfile(name="researcher", role=AgentRole.researcher, skill=0.95, cost=1.2, latency_ms=250, replicas=2, service_account="researcher-sa"),
    AgentProfile(name="coder", role=AgentRole.coder, skill=0.90, cost=1.0, latency_ms=200, replicas=2, service_account="coder-sa"),
    AgentProfile(name="reviewer", role=AgentRole.reviewer, skill=0.92, cost=1.1, latency_ms=180, replicas=1, service_account="reviewer-sa"),
]
_workers = [WorkerAgent(p) for p in _default_profiles]
_supervisor = SupervisorAgent(_workers, _config)
_security = SecurityManager(_config.security, _config.namespace)
_manifest_gen = ManifestGenerator(_config)


def _ok(data: Any, status: int = 200) -> tuple:
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}), status


def _err(msg: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": msg}), status


def _run_async(coro):
    """Helper para ejecutar coroutines en Flask (sync)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc271-multiagent-k8s-security-hpa", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/task/run", methods=["POST"])
def run_task():
    """Ejecuta una tarea con contract net + security + HPA."""
    data = request.get_json(silent=True) or {}
    task = data.get("task")
    if not task:
        return _err("'task' is required", 400)
    req = TaskRequest(task=task, resource=data.get("resource"), priority=data.get("priority", 5))
    result = _run_async(_supervisor.run_task(req))
    return _ok(result.model_dump(mode="json"))


@app.route("/api/v1/hpa/evaluate", methods=["POST"])
def hpa_evaluate():
    """Evalúa métricas y retorna decisión de escalado."""
    data = request.get_json(silent=True) or {}
    try:
        metrics = PodMetrics.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid metrics: {exc}", 400)
    decision = _supervisor.hpa.evaluate(metrics)
    return _ok(decision.model_dump(mode="json"))


@app.route("/api/v1/hpa/status", methods=["GET"])
def hpa_status():
    """Estado actual del HPA de todos los agentes."""
    statuses = _supervisor.get_hpa_statuses()
    return _ok([s.model_dump(mode="json") for s in statuses])


@app.route("/api/v1/security/generate", methods=["POST"])
def security_generate():
    """Genera políticas de seguridad para un agente."""
    data = request.get_json(silent=True) or {}
    try:
        profile = AgentProfile.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid agent profile: {exc}", 400)
    rbac = _security.generate_rbac(profile)
    netpol = _security.generate_network_policy(profile, [w.name for w in _workers])
    sa = _security.generate_service_account(profile)
    sec_ctx = _security.generate_security_context(profile)
    return _ok({
        "rbac": rbac.model_dump(mode="json"),
        "network_policy": netpol.model_dump(mode="json"),
        "service_account": sa.model_dump(mode="json"),
        "security_context": sec_ctx.model_dump(mode="json"),
    })


@app.route("/api/v1/security/validate", methods=["POST"])
def security_validate():
    """Valida que un agente cumple con políticas de seguridad."""
    data = request.get_json(silent=True) or {}
    try:
        profile = AgentProfile.model_validate(data)
    except Exception as exc:
        return _err(f"Invalid agent profile: {exc}", 400)
    violations = _security.validate_agent_security(profile)
    return _ok({"agent": profile.name, "valid": len(violations) == 0, "violations": violations})


@app.route("/api/v1/manifests/generate", methods=["POST"])
def manifests_generate():
    """Genera manifiestos K8s para una lista de agentes."""
    data = request.get_json(silent=True) or {}
    agents_data = data.get("agents", [])
    if not agents_data:
        agents_data = [p.model_dump() for p in _default_profiles]
    try:
        agents = [AgentProfile.model_validate(a) for a in agents_data]
    except Exception as exc:
        return _err(f"Invalid agents: {exc}", 400)
    manifests = _manifest_gen.generate_all(agents)
    return _ok([m.model_dump(mode="json") for m in manifests])


@app.route("/api/v1/audit", methods=["GET"])
def audit_trail():
    """Auditoría de seguridad."""
    return _ok(_supervisor.get_security_audit())


# ============================================================
# Card Views
# ============================================================

INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/task/run",
        "description": "Ejecutar tarea con contract net protocol + seguridad + HPA auto-scaling.",
        "parameters": [
            {"name": "task", "type": "string", "required": True, "description": "Descripción de la tarea a ejecutar"},
            {"name": "resource", "type": "string", "required": False, "description": "Recurso objetivo"},
            {"name": "priority", "type": "int (0-10)", "required": False, "default": 5},
        ],
    },
    {
        "endpoint": "POST /api/v1/hpa/evaluate",
        "description": "Evaluar métricas de un agente y obtener decisión de escalado HPA.",
        "parameters": [
            {"name": "agent_name", "type": "string", "required": True},
            {"name": "cpu_percent", "type": "float (0-100)", "required": True},
            {"name": "memory_percent", "type": "float (0-100)", "required": True},
            {"name": "queue_depth", "type": "int", "required": False, "default": 0},
            {"name": "active_tasks", "type": "int", "required": False, "default": 0},
            {"name": "replicas_current", "type": "int", "required": False, "default": 1},
        ],
    },
    {
        "endpoint": "POST /api/v1/security/generate",
        "description": "Genera políticas de seguridad (RBAC, NetworkPolicy, ServiceAccount, SecurityContext) para un agente.",
        "parameters": [
            {"name": "name", "type": "string", "required": True},
            {"name": "role", "type": "string", "required": True, "enum": ["supervisor", "researcher", "coder", "reviewer", "executor"]},
            {"name": "skill", "type": "float (0-1)", "required": True},
            {"name": "cost", "type": "float", "required": True},
            {"name": "latency_ms", "type": "int", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/security/validate",
        "description": "Valida que un agente cumple con las políticas de seguridad del cluster.",
        "parameters": [
            {"name": "name", "type": "string", "required": True},
            {"name": "role", "type": "string", "required": True},
            {"name": "skill", "type": "float", "required": True},
            {"name": "cost", "type": "float", "required": True},
            {"name": "latency_ms", "type": "int", "required": True},
            {"name": "service_account", "type": "string", "required": False},
            {"name": "replicas", "type": "int", "required": False, "default": 1},
        ],
    },
    {
        "endpoint": "POST /api/v1/manifests/generate",
        "description": "Genera manifiestos K8s completos (Deployment, HPA, NetworkPolicy, RBAC, ServiceAccount).",
        "parameters": [
            {"name": "agents", "type": "list[AgentProfile]", "required": False, "description": "Si vacío, usa agentes por defecto"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/task/run",
        "description": "Resultado de ejecución con contract net, decisión HPA y contexto de seguridad.",
        "fields": [
            {"name": "task_id", "type": "UUID"},
            {"name": "task", "type": "string"},
            {"name": "winner", "type": "string"},
            {"name": "proposals", "type": "list[Proposal]"},
            {"name": "execution", "type": "object"},
            {"name": "scaling_decision", "type": "ScalingDecision"},
            {"name": "security_context", "type": "SecurityContext"},
        ],
    },
    {
        "endpoint": "POST /api/v1/hpa/evaluate",
        "description": "Decisión de escalado HPA.",
        "fields": [
            {"name": "decision_id", "type": "UUID"},
            {"name": "agent_name", "type": "string"},
            {"name": "direction", "type": "string", "enum": ["scale_up", "scale_down", "no_change"]},
            {"name": "current_replicas", "type": "int"},
            {"name": "desired_replicas", "type": "int"},
            {"name": "reason", "type": "string"},
            {"name": "cooldown_remaining_sec", "type": "int"},
        ],
    },
    {
        "endpoint": "POST /api/v1/security/generate",
        "description": "Políticas de seguridad generadas.",
        "fields": [
            {"name": "rbac", "type": "RBACPolicy"},
            {"name": "network_policy", "type": "NetworkPolicy"},
            {"name": "service_account", "type": "ServiceAccountConfig"},
            {"name": "security_context", "type": "SecurityContext"},
        ],
    },
    {
        "endpoint": "POST /api/v1/security/validate",
        "description": "Resultado de validación de seguridad.",
        "fields": [
            {"name": "agent", "type": "string"},
            {"name": "valid", "type": "bool"},
            {"name": "violations", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/manifests/generate",
        "description": "Lista de manifiestos K8s generados.",
        "fields": [
            {"name": "kind", "type": "string"},
            {"name": "api_version", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "namespace", "type": "string"},
            {"name": "content", "type": "object (full K8s manifest)"},
        ],
    },
]


if __name__ == "__main__":
    port = int(os.getenv("UC271_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
