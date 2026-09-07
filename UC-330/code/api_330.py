"""
UC-330 — API REST Flask para Exploitation–Exploration Governance.

Expone el controlador de balance exploración-explotación como servicio REST.
Puerto por defecto: 5330
"""

from flask import Flask, request, jsonify
from typing import Dict, Any, List

from balance_ex_models import BalanceExConfig, ContextSnapshot, DecisionMode
from balance_ex_engine import BalanceExEngine

app = Flask(__name__)

# Engine global (can be reset via endpoint)
_engine: BalanceExEngine = BalanceExEngine(
    actions=["action_1", "action_2", "action_3"],
    feature_keys=["feature_1", "feature_2", "feature_3"],
)

INPUT_CARDS = {
    "POST /api/v1/balance-ex/decide": {
        "description": "Decide el modo y acción para un contexto dado.",
        "parameters": {
            "context": {"type": "object", "required": True, "description": "Mapa de características (features)."},
            "domain": {"type": "string", "required": False, "default": "default", "description": "Dominio temático."},
            "environment": {"type": "string", "required": False, "default": "sandbox", "description": "production | sandbox."},
            "authorized_actions": {"type": "array", "required": False, "description": "Acciones permitidas en producción."},
            "risk_score": {"type": "float", "required": False, "default": 0.0, "description": "Score de riesgo entre 0 y 1."},
            "steps_remaining": {"type": "integer", "required": False, "description": "Pasos restantes para presupuesto."},
        },
    },
    "POST /api/v1/balance-ex/update": {
        "description": "Actualiza modelos con el resultado de una acción.",
        "parameters": {
            "decision": {"type": "object", "required": True, "description": "Decisión previa (dict con action, mode, etc.)."},
            "context": {"type": "object", "required": True, "description": "Contexto actual."},
            "reward": {"type": "float", "required": True, "description": "Recompensa observada."},
            "next_context": {"type": "object", "required": False, "description": "Contexto siguiente."},
            "cost": {"type": "float", "required": False, "default": 0.0, "description": "Costo de exploración."},
            "duration_ms": {"type": "float", "required": False, "default": 0.0},
        },
    },
    "POST /api/v1/balance-ex/episode": {
        "description": "Ejecuta un episodio completo de decisiones y actualizaciones.",
        "parameters": {
            "contexts": {"type": "array", "required": True, "description": "Lista de contextos."},
            "rewards": {"type": "array", "required": True, "description": "Lista de recompensas."},
            "environment": {"type": "string", "required": False, "default": "sandbox"},
            "authorized_actions": {"type": "array", "required": False},
        },
    },
    "GET /api/v1/balance-ex/stats": {
        "description": "Estadísticas del motor.",
        "parameters": {},
    },
    "GET /api/v1/balance-ex/recommend": {
        "description": "Recomendaciones basadas en métricas actuales.",
        "parameters": {},
    },
    "POST /api/v1/balance-ex/reset": {
        "description": "Reinicia el motor con nueva configuración.",
        "parameters": {
            "actions": {"type": "array", "required": True},
            "feature_keys": {"type": "array", "required": True},
            "config": {"type": "object", "required": False},
        },
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/balance-ex/decide": {
        "description": "Decisión de modo y acción.",
        "fields": {
            "decision_id": "string",
            "mode": "exploit | sandbox | escalate",
            "strategy": "random | ucb | directed | curiosity",
            "action": "string",
            "epsilon": "float",
            "uncertainty": "float",
            "risk_score": "float",
            "justification": "string",
            "metadata": "object",
        },
    },
    "POST /api/v1/balance-ex/update": {
        "description": "Registro de la acción actualizada.",
        "fields": {
            "action_id": "string",
            "action": "string",
            "mode": "string",
            "strategy": "string",
            "reward": "float",
            "risk": "float",
            "cost": "float",
        },
    },
    "POST /api/v1/balance-ex/episode": {
        "description": "Resultado del episodio.",
        "fields": {
            "trace_id": "string",
            "metrics": "object",
            "history": "array",
            "recommendations": "array",
            "duration_ms": "float",
        },
    },
    "GET /api/v1/balance-ex/stats": {
        "description": "Estadísticas completas del motor.",
        "fields": {
            "actions": "array",
            "feature_keys": "array",
            "config": "object",
            "metrics": "object",
            "total_records": "int",
        },
    },
    "GET /api/v1/balance-ex/recommend": {
        "description": "Lista de recomendaciones.",
        "fields": {
            "recommendations": "array",
        },
    },
    "POST /api/v1/balance-ex/reset": {
        "description": "Confirmación de reinicio.",
        "fields": {
            "status": "string",
            "actions": "array",
            "feature_keys": "array",
        },
    },
}


