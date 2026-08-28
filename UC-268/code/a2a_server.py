"""Servidor A2A con Flask para UC-268.

Exposición:
- /.well-known/agent.json (Agent Card, sin autenticación).
- /a2a (JSON-RPC 2.0 para tasks/send, tasks/get, tasks/cancel, autenticado).
- /api/v1/schema (card views de entrada/salida).
- /api/v1/security/token (emisión de JWT de prueba).
- /api/v1/agents (agentes registrados en el bus interno).
- /api/v1/communication/send (enviar un mensaje por el bus interno).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from agents import (
    CriticAgent,
    ExecutorAgent,
    PlannerAgent,
    SimulatorAgent,
    UserProxyAgent,
)
from config import AppConfig, get_config
from message_bus import MessageBus
from models import (
    AgentCapability,
    AgentCard,
    AgentProvider,
    AgentSecurityScheme,
    FlightSearchRequest,
    JSONRPCRequest,
    JSONRPCResponse,
    Message,
    Part,
    Priority,
    SecuritySchemeType,
    Task,
    TaskStatus,
)
from security import SecurityManager, require_auth


app = Flask(__name__)


def _ok(data: Any, status: int = 200) -> tuple:
    return (
        jsonify(
            {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
        ),
        status,
    )


def _err(message: str, status: int = 400) -> tuple:
    return jsonify({"status": "error", "message": message}), status


def build_bus(config: AppConfig) -> MessageBus:
    """Construye el bus interno con los agentes del sistema."""
    bus = MessageBus(config.bus)
    bus.register(PlannerAgent(bus))
    bus.register(SimulatorAgent(bus))
    bus.register(CriticAgent(bus))
    bus.register(ExecutorAgent(bus))
    bus.register(UserProxyAgent(bus))
    return bus


# Inicializar bus global para el servidor
_app_config = get_config()
_bus = build_bus(_app_config)


def get_agent_card(config: AppConfig = _app_config) -> AgentCard:
    return AgentCard(
        name=config.agent.agent_name,
        description="Agente A2A de Mustiamente para planificación de viajes segura y colaborativa.",
        url=config.agent.agent_url,
        version=config.agent.version,
        provider=AgentProvider(
            organization="Codificando.AI / Mustiamente",
            url="https://mustiamente.ai",
        ),
        documentation_url="https://github.com/a2aproject/A2A",
        capabilities=[
            AgentCapability(
                skill_id="flight.search",
                name="Búsqueda de vuelos",
                description="Busca opciones de vuelo entre dos aeropuertos.",
                tags=["flights", "search"],
                scopes=["a2a:read"],
            ),
            AgentCapability(
                skill_id="plan.simulate",
                name="Simulación de planes",
                description="Simula planes de viaje con Monte Carlo.",
                tags=["planning", "simulation"],
                scopes=["a2a:write"],
            ),
            AgentCapability(
                skill_id="plan.critique",
                name="Evaluación crítica",
                description="Evalúa planes simulados y emite veredicto.",
                tags=["planning", "critique"],
                scopes=["a2a:write"],
            ),
        ],
        security_schemes=[
            AgentSecurityScheme(
                scheme=SecuritySchemeType.bearer,
                description="OAuth2 / OpenID Connect Bearer token",
                scopes={
                    "a2a:read": "Read tasks and artifacts",
                    "a2a:write": "Create and update tasks",
                    "a2a:admin": "Administrative operations",
                },
            ),
            AgentSecurityScheme(
                scheme=SecuritySchemeType.api_key,
                description="API key en header X-API-Key",
                in_header="X-API-Key",
            ),
        ],
    )


@app.route("/.well-known/agent.json", methods=["GET"])
def agent_card() -> tuple:
    return _ok(get_agent_card().model_dump())


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc268-a2a-secure-agent", "status": "ready"})


@app.route("/a2a", methods=["POST"])
@require_auth(scopes=["a2a:read", "a2a:write"])
def a2a_jsonrpc() -> tuple:
    """Endpoint JSON-RPC 2.0 para A2A tasks."""
    payload = request.get_json(silent=True) or {}
    try:
        rpc = JSONRPCRequest.model_validate(payload)
    except Exception as exc:
        return _jsonrpc_error(-32700, f"Parse error: {exc}", payload.get("id"))

    try:
        if rpc.method == "tasks/send":
            return _handle_tasks_send(rpc)
        if rpc.method == "tasks/get":
            return _handle_tasks_get(rpc)
        if rpc.method == "tasks/cancel":
            return _handle_tasks_cancel(rpc)
        return _jsonrpc_error(-32601, f"Method not found: {rpc.method}", rpc.id, 404)
    except Exception as exc:
        return _jsonrpc_error(-32603, f"Internal error: {exc}", rpc.id, 500)


def _handle_tasks_send(rpc: JSONRPCRequest) -> tuple:
    params = rpc.params or {}
    task_data = params.get("task") or {}
    task = Task.model_validate(task_data)
    task.update_status(TaskStatus.working, "Task accepted by A2A server")

    # Ejecutar flujo interno si el mensaje del usuario contiene una búsqueda de vuelos
    user_messages = [m for m in task.messages if m.role == "user"]
    if user_messages:
        # Intenta extraer payload JSON de la primera parte
        for part in user_messages[0].parts:
            if part.type == "json" and isinstance(part.content, dict):
                try:
                    search_req = FlightSearchRequest.model_validate(part.content)
                    _run_internal_flow(search_req, task)
                except Exception:
                    pass

    if task.status != TaskStatus.completed:
        task.update_status(TaskStatus.completed, "A2A task completed")
    return _jsonrpc_result({"task": task.model_dump(mode="json")}, rpc.id)


def _run_internal_flow(search_req: FlightSearchRequest, task: Task) -> None:
    user = UserProxyAgent(_bus)
    user.request_plan(search_req)
    # Recopilar resultados que llegaron al user proxy
    artifacts: List[Dict[str, Any]] = []
    for envelope in user.responses:
        artifacts.append(
            {
                "name": envelope.message_type,
                "parts": [
                    {
                        "type": "json",
                        "content": _model_or_dict(envelope.payload),
                    }
                ],
            }
        )
    task.artifacts.extend(
        [
            {
                "name": a.get("name", "result"),
                "parts": a.get("parts", []),
            }
            for a in artifacts
        ]
    )
    task.final_output = {"artifacts_count": len(artifacts)}
    task.update_status(TaskStatus.completed, "Internal planning flow finished")


def _model_or_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _handle_tasks_get(rpc: JSONRPCRequest) -> tuple:
    params = rpc.params or {}
    task_id = params.get("task_id", "")
    # Simulación: devolver una tarea con el mismo id y estado working/completed
    task = Task(
        task_id=task_id,
        status=TaskStatus.completed,
        final_output={"detail": "Task status retrieved"},
    )
    return _jsonrpc_result({"task": task.model_dump(mode="json")}, rpc.id)


def _handle_tasks_cancel(rpc: JSONRPCRequest) -> tuple:
    params = rpc.params or {}
    task_id = params.get("task_id", "")
    task = Task(task_id=task_id, status=TaskStatus.cancelled)
    return _jsonrpc_result({"task": task.model_dump(mode="json")}, rpc.id)


def _jsonrpc_result(result: Dict[str, Any], req_id: Any) -> tuple:
    resp = JSONRPCResponse(result=result, id=req_id)
    return _ok(resp.model_dump())


def _jsonrpc_error(code: int, message: str, req_id: Any, http_status: int = 400) -> tuple:
    resp = JSONRPCResponse(
        error={"code": code, "message": message},
        id=req_id,
    )
    return jsonify(resp.model_dump()), http_status


@app.route("/api/v1/security/token", methods=["POST"])
def issue_token() -> tuple:
    """Emite un JWT de prueba con los scopes solicitados."""
    data = request.get_json(silent=True) or {}
    identity = data.get("identity", "test-user")
    scopes = data.get("scopes", ["a2a:read", "a2a:write"])
    ttl = data.get("ttl_minutes")
    try:
        token = SecurityManager(_app_config.security).generate_token(
            identity, scopes, ttl_minutes=ttl
        )
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok({"token": token, "identity": identity, "scopes": scopes})


@app.route("/api/v1/agents", methods=["GET"])
@require_auth(scopes=["a2a:read"])
def list_agents() -> tuple:
    agents = [
        {"role": role.value, "metrics": agent.metrics}
        for role, agent in _bus.agents.items()
    ]
    return _ok(agents)


@app.route("/api/v1/communication/send", methods=["POST"])
@require_auth(scopes=["a2a:write"])
def send_internal_message() -> tuple:
    """Envía un mensaje por el bus interno (para tests e integración)."""
    data = request.get_json(silent=True) or {}
    try:
        envelope = _deserialize_envelope(data)
    except Exception as exc:
        return _err(f"Invalid envelope: {exc}", 400)
    try:
        _bus.publish(envelope)
    except Exception as exc:
        return _err(f"Publish failed: {exc}", 500)
    return _ok({"published": True, "message_id": str(envelope.message_id)})


def _deserialize_envelope(data: Dict[str, Any]):
    from models import MessageEnvelope
    return MessageEnvelope.model_validate(data)


@app.route("/api/v1/communication/history", methods=["GET"])
@require_auth(scopes=["a2a:read"])
def message_history() -> tuple:
    limit = request.args.get("limit", 100, type=int)
    items = [env.model_dump(mode="json") for env in list(_bus.history)[-limit:]]
    return _ok(items)


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /a2a",
        "description": "JSON-RPC 2.0 A2A para enviar, consultar y cancelar tareas.",
        "parameters": [
            {"name": "jsonrpc", "type": "string", "required": True, "example": "2.0"},
            {"name": "method", "type": "string", "required": True, "enum": ["tasks/send", "tasks/get", "tasks/cancel"]},
            {"name": "params", "type": "object", "required": True},
            {"name": "id", "type": "string | int", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/security/token",
        "description": "Emite un JWT de prueba para autenticación Bearer.",
        "parameters": [
            {"name": "identity", "type": "string", "required": False, "default": "test-user"},
            {"name": "scopes", "type": "list[string]", "required": False, "default": ["a2a:read", "a2a:write"]},
            {"name": "ttl_minutes", "type": "integer", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/communication/send",
        "description": "Envía un MessageEnvelope por el bus interno.",
        "parameters": [
            {"name": "source_agent", "type": "string", "required": True},
            {"name": "target_agent", "type": "string", "required": True},
            {"name": "message_type", "type": "string", "required": True},
            {"name": "payload", "type": "object", "required": True},
            {"name": "correlation_id", "type": "string", "required": False},
            {"name": "causation_id", "type": "string", "required": False},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "GET /.well-known/agent.json",
        "description": "Agent Card con capacidades y esquemas de seguridad soportados.",
        "fields": [
            {"name": "name", "type": "string"},
            {"name": "url", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "capabilities", "type": "list[object]"},
            {"name": "security_schemes", "type": "list[object]"},
        ],
    },
    {
        "endpoint": "POST /a2a",
        "description": "Respuesta JSON-RPC 2.0 con la tarea procesada.",
        "fields": [
            {"name": "jsonrpc", "type": "string"},
            {"name": "result.task", "type": "object"},
            {"name": "error", "type": "object"},
            {"name": "id", "type": "string | int"},
        ],
    },
    {
        "endpoint": "POST /api/v1/security/token",
        "description": "Token JWT y metadatos.",
        "fields": [
            {"name": "token", "type": "string"},
            {"name": "identity", "type": "string"},
            {"name": "scopes", "type": "list[string]"},
        ],
    },
    {
        "endpoint": "GET /api/v1/agents",
        "description": "Lista de agentes registrados en el bus.",
        "fields": [
            {"name": "role", "type": "string"},
            {"name": "metrics", "type": "object"},
        ],
    },
]


@app.errorhandler(404)
def not_found(_e: Any) -> tuple:
    return _err("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_e: Any) -> tuple:
    return _err("Method not allowed", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC268_PORT", _app_config.port))
    app.run(host="0.0.0.0", port=port, debug=_app_config.debug)
