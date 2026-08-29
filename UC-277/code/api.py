"""API Flask para UC-277 — Memoria Multi-Turno a Largo Plazo.

18 endpoints organizados por capa de memoria.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from config import get_config
from memory_system import MultiLayerMemorySystem
from models import GoalStatus, MemoryImportance, MemoryType

app = Flask(__name__)
_config = get_config()

_agents: Dict[str, MultiLayerMemorySystem] = {}


def _get_or_create(agent_id: str) -> MultiLayerMemorySystem:
    if agent_id not in _agents:
        _agents[agent_id] = MultiLayerMemorySystem(agent_id, db_path=_config.db_path)
    return _agents[agent_id]


def _ok(data: Any, status: int = 200):
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}), status


def _err(msg: str, status: int = 400):
    return jsonify({"status": "error", "message": msg}), status


# ============================================================
# Health & Schema
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc277-multi-turn-memory", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


# ============================================================
# Agent Management
# ============================================================

@app.route("/api/v1/agent/create", methods=["POST"])
def create_agent():
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    if not agent_id:
        return _err("agent_id is required")
    _get_or_create(agent_id)
    return _ok({"agent_id": agent_id, "status": "created"})


@app.route("/api/v1/agent/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    if agent_id not in _agents:
        return _err(f"Agent {agent_id} not found", 404)
    return _ok(_agents[agent_id].get_system_stats())


@app.route("/api/v1/agents", methods=["GET"])
def list_agents():
    return _ok([{"agent_id": aid, **ms.get_system_stats()} for aid, ms in _agents.items()])


# ============================================================
# Memory Operations
# ============================================================

@app.route("/api/v1/memory/store", methods=["POST"])
def memory_store():
    """Almacena interaccion en sistema multi-capa."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    summary = data.get("summary")
    if not agent_id or not summary:
        return _err("agent_id and summary are required")

    ms = _get_or_create(agent_id)
    episode_id = ms.store_interaction(
        summary=summary,
        session_id=data.get("session_id", ""),
        episode_type=data.get("episode_type", "interaction"),
        details=data.get("details"),
        tags=data.get("tags"),
        importance=MemoryImportance(data.get("importance", "medium")),
        sentiment=data.get("sentiment", 0.0),
        extract_facts=data.get("extract_facts", True),
    )
    return _ok({"episode_id": episode_id, "agent_id": agent_id})


@app.route("/api/v1/memory/recall", methods=["POST"])
def memory_recall():
    """Recall multi-capa: busca en todas las capas relevantes."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    query = data.get("query")
    if not agent_id or not query:
        return _err("agent_id and query are required")

    ms = _get_or_create(agent_id)
    layers = None
    if data.get("layers"):
        layers = [MemoryType(l) for l in data["layers"]]
    result = ms.recall(query, top_k=data.get("top_k", 5), layers=layers)
    return _ok(result)


@app.route("/api/v1/memory/consolidate", methods=["POST"])
def memory_consolidate():
    """Consolida memorias: episodica -> semantica."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    if not agent_id:
        return _err("agent_id is required")
    ms = _get_or_create(agent_id)
    result = ms.consolidate()
    return _ok(result)


# ============================================================
# Session Management
# ============================================================

@app.route("/api/v1/session/new", methods=["POST"])
def new_session():
    """Inicia nueva sesion."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    if not agent_id:
        return _err("agent_id is required")
    ms = _get_or_create(agent_id)
    session_id = ms.new_session()
    return _ok({"agent_id": agent_id, "session_id": session_id})


@app.route("/api/v1/session/<session_id>/episodes", methods=["GET"])
def session_episodes(session_id: str):
    """Episodios de una sesion."""
    # Busca en todos los agentes
    for ms in _agents.values():
        episodes = ms.episodic.recall_by_session(session_id)
        if episodes:
            return _ok([{
                "episode_id": ep.episode_id, "summary": ep.summary,
                "episode_type": ep.episode_type, "timestamp": ep.timestamp,
            } for ep in episodes])
    return _ok([])


# ============================================================
# Episodic Memory
# ============================================================

@app.route("/api/v1/episodic/search", methods=["POST"])
def episodic_search():
    """Busqueda semantica en memoria episodica."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    query = data.get("query")
    if not agent_id or not query:
        return _err("agent_id and query are required")
    ms = _get_or_create(agent_id)
    episodes = ms.episodic.recall_semantic(query, agent_id, top_k=data.get("top_k", 5))
    return _ok([{
        "episode_id": ep.episode_id, "summary": ep.summary,
        "episode_type": ep.episode_type, "importance": ep.importance.value,
        "sentiment": ep.outcome_sentiment, "tags": ep.tags,
    } for ep in episodes])