def _build_context(data: Dict[str, Any]) -> ContextSnapshot:
    return ContextSnapshot(
        features=data.get("context", {}),
        domain=data.get("domain", "default"),
        metadata=data.get("metadata", {}),
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-330 Balance-EX"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-330 — Exploitation–Exploration Governance",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/balance-ex/decide"},
            {"method": "POST", "path": "/api/v1/balance-ex/update"},
            {"method": "POST", "path": "/api/v1/balance-ex/episode"},
            {"method": "GET", "path": "/api/v1/balance-ex/stats"},
            {"method": "GET", "path": "/api/v1/balance-ex/recommend"},
            {"method": "POST", "path": "/api/v1/balance-ex/reset"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/balance-ex/decide", methods=["POST"])
def decide():
    data = request.get_json(force=True)
    context = _build_context(data)
    decision = _engine.decide(
        context=context,
        environment=data.get("environment", "sandbox"),
        authorized_actions=data.get("authorized_actions"),
        risk_score=float(data.get("risk_score", 0.0)),
        steps_remaining=data.get("steps_remaining"),
    )
    return jsonify(decision.to_dict())


@app.route("/api/v1/balance-ex/update", methods=["POST"])
def update():
    data = request.get_json(force=True)
    decision_data = data.get("decision")
    if not decision_data:
        return jsonify({"error": "decision is required"}), 400

    decision = DecisionMode(decision_data.get("mode", "exploit"))
    from balance_ex_models import Decision, ExplorationStrategy
    dec = Decision(
        decision_id=decision_data.get("decision_id", ""),
        mode=DecisionMode(decision_data.get("mode", "exploit")),
        strategy=ExplorationStrategy(decision_data.get("strategy", "random")),
        action=decision_data.get("action", ""),
        epsilon=float(decision_data.get("epsilon", 0.0)),
        uncertainty=float(decision_data.get("uncertainty", 0.0)),
        risk_score=float(decision_data.get("risk_score", 0.0)),
        justification=decision_data.get("justification", ""),
        metadata=decision_data.get("metadata", {}),
    )
    context = _build_context(data)
    next_ctx = None
    if data.get("next_context"):
        next_ctx = _build_context({"context": data["next_context"], "domain": data.get("domain", "default")})

    record = _engine.update(
        decision=dec,
        context=context,
        reward=float(data.get("reward", 0.0)),
        next_context=next_ctx,
        cost=float(data.get("cost", 0.0)),
        duration_ms=float(data.get("duration_ms", 0.0)),
    )
    return jsonify(record.to_dict())


@app.route("/api/v1/balance-ex/episode", methods=["POST"])
def episode():
    data = request.get_json(force=True)
    contexts = [_build_context({"context": c}) for c in data.get("contexts", [])]
    rewards = data.get("rewards", [])
    if len(contexts) != len(rewards):
        return jsonify({"error": "contexts and rewards must have same length"}), 400
    result = _engine.run_episode(
        contexts=contexts,
        rewards=rewards,
        environment=data.get("environment", "sandbox"),
        authorized_actions=data.get("authorized_actions"),
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/balance-ex/stats", methods=["GET"])
def stats():
    return jsonify(_engine.get_statistics())


@app.route("/api/v1/balance-ex/recommend", methods=["GET"])
def recommend():
    return jsonify({"recommendations": _engine.recommend()})


@app.route("/api/v1/balance-ex/reset", methods=["POST"])
def reset():
    global _engine
    data = request.get_json(force=True)
    actions = data.get("actions")
    feature_keys = data.get("feature_keys")
    if not actions or not feature_keys:
        return jsonify({"error": "actions and feature_keys are required"}), 400
    config = None
    if data.get("config"):
        config = BalanceExConfig(**data["config"])
    _engine = BalanceExEngine(actions=actions, feature_keys=feature_keys, config=config)
    return jsonify({
        "status": "reset",
        "actions": actions,
        "feature_keys": feature_keys,
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    # UC-330 engine does not keep an observability manager by default; expose empty
    return "", 200, {"Content-Type": "text/plain"}


def run_server(port: int = 5330) -> None:
    print(f"UC-330 Balance-EX API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
