"""UC-317 — API REST Flask para el kernel AIOS-style."""
from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from agent_kernel import AgentKernel
from kernel_config import KernelConfig
from syscalls import SyscallOp, SyscallRequest, SyscallType

app = Flask(__name__)
kernel = AgentKernel()

# ---------------------------------------------------------------------------
# Cards de entrada
# ---------------------------------------------------------------------------
INPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/kernel/sessions": {
        "endpoint": "POST /api/v1/kernel/sessions",
        "description": "Crea una sesión de agente con roles, modelo y system_prompt.",
        "parameters": [
            {"name": "name", "type": "string", "required": True, "example": "research-agent"},
            {"name": "roles", "type": "list[string]", "required": False, "default": ["user"], "example": ["user", "developer"]},
            {"name": "model", "type": "string", "required": False, "default": "mock", "example": "mock"},
            {"name": "system_prompt", "type": "string", "required": False, "default": "You are a helpful AI agent."},
            {"name": "metadata", "type": "object", "required": False, "default": {}},
        ],
    },
    "POST /api/v1/kernel/chat": {
        "endpoint": "POST /api/v1/kernel/chat",
        "description": "Envía un mensaje al agente y obtiene respuesta del LLM (con tools y memoria).",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "agent_abc12345"},
            {"name": "message", "type": "string", "required": True, "example": "hello"},
            {"name": "use_tools", "type": "boolean", "required": False, "default": True},
        ],
    },
    "POST /api/v1/kernel/syscall": {
        "endpoint": "POST /api/v1/kernel/syscall",
        "description": "Ejecuta un syscall del kernel (LLM, memory, tool, storage, schedule).",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "syscall_type", "type": "string", "required": True, "enum": ["llm", "memory", "tool", "storage", "schedule"]},
            {"name": "operation", "type": "string", "required": True, "example": "llm.generate"},
            {"name": "payload", "type": "object", "required": True, "example": {"messages": [{"role": "user", "content": "hello"}]}},
        ],
    },
    "POST /api/v1/kernel/schedule": {
        "endpoint": "POST /api/v1/kernel/schedule",
        "description": "Programa una tarea para un agente.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "goal", "type": "string", "required": True, "example": "Investigate market trends"},
        ],
    },
    "POST /api/v1/kernel/tools/call": {
        "endpoint": "POST /api/v1/kernel/tools/call",
        "description": "Invoca una herramienta registrada por nombre.",
        "parameters": [
            {"name": "name", "type": "string", "required": True, "example": "calculator"},
            {"name": "args", "type": "object", "required": False, "default": {}, "example": {"expression": "2+2"}},
        ],
    },
    "POST /api/v1/kernel/storage": {
        "endpoint": "POST /api/v1/kernel/storage",
        "description": "Guarda un valor en el storage del kernel.",
        "parameters": [
            {"name": "key", "type": "string", "required": True, "example": "state"},
            {"name": "data", "type": "object", "required": True, "example": {"counter": 1}},
        ],
    },
}