@app.route("/api/v1/episodic/by-tag/<tag>", methods=["GET"])
def episodic_by_tag(tag: str):
    agent_id = request.args.get("agent_id")
    if not agent_id:
        return _err("agent_id query param required")
    ms = _get_or_create(agent_id)
    episodes = ms.episodic.recall_by_tag(agent_id, tag)
    return _ok([{"episode_id": ep.episode_id, "summary": ep.summary} for ep in episodes])


# ============================================================
# Semantic Memory
# ============================================================

@app.route("/api/v1/semantic/add-fact", methods=["POST"])
def semantic_add_fact():
    """Agrega hecho a memoria semantica."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    content = data.get("content")
    if not agent_id or not content:
        return _err("agent_id and content are required")
    ms = _get_or_create(agent_id)
    node_id = ms.semantic.add_fact(agent_id, content,
                                   data.get("node_type", "fact"),
                                   confidence=data.get("confidence", 0.8))
    return _ok({"node_id": node_id})


@app.route("/api/v1/semantic/query", methods=["POST"])
def semantic_query():
    """Consulta memoria semantica."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    query = data.get("query")
    if not agent_id or not query:
        return _err("agent_id and query are required")
    ms = _get_or_create(agent_id)
    results = ms.semantic.query(agent_id, query, top_k=data.get("top_k", 5))
    return _ok(results)


@app.route("/api/v1/semantic/preferences/<agent_id>", methods=["GET"])
def semantic_preferences(agent_id: str):
    ms = _get_or_create(agent_id)
    return _ok(ms.semantic.get_preferences(agent_id))


# ============================================================
# Goals
# ============================================================

