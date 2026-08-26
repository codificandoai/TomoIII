"""API REST Flask para UC-263 - Q-Learning vectorial turístico."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request as flask_request

from config import get_config
from graph import recommend, train
from models import TravelerContext

app = Flask(__name__)

_config = get_config()


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


INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/rl/recommend",
        "description": (
            "Obtiene una recomendación turística para un contexto de viajero usando "
            "Q-Learning vectorial con similitud del coseno."
        ),
        "parameters": [
            {"name": "user_id", "type": "string", "required": False, "default": "anonymous"},
            {"name": "age_group", "type": "string", "required": False, "default": "adult"},
            {"name": "group_type", "type": "string", "required": False, "default": "solo", "description": "solo, couple, family, friends"},
            {"name": "season", "type": "string", "required": False, "default": "summer"},
            {"name": "budget_level", "type": "string", "required": False, "default": "medium", "description": "low, medium, high"},
            {"name": "interests", "type": "list[string]", "required": False, "example": ["culture", "food"]},
            {"name": "origin", "type": "string", "required": False},
            {"name": "destination", "type": "string", "required": False},
            {"name": "mood", "type": "string", "required": False, "example": "relaxed"},
        ],
    },
    {
        "endpoint": "POST /api/v1/rl/feedback",
        "description": (
            "Registra una recompensa real del usuario para actualizar el Q-Learning "
            "vectorial."
        ),
        "parameters": [
            {"name": "user_id", "type": "string", "required": False, "default": "anonymous"},
            {"name": "context", "type": "object", "required": True, "description": "Mismo formato que /recommend"},
            {"name": "action", "type": "string", "required": True},
            {"name": "reward", "type": "number", "required": True, "description": "Valor en [-1, 1]"},
            {"name": "next_context", "type": "object", "required": False},
        ],
    },
    {
        "endpoint": "POST /api/v1/rl/train",
        "description": "Entrena el agente RL con un conjunto de contextos de ejemplo durante N episodios.",
        "parameters": [
            {"name": "contexts", "type": "list[object]", "required": True},
            {"name": "episodes", "type": "integer", "required": False, "default": 50},
        ],
    },
    {
        "endpoint": "GET /api/v1/rl/memory",
        "description": "Devuelve estadísticas de la memoria vectorial de experiencias.",
        "parameters": [],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/rl/recommend",
        "description": "Recomendación generada por el agente RL con Q-values y alternativas.",
        "fields": [
            {"name": "context", "type": "object"},
            {"name": "state_description", "type": "string"},
            {"name": "last_action", "type": "string"},
            {"name": "last_reward", "type": "number"},
            {"name": "last_q_value", "type": "number"},
            {"name": "final_q_values", "type": "object"},
            {"name": "recommendations", "type": "list[object]"},
            {"name": "learner_stats", "type": "object"},
            {"name": "status", "type": "string"},
        ],
    },
    {
        "endpoint": "POST /api/v1/rl/feedback y POST /api/v1/rl/train",
        "description": "Resultado de entrenamiento o actualización de la memoria RL.",
        "fields": [
            {"name": "stats", "type": "object"},
            {"name": "learner_stats", "type": "object"},
            {"name": "status", "type": "string"},
        ],
    },
]


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return _ok({"service": "uc263-rl-vector-agent", "status": "ready"})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> tuple:
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/rl/recommend", methods=["POST"])
def recommend_endpoint() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    try:
        context = TravelerContext.from_dict(payload)
    except Exception as exc:
        return _err(f"Invalid context: {exc}", 400)
    try:
        result = recommend(context, _config)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(result)


@app.route("/api/v1/rl/feedback", methods=["POST"])
def feedback_endpoint() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    context_data = payload.get("context")
    action = payload.get("action")
    reward = payload.get("reward")
    next_context_data = payload.get("next_context")
    if not context_data or not action or reward is None:
        return _err("context, action and reward are required", 400)
    try:
        context = TravelerContext.from_dict(context_data)
        next_state = (
            TravelerContext.from_dict(next_context_data).describe()
            if next_context_data
            else f"post-{context.describe()}"
        )
        from vector_q_learner import VectorQLearner
        learner = VectorQLearner(_config.rl, _config.memory.path)
        actions = _config.agent.actions
        learner.update(
            context.describe(),
            action,
            float(reward),
            next_state,
            actions,
        )
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok({"updated": True, "learner_stats": learner.stats()})


@app.route("/api/v1/rl/train", methods=["POST"])
def train_endpoint() -> tuple:
    payload = flask_request.get_json(silent=True) or {}
    contexts = payload.get("contexts")
    if not contexts or not isinstance(contexts, list):
        return _err("contexts (list) is required", 400)
    episodes = int(payload.get("episodes", _config.rl.episodes))
    try:
        result = train(contexts, episodes=episodes, config=_config)
    except Exception as exc:
        return _err(str(exc), 500)
    return _ok(result)


@app.route("/api/v1/rl/memory", methods=["GET"])
def memory_endpoint() -> tuple:
    from vector_q_learner import VectorQLearner

    learner = VectorQLearner(_config.rl, _config.memory.path)
    return _ok(learner.stats())


@app.errorhandler(404)
def not_found(_e: Any) -> tuple:
    return _err("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_e: Any) -> tuple:
    return _err("Method not allowed", 405)


if __name__ == "__main__":
    port = int(os.getenv("UC263_PORT", _config.port))
    app.run(host="0.0.0.0", port=port, debug=False)