# ---------------------------------------------------------------------------
# Cards de salida
# ---------------------------------------------------------------------------
OUTPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/kernel/sessions": {
        "endpoint": "POST /api/v1/kernel/sessions",
        "description": "Sesión creada con agent_id único.",
        "fields": [
            {"name": "agent_id", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "roles", "type": "list[string]"},
            {"name": "model", "type": "string"},
            {"name": "system_prompt", "type": "string"},
        ],
    },
    "POST /api/v1/kernel/chat": {
        "endpoint": "POST /api/v1/kernel/chat",
        "description": "Respuesta del agente con contenido, tool_calls y usage.",
        "fields": [
            {"name": "agent_id", "type": "string"},
            {"name": "response", "type": "string"},
            {"name": "model", "type": "string"},
            {"name": "provider", "type": "string"},
            {"name": "tool_calls", "type": "list[object]"},
            {"name": "tool_results", "type": "list[object]"},
            {"name": "usage", "type": "object"},
        ],
    },
    "POST /api/v1/kernel/syscall": {
        "endpoint": "POST /api/v1/kernel/syscall",
        "description": "Respuesta del syscall con success, result y error.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "result", "type": "any"},
            {"name": "error", "type": "string|null"},
            {"name": "metadata", "type": "object"},
        ],
    },
    "POST /api/v1/kernel/schedule": {
        "endpoint": "POST /api/v1/kernel/schedule",
        "description": "Tarea programada con task_id.",
        "fields": [
            {"name": "agent_id", "type": "string"},
            {"name": "task_id", "type": "string"},
            {"name": "goal", "type": "string"},
            {"name": "status", "type": "string"},
        ],
    },
    "POST /api/v1/kernel/tools/call": {
        "endpoint": "POST /api/v1/kernel/tools/call",
        "description": "Resultado de la herramienta.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "result", "type": "any"},
            {"name": "error", "type": "string|null"},
        ],
    },
    "POST /api/v1/kernel/storage": {
        "endpoint": "POST /api/v1/kernel/storage",
        "description": "Confirmación de guardado.",
        "fields": [
            {"name": "saved", "type": "string"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.route("/api/v1/schema", methods=["GET"])
def schema() -> Dict[str, Any]:
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/kernel/models", methods=["GET"])
def list_models() -> Dict[str, Any]:
    return jsonify({"models": kernel.llm.list_models()})


@app.route("/api/v1/kernel/tools", methods=["GET"])
def list_tools() -> Dict[str, Any]:
    return jsonify({"tools": kernel.tools.list_tools()})


@app.route("/api/v1/kernel/roles", methods=["GET"])
def list_roles() -> Dict[str, Any]:
    return jsonify({"roles": kernel.access.list_roles()})


@app.route("/api/v1/kernel/scheduler/status", methods=["GET"])
def scheduler_status() -> Dict[str, Any]:
    return jsonify(kernel.scheduler.status())


@app.route("/api/v1/kernel/sessions", methods=["POST"])
def create_session() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    session = kernel.create_session(
        name=name,
        roles=payload.get("roles", ["user"]),
        model=payload.get("model"),
        system_prompt=payload.get("system_prompt"),
        metadata=payload.get("metadata", {}),
    )
    return jsonify({
        "agent_id": session.agent_id,
        "name": session.name,
        "roles": session.roles,
        "model": session.model,
        "system_prompt": session.system_prompt,
    })


@app.route("/api/v1/kernel/chat", methods=["POST"])
def chat() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    agent_id = payload.get("agent_id")
    message = payload.get("message")
    if not agent_id or not message:
        return jsonify({"error": "agent_id and message are required"}), 400
    if not kernel.get_session(agent_id):
        return jsonify({"error": f"Agent session {agent_id} not found"}), 404
    use_tools = payload.get("use_tools", True)
    result = kernel.chat(agent_id, message, use_tools=use_tools)
    return jsonify(result)


@app.route("/api/v1/kernel/syscall", methods=["POST"])
def syscall() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    agent_id = payload.get("agent_id")
    stype = payload.get("syscall_type")
    operation = payload.get("operation")
    req_payload = payload.get("payload", {})
    if not agent_id or not stype or not operation:
        return jsonify({"error": "agent_id, syscall_type and operation are required"}), 400
    try:
        stype_enum = SyscallType(stype)
    except ValueError:
        return jsonify({"error": f"Invalid syscall_type: {stype}"}), 400
    req = SyscallRequest(
        syscall_type=stype_enum,
        operation=operation,
        payload=req_payload,
        agent_id=agent_id,
    )
    resp = kernel.syscall(req)
    return jsonify(resp.to_dict())


@app.route("/api/v1/kernel/schedule", methods=["POST"])
def schedule() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    agent_id = payload.get("agent_id")
    goal = payload.get("goal")
    if not agent_id or not goal:
        return jsonify({"error": "agent_id and goal are required"}), 400
    task = kernel.scheduler.schedule(agent_id, goal)
    return jsonify({
        "agent_id": task.agent_id,
        "task_id": task.task_id,
        "goal": task.goal,
        "status": task.status.value,
    })


@app.route("/api/v1/kernel/tools/call", methods=["POST"])
def tools_call() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    args = payload.get("args", {})
    result = kernel.tools.call(name, args)
    return jsonify(result)


@app.route("/api/v1/kernel/storage", methods=["POST"])
def storage_save() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    key = payload.get("key")
    data = payload.get("data")
    if not key or data is None:
        return jsonify({"error": "key and data are required"}), 400
    kernel.storage.save(key, data)
    return jsonify({"saved": key})


@app.route("/api/v1/kernel/storage/<key>", methods=["GET"])
def storage_load(key: str) -> Dict[str, Any]:
    data = kernel.storage.load(key)
    if data is None:
        return jsonify({"error": f"Key {key} not found"}), 404
    return jsonify({"key": key, "data": data})


@app.route("/health", methods=["GET"])
def health() -> Dict[str, Any]:
    return jsonify({"status": "ok", "service": "uc-317-kernel"})


def run_server(port: int = 5317) -> None:
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    run_server()
