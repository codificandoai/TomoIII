"""UC-314 — API REST Flask del planificador recursivo neuro-simbólico."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Flask, jsonify, request as flask_request
from prometheus_client import generate_latest

from causal_model import LLMReasoner, SymbolicCausalModel
from metrics_collector import metrics
from neuro_symbolic_integrator import NeuroSymbolicIntegrator
from tool_registry import ToolRegistry, default_tools


app = Flask(__name__)

# Instancia compartida del integrador (puede extenderse para multi-tenant)
_integrator = NeuroSymbolicIntegrator(
    scm=SymbolicCausalModel(),
    llm=LLMReasoner(),
    tool_registry=ToolRegistry(default_tools()),
)

# -----------------------------------------------------------------------------
# Cards de entrada/salida (documentación automática)
# -----------------------------------------------------------------------------
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/plan",
        "description": "Genera un plan recursivo a partir de un objetivo de alto nivel.",
        "parameters": [
            {"name": "goal", "type": "string", "required": True, "example": "Planificar una campaña de marketing para producto X"},
            {"name": "max_depth", "type": "integer", "required": False, "default": 5},
            {"name": "max_nodes", "type": "integer", "required": False, "default": 100},
            {"name": "context", "type": "object", "required": False, "default": {}},
        ],
    },
    {
        "endpoint": "POST /api/v1/plan/execute",
        "description": "Genera y ejecuta simuladamente el plan recursivo.",
        "parameters": [
            {"name": "goal", "type": "string", "required": True},
            {"name": "context", "type": "object", "required": False, "default": {}},
        ],
    },
    {
        "endpoint": "POST /api/v1/plan/evaluate",
        "description": "Evalúa un plan ya generado (plan tree JSON).",
        "parameters": [
            {"name": "plan", "type": "object", "required": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/causal/root-cause",
        "description": "Trazado de causa raíz neuro-simbólico (LLM + SCM).",
        "parameters": [
            {"name": "task_id", "type": "string", "required": True},
            {"name": "failed_tool", "type": "string", "required": True},
            {"name": "error_msg", "type": "string", "required": True},
            {"name": "context", "type": "string", "required": False, "default": ""},
        ],
    },
    {
        "endpoint": "POST /api/v1/causal/graph",
        "description": "Consulta o modifica el grafo causal (añadir dependencia o estado).",
        "parameters": [
            {"name": "action", "type": "string", "required": True, "enum": ["get", "add_dependency", "set_state"]},
            {"name": "parent", "type": "string", "required": False},
            {"name": "child", "type": "string", "required": False},
            {"name": "node", "type": "string", "required": False},
            {"name": "state", "type": "string", "required": False},
        ],
    },
    {
        "endpoint": "GET /api/v1/tools",
        "description": "Lista de herramientas disponibles para el planificador.",
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/plan",
        "description": "Plan recursivo con métricas de calidad.",
        "fields": [
            {"name": "goal", "type": "string"},
            {"name": "plan", "type": "object"},
            {"name": "metrics", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/plan/execute",
        "description": "Resultado de la ejecución simulada del plan.",
        "fields": [
            {"name": "goal", "type": "string"},
            {"name": "plan", "type": "object"},
            {"name": "metrics", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/plan/evaluate",
        "description": "Métricas de auditoría del plan.",
        "fields": [
            {"name": "total_nodes", "type": "integer"},
            {"name": "executable_leaves", "type": "integer"},
            {"name": "blocked_leaves", "type": "integer"},
            {"name": "max_depth", "type": "integer"},
            {"name": "executability_ratio", "type": "number"},
            {"name": "causal_consistency", "type": "number"},
            {"name": "audit_score", "type": "number"},
            {"name": "recommendations", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "POST /api/v1/causal/root-cause",
        "description": "Resultado del trazado de causa raíz LLM vs SCM.",
        "fields": [
            {"name": "task_id", "type": "string"},
            {"name": "failed_tool", "type": "string"},
            {"name": "llm_hypothesis", "type": "object"},
            {"name": "formal_causal_trace", "type": "list[string]"},
            {"name": "actual_root_cause", "type": "string"},
            {"name": "llm_scm_agreement", "type": "boolean"},
            {"name": "scm_intervention", "type": "boolean"},
            {"name": "latency_seconds", "type": "number"},
        ],
    },
]


def _ok(payload: Any) -> tuple:
    return jsonify({"status": "ok", "data": payload}), 200


def _err(message: str, code: int = 400) -> tuple:
    return jsonify({"status": "error", "message": message}), code


@app.route("/", methods=["GET"])
def index() -> tuple:
    return _ok({
        "service": "UC-314 Neuro-Symbolic Recursive Planner",
        "input_cards": INPUT_CARDS,
        "output_cards": OUTPUT_CARDS,
    })


@app.route("/api/v1/tools", methods=["GET"])
def list_tools() -> tuple:
    return _ok(_integrator.registry.list_tools())


@app.route("/api/v1/plan", methods=["POST"])
def plan() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    goal = payload.get("goal")
    if not goal:
        return _err("'goal' es obligatorio")
    # Actualizar límites del planificador si se indican
    _integrator.planner.max_depth = max(1, min(int(payload.get("max_depth", 5)), 10))
    _integrator.planner.max_nodes = max(1, min(int(payload.get("max_nodes", 100)), 500))
    result = _integrator.plan_and_evaluate(goal, payload.get("context", {}))
    return _ok(result)


@app.route("/api/v1/plan/execute", methods=["POST"])
def execute_plan() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    goal = payload.get("goal")
    if not goal:
        return _err("'goal' es obligatorio")
    result = _integrator.execute_plan(goal, payload.get("context", {}))
    return _ok(result)


@app.route("/api/v1/plan/evaluate", methods=["POST"])
def evaluate_plan() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    plan_data = payload.get("plan")
    if not plan_data:
        return _err("'plan' es obligatorio")
    # Reconstruir árbol a partir del dict para evaluar
    from recursive_planner import PlanNode
    root = _dict_to_plan_node(plan_data)
    metrics = _integrator.evaluator.evaluate(root)
    return _ok(metrics.to_dict())


def _dict_to_plan_node(data: Dict[str, Any]) -> PlanNode:
    """Construye recursivamente un PlanNode desde su representación dict."""
    from recursive_planner import PlanNode
    children = [_dict_to_plan_node(c) for c in data.get("children", [])]
    payload = dict(data)
    payload["children"] = children
    return PlanNode(**payload)


@app.route("/api/v1/causal/root-cause", methods=["POST"])
def root_cause() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    task_id = payload.get("task_id")
    failed_tool = payload.get("failed_tool")
    error_msg = payload.get("error_msg")
    if not (task_id and failed_tool and error_msg):
        return _err("'task_id', 'failed_tool' y 'error_msg' son obligatorios")
    result = _integrator.handle_breakdown(
        task_id=task_id,
        failed_tool=failed_tool,
        error_msg=error_msg,
        context=payload.get("context", ""),
    )
    return _ok(result)


@app.route("/api/v1/causal/graph", methods=["POST"])
def causal_graph() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    action = payload.get("action", "get")
    scm = _integrator.scm
    if action == "get":
        return _ok(scm.to_dict())
    if action == "add_dependency":
        parent = payload.get("parent")
        child = payload.get("child")
        if not (parent and child):
            return _err("'parent' y 'child' son obligatorios")
        scm.add_dependency(parent, child)
        if scm.has_cycle():
            # deshacer simple no implementado; advertimos
            return _err("La dependencia crea un ciclo en el grafo causal", 422)
        return _ok({"added": True, "graph": scm.to_dict()})
    if action == "set_state":
        node = payload.get("node")
        state = payload.get("state")
        if not (node and state):
            return _err("'node' y 'state' son obligatorios")
        scm.set_node_state(node, state)
        return _ok({"updated": True, "graph": scm.to_dict()})
    return _err("Acción no soportada", 400)


@app.route("/metrics", methods=["GET"])
def metrics_endpoint() -> Any:
    return generate_latest()


@app.route("/api/v1/cards", methods=["GET"])
def cards() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


def main() -> int:
    port = int(os.environ.get("UC314_PORT", 5297))
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