@app.route("/api/v1/goals/create", methods=["POST"])
def create_goal():
    """Crea meta a largo plazo."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    title = data.get("title")
    if not agent_id or not title:
        return _err("agent_id and title are required")
    ms = _get_or_create(agent_id)
    goal_id = ms.goals.create_goal(
        agent_id, title, data.get("description", ""),
        priority=data.get("priority", 0.5),
        deadline=data.get("deadline"),
        sub_goals=data.get("sub_goals"),
    )
    return _ok({"goal_id": goal_id})


@app.route("/api/v1/goals/<agent_id>", methods=["GET"])
def list_goals(agent_id: str):
    ms = _get_or_create(agent_id)
    goals = ms.goals.get_all_goals(agent_id)
    return _ok([{
        "goal_id": g.goal_id, "title": g.title, "status": g.status.value,
        "progress": g.progress, "priority": g.priority,
    } for g in goals])


@app.route("/api/v1/goals/update-progress", methods=["POST"])
def update_goal_progress():
    data = request.get_json(silent=True) or {}
    goal_id = data.get("goal_id")
    progress = data.get("progress")
    if not goal_id or progress is None:
        return _err("goal_id and progress are required")
    # Find agent
    for ms in _agents.values():
        if goal_id in ms.goals.goals:
            ms.goals.update_progress(goal_id, progress, data.get("milestone"))
            return _ok({"goal_id": goal_id, "progress": progress})
    return _err("Goal not found", 404)


# ============================================================
# System
# ============================================================

@app.route("/api/v1/system/status", methods=["GET"])
def system_status():
    total_episodes = sum(len(ms.episodic.episodes) for ms in _agents.values())
    total_facts = sum(len(ms.semantic.nodes) for ms in _agents.values())
    total_skills = sum(len(ms.procedural.skills) for ms in _agents.values())
    total_goals = sum(len(ms.goals.goals) for ms in _agents.values())
    return _ok({
        "service": "uc277-multi-turn-memory",
        "total_agents": len(_agents),
        "total_episodes": total_episodes,
        "total_semantic_nodes": total_facts,
        "total_skills": total_skills,
        "total_goals": total_goals,
    })


# ============================================================
# Card Views
# ============================================================

INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/memory/store",
        "description": "Almacena interaccion en sistema multi-capa (episodic + working + semantic).",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True, "example": "trading_agent"},
            {"name": "summary", "type": "string", "required": True, "example": "Usuario solicito analisis de BTC"},
            {"name": "session_id", "type": "string", "required": False},
            {"name": "episode_type", "type": "string", "required": False, "default": "interaction"},
            {"name": "details", "type": "dict", "required": False},
            {"name": "tags", "type": "list[str]", "required": False, "example": ["btc", "analysis"]},
            {"name": "importance", "type": "string", "required": False, "enum": ["trivial", "low", "medium", "high", "critical"]},
            {"name": "sentiment", "type": "float", "required": False, "range": "-1.0 to 1.0"},
            {"name": "extract_facts", "type": "bool", "required": False, "default": True},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/recall",
        "description": "Recall multi-capa: busca en working + episodic + semantic + procedural + goals.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "query", "type": "string", "required": True, "example": "preferencias del usuario sobre riesgo"},
            {"name": "top_k", "type": "int", "required": False, "default": 5},
            {"name": "layers", "type": "list[str]", "required": False, "enum": ["working", "episodic", "semantic", "procedural", "goal"]},
        ],
    },
    {
        "endpoint": "POST /api/v1/semantic/add-fact",
        "description": "Agrega hecho permanente a memoria semantica (grafo de conocimiento).",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "content", "type": "string", "required": True, "example": "El usuario prefiere operaciones conservadoras"},
            {"name": "node_type", "type": "string", "required": False, "default": "fact"},
            {"name": "confidence", "type": "float", "required": False, "default": 0.8},
        ],
    },
    {
        "endpoint": "POST /api/v1/goals/create",
        "description": "Crea meta a largo plazo con tracking de progreso.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "title", "type": "string", "required": True, "example": "Alcanzar 10% ROI mensual"},
            {"name": "description", "type": "string", "required": False},
            {"name": "priority", "type": "float", "required": False, "default": 0.5},
            {"name": "deadline", "type": "float", "required": False, "description": "Unix timestamp"},
            {"name": "sub_goals", "type": "list[str]", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/episodic/search",
        "description": "Busqueda semantica en memoria episodica con boost por importancia y recencia.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
            {"name": "query", "type": "string", "required": True},
            {"name": "top_k", "type": "int", "required": False, "default": 5},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/consolidate",
        "description": "Consolida memorias episodicas importantes a memoria semantica permanente.",
        "parameters": [
            {"name": "agent_id", "type": "string", "required": True},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/memory/store",
        "description": "Resultado del almacenamiento multi-capa.",
        "fields": [
            {"name": "episode_id", "type": "string"},
            {"name": "agent_id", "type": "string"},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/recall",
        "description": "Resultado multi-capa del recall.",
        "fields": [
            {"name": "query", "type": "string"},
            {"name": "working", "type": "dict", "description": "Contexto activo de sesion"},
            {"name": "episodic", "type": "list", "description": "Episodios relevantes (semantic search)"},
            {"name": "semantic", "type": "list", "description": "Hechos y preferencias relevantes"},
            {"name": "procedural", "type": "list", "description": "Habilidades aplicables"},
            {"name": "goals", "type": "list", "description": "Metas activas"},
        ],
    },
    {
        "endpoint": "POST /api/v1/goals/create",
        "description": "Meta creada.",
        "fields": [
            {"name": "goal_id", "type": "string"},
        ],
    },
    {
        "endpoint": "GET /api/v1/system/status",
        "description": "Estado del sistema de memoria.",
        "fields": [
            {"name": "total_agents", "type": "int"},
            {"name": "total_episodes", "type": "int"},
            {"name": "total_semantic_nodes", "type": "int"},
            {"name": "total_skills", "type": "int"},
            {"name": "total_goals", "type": "int"},
        ],
    },
    {
        "endpoint": "POST /api/v1/memory/consolidate",
        "description": "Resultado de consolidacion.",
        "fields": [
            {"name": "episodes_processed", "type": "int"},
            {"name": "consolidated_to_semantic", "type": "int"},
        ],
    },
]

if __name__ == "__main__":
    port = int(os.getenv("UC277_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=_config.debug)
