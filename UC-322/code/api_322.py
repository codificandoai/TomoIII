"""API REST Flask para UC-322 — Resolución de Conflictos Multiagente.

Expone endpoints para:
- Resolver conflictos entre agentes.
- Consultar y gestionar reputación dinámica.
- Detectar trabajo duplicado y deadlocks.
- Consultar historial de resoluciones.
- Exportar métricas Prometheus.
- Consultar logs y trazas.

Cards de entrada/salida documentadas en /api/v1/schema.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request

from uc322 import ConflictResolutionLayer
from conflict_models import AgentBelief

app = Flask(__name__)
layer = ConflictResolutionLayer()

# ─── Cards de entrada/salida ──────────────────────────────────────────────

INPUT_CARDS: Dict[str, Any] = {
    "POST /api/v1/conflicts/resolve": {
        "description": "Resuelve un conflicto entre agentes usando los 4 niveles.",
        "parameters": [
            {"name": "beliefs", "type": "list[object]", "required": True,
             "description": "Lista de creencias de agentes",
             "example": [
                 {"agent_id": "technical", "proposition": "BUY AAPL", "confidence": 0.85},
                 {"agent_id": "sentiment", "proposition": "BUY AAPL", "confidence": 0.40}
             ]},
            {"name": "domain", "type": "string", "required": False, "default": "trading"},
            {"name": "options", "type": "list[string]", "required": False,
             "description": "Opciones votables para Nivel 2",
             "example": ["BUY", "SELL", "HOLD"]},
            {"name": "task_id", "type": "string", "required": False,
             "description": "ID de la tarea en disputa para Nivel 3"},
            {"name": "agent_bids", "type": "list[object]", "required": False,
             "description": "Pujas de agentes para Nivel 3",
             "example": [
                 {"agent_id": "technical", "bid_score": 0.9, "confidence": 0.85,
                  "estimated_cost": 0.1, "estimated_latency_ms": 500}
             ]},
        ],
    },
    "POST /api/v1/reputation/record": {
        "description": "Registra un episodio y actualiza la reputación de un agente.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "task_id", "type": "string", "required": True},
            {"name": "success", "type": "boolean", "required": True},
            {"name": "quality", "type": "float", "required": False, "default": 0.5},
            {"name": "efficiency", "type": "float", "required": False, "default": 0.5},
            {"name": "domain", "type": "string", "required": False, "default": "trading"},
        ],
    },
    "GET /api/v1/reputation/ranking": {
        "description": "Retorna el ranking de agentes por reputación.",
        "parameters": [
            {"name": "domain", "type": "string", "required": False, "default": "trading"},
            {"name": "top_n", "type": "integer", "required": False, "default": 10},
        ],
    },
    "POST /api/v1/duplicate/check": {
        "description": "Verifica si una tarea es duplicado de una activa.",
        "parameters": [
            {"name": "task_id", "type": "string", "required": True},
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "domain", "type": "string", "required": True},
            {"name": "description", "type": "string", "required": True},
        ],
    },
    "POST /api/v1/deadlock/check": {
        "description": "Verifica si hay deadlocks en el grafo de espera.",
        "parameters": [
            {"name": "waiting_graph", "type": "object", "required": False,
             "description": "Grafo de espera agent_id -> waiting_for"},
        ],
    },
}

OUTPUT_CARDS: Dict[str, Any] = {
    "POST /api/v1/conflicts/resolve": {
        "description": "Resultado completo de la resolución del conflicto.",
        "fields": [
            {"name": "conflict", "type": "object", "description": "Conflicto detectado"},
            {"name": "level_reached", "type": "string",
             "description": "Nivel de resolución alcanzado: NEGOTIATION, VOTING, CNP_BIDDING, ESCALATION"},
            {"name": "negotiation_result", "type": "object|null", "description": "Resultado de negociación"},
            {"name": "voting_result", "type": "object|null", "description": "Resultado de votación"},
            {"name": "cnp_result", "type": "object|null", "description": "Resultado de CNP"},
            {"name": "escalation_result", "type": "object|null", "description": "Resultado de escalación"},
            {"name": "success", "type": "boolean", "description": "Si el conflicto fue resuelto"},
            {"name": "total_duration", "type": "float", "description": "Duración total en segundos"},
        ],
    },
    "POST /api/v1/reputation/record": {
        "description": "Nueva reputación del agente tras el episodio.",
        "fields": [
            {"name": "agent_id", "type": "string"},
            {"name": "new_reputation", "type": "float"},
            {"name": "total_episodes", "type": "integer"},
        ],
    },
    "GET /api/v1/reputation/ranking": {
        "description": "Ranking de agentes por reputación.",
        "fields": [
            {"name": "ranking", "type": "list[object]"},
            {"name": "domain", "type": "string"},
        ],
    },
    "POST /api/v1/duplicate/check": {
        "description": "Resultado de la verificación de duplicado.",
        "fields": [
            {"name": "registered", "type": "boolean"},
            {"name": "conflict", "type": "object|null"},
        ],
    },
    "POST /api/v1/deadlock/check": {
        "description": "Resultado de la verificación de deadlock.",
        "fields": [
            {"name": "deadlock_detected", "type": "boolean"},
            {"name": "deadlock", "type": "object|null"},
            {"name": "waiting_graph", "type": "object"},
        ],
    },
}


# ─── Endpoints ────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "uc-322-conflict-resolution"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({
        "input_cards": INPUT_CARDS,
        "output_cards": OUTPUT_CARDS,
    })


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-322 Conflict Resolution Layer",
        "version": "1.0",
        "endpoints": list(INPUT_CARDS.keys()),
        "schema_url": "/api/v1/schema",
    })


@app.route("/api/v1/conflicts/resolve", methods=["POST"])
def resolve_conflict():
    """Resuelve un conflicto entre agentes."""
    data = request.get_json(force=True)
    beliefs_data = data.get("beliefs", [])
    beliefs = [
        AgentBelief(
            agent_id=b["agent_id"],
            proposition=b.get("proposition", ""),
            confidence=b.get("confidence", 0.5),
            evidence=b.get("evidence", {}),
        )
        for b in beliefs_data
    ]
    domain = data.get("domain", "trading")
    options = data.get("options")
    task_id = data.get("task_id")
    agent_bids = data.get("agent_bids")

    result = layer.resolve(
        beliefs=beliefs,
        domain=domain,
        options=options,
        task_id=task_id,
        agent_bids=agent_bids,
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/reputation/record", methods=["POST"])
def record_reputation():
    """Registra un episodio y actualiza la reputación."""
    data = request.get_json(force=True)
    new_rep = layer.reputation.record_episode(
        agent_id=data["agent_id"],
        task_id=data["task_id"],
        success=data["success"],
        quality=data.get("quality", 0.5),
        efficiency=data.get("efficiency", 0.5),
        domain=data.get("domain", "trading"),
    )
    entry = layer.reputation.get_entry(data["agent_id"], data.get("domain", "trading"))
    return jsonify({
        "agent_id": data["agent_id"],
        "new_reputation": round(new_rep, 4),
        "total_episodes": entry.total_episodes,
    })


@app.route("/api/v1/reputation/ranking", methods=["GET"])
def reputation_ranking():
    """Retorna el ranking de agentes por reputación."""
    domain = request.args.get("domain", "trading")
    top_n = int(request.args.get("top_n", 10))
    ranking = layer.get_reputation_ranking(domain)
    return jsonify({"ranking": ranking[:top_n], "domain": domain})


@app.route("/api/v1/reputation/<agent_id>", methods=["GET"])
def get_reputation(agent_id: str):
    """Retorna la reputación de un agente específico."""
    domain = request.args.get("domain", "trading")
    entry = layer.reputation.get_entry(agent_id, domain)
    return jsonify(entry.to_dict())


@app.route("/api/v1/duplicate/check", methods=["POST"])
def check_duplicate():
    """Verifica si una tarea es duplicado."""
    data = request.get_json(force=True)
    result = layer.check_duplicate(
        task_id=data["task_id"],
        agent_id=data["agent_id"],
        domain=data["domain"],
        description=data["description"],
    )
    return jsonify(result)


@app.route("/api/v1/deadlock/check", methods=["POST"])
def check_deadlock():
    """Verifica si hay deadlocks."""
    data = request.get_json(force=True) or {}
    graph = data.get("waiting_graph", {})
    for agent_id, waiting_for in graph.items():
        layer.deadlock_detector.set_waiting(agent_id, waiting_for, agent_id)
    result = layer.check_deadlock()
    return jsonify(result)


@app.route("/api/v1/conflicts/history", methods=["GET"])
def conflict_history():
    """Retorna el historial de resoluciones."""
    limit = int(request.args.get("limit", 20))
    return jsonify({"history": layer.get_resolution_history(limit)})


@app.route("/api/v1/escalation/history", methods=["GET"])
def escalation_history():
    """Retorna el historial de escalaciones."""
    return jsonify({"history": layer.escalation.get_history()})


@app.route("/api/v1/escalation/circuit-breaker", methods=["GET"])
def circuit_breaker_status():
    """Retorna el estado del circuit breaker."""
    return jsonify({
        "open": layer.escalation.circuit_breaker_open,
        "consecutive_conflicts": layer.escalation.consecutive_conflicts,
    })


@app.route("/api/v1/escalation/circuit-breaker/reset", methods=["POST"])
def reset_circuit_breaker():
    """Resetea el circuit breaker."""
    layer.escalation.reset_circuit_breaker()
    return jsonify({"status": "reset", "open": False})


@app.route("/api/v1/observability/summary", methods=["GET"])
def observability_summary():
    """Retorna un resumen de métricas, logs y trazas."""
    return jsonify(layer.get_observability_summary())


@app.route("/api/v1/observability/logs", methods=["GET"])
def observability_logs():
    """Retorna logs estructurados."""
    level = request.args.get("level")
    trace_id = request.args.get("trace_id")
    limit = int(request.args.get("limit", 100))
    logs = layer.observability.get_logs(level=level, trace_id=trace_id, limit=limit)
    return jsonify({"logs": logs})


@app.route("/api/v1/observability/spans", methods=["GET"])
def observability_spans():
    """Retorna trazas (spans)."""
    trace_id = request.args.get("trace_id")
    spans = layer.observability.get_spans(trace_id=trace_id)
    return jsonify({"spans": spans})


@app.route("/metrics", methods=["GET"])
def metrics():
    """Endpoint de métricas Prometheus."""
    from flask import Response
    return Response(layer.observability.export_prometheus(), mimetype="text/plain")


@app.route("/api/v1/tasks/active", methods=["GET"])
def active_tasks():
    """Retorna las tareas activas registradas."""
    domain = request.args.get("domain")
    tasks = layer.duplicate_detection.get_active_tasks(domain)
    return jsonify({"tasks": tasks})


def run_server(port: int = 5322) -> None:
    """Inicia el servidor Flask."""
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
