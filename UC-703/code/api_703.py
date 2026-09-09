"""
UC-703 — API REST Flask con card views de entrada/salida.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_runtime_orchestrator import AgentRuntimeOrchestrator
from fine_tuning.controller import FineTuningController
from fine_tuning.models_ft import FeedbackItem

# Preferir Flask local si existe, sino mock mínimo.
try:
    from flask import Flask, jsonify, request
except Exception as exc:  # pragma: no cover
    print(f"Flask no disponible: {exc}")
    sys.exit(1)


app = Flask(__name__)
_orchestrator: Optional[AgentRuntimeOrchestrator] = None
_ft_controller: Optional[FineTuningController] = None


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
        ft_controller = FineTuningController()
    _orchestrator = orchestrator
    _ft_controller = ft_controller
    return app


def main() -> None:
    create_app()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5703
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
