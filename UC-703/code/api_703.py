"""
UC-703 — API REST Flask con card views de entrada/salida.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_runtime_orchestrator import AgentRuntimeOrchestrator

# Preferir Flask local si existe, sino mock mínimo.
try:
    from flask import Flask, jsonify, request
except Exception as exc:  # pragma: no cover
    print(f"Flask no disponible: {exc}")
    sys.exit(1)


app = Flask(__name__)
_orchestrator: Optional[AgentRuntimeOrchestrator] = None


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
# Bootstrap
# ---------------------------------------------------------------------------

def create_app(orchestrator: Optional[AgentRuntimeOrchestrator] = None) -> Flask:
    global _orchestrator
    if orchestrator is None:
        orchestrator = AgentRuntimeOrchestrator()
    _orchestrator = orchestrator
    return app


def main() -> None:
    create_app()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5703
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
