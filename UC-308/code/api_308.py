"""
UC-308 — API REST Flask para Agent Drift / Environmental Degradation.

Puerto por defecto: 5308
Endpoints: health, schema, run-evaluation, baseline, datasets, history,
alerts, status, metrics, reset.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Flask, jsonify, request

from drift_orchestrator import DriftOrchestrator
from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import build_default_golden_dataset
from models_308 import DriftConfig

from cc_models_308 import ExperimentConfig, MarketEvent
from champion_challenger_experiment_308 import (
    ChampionChallengerExperiment,
    ChampionChallengerManager,
    generate_market_events,
)
from cc_predictors_308 import ChampionDemoPredictor, ChallengerDemoPredictor, UC315SkillPredictorAdapter

from cc_models_308 import ExperimentConfig, MarketEvent
from champion_challenger_experiment_308 import (
    ChampionChallengerExperiment,
    ChampionChallengerManager,
    generate_market_events,
)
from cc_predictors_308 import ChampionDemoPredictor, ChallengerDemoPredictor, UC315SkillPredictorAdapter

app = Flask(__name__)


def _create_orchestrator() -> DriftOrchestrator:
    """Factory con dataset y config por defecto."""
    dataset = build_default_golden_dataset(version="1.0.0")
    config = DriftConfig()
    environment = SimulatedExternalEnvironment(seed=int(os.environ.get("UC308_SEED", "42")))
    return DriftOrchestrator(
        config=config,
        dataset=dataset,
        environment=environment,
    )


_orchestrator: DriftOrchestrator = _create_orchestrator()


_cc_manager: ChampionChallengerManager = ChampionChallengerManager()


_cc_manager: ChampionChallengerManager = ChampionChallengerManager()


def _ensure_baselines() -> None:
    """Inicializa baselines si no existen."""
    if not _orchestrator.baseline_manager.baselines:
        _orchestrator.initialize_baselines(scenario="healthy")


# ---------------------------------------------------------------------------
# INPUT Cards
# ---------------------------------------------------------------------------
INPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "GET /health": {
        "endpoint": "GET /health",
        "description": "Health check del servicio UC-308.",
        "parameters": [],
    },
    "GET /api/v1/schema": {
        "endpoint": "GET /api/v1/schema",
        "description": "INPUT/OUTPUT cards de la API.",
        "parameters": [],
    },
    "POST /api/v1/run-evaluation": {
        "endpoint": "POST /api/v1/run-evaluation",
        "description": (
            "Ejecuta el golden dataset contra el entorno simulado y detecta deriva. "
            "No realiza llamadas externas."
        ),
        "parameters": [
            {"name": "trigger", "type": "string", "required": False, "default": "manual"},
            {"name": "scenario", "type": "string", "required": False, "description": "healthy, api_schema_change, html_selector_change, data_distribution_shift, latency_regression, error_regression, timeout_regression, behavioral_regression, quality_regression"},
            {"name": "scenario_params", "type": "object", "required": False, "default": {}},
        ],
    },
    "GET /api/v1/baseline": {
        "endpoint": "GET /api/v1/baseline",
        "description": "Lista los baselines registrados.",
        "parameters": [
            {"name": "tool", "type": "string", "required": False, "in": "query"},
        ],
    },
    "POST /api/v1/baseline": {
        "endpoint": "POST /api/v1/baseline",
        "description": "Crea un baseline desde la última corrida o manualmente.",
        "parameters": [
            {"name": "from_last_run", "type": "boolean", "required": False, "default": True},
            {"name": "tool", "type": "string", "required": False},
            {"name": "metrics", "type": "object", "required": False},
        ],
    },
    "GET /api/v1/datasets": {
        "endpoint": "GET /api/v1/datasets",
        "description": "Metadatos del golden dataset y casos públicos (secretos omitidos).",
        "parameters": [
            {"name": "include_secret", "type": "boolean", "required": False, "default": False, "description": "Si true, incluye metadatos de casos secretos (no payloads)."},
        ],
    },
    "GET /api/v1/history": {
        "endpoint": "GET /api/v1/history",
        "description": "Historial de evaluaciones ejecutadas.",
        "parameters": [
            {"name": "limit", "type": "integer", "required": False, "default": 50, "in": "query"},
        ],
    },
    "GET /api/v1/alerts": {
        "endpoint": "GET /api/v1/alerts",
        "description": "Alertas emitidas por el sistema.",
        "parameters": [
            {"name": "active_only", "type": "boolean", "required": False, "default": False, "in": "query"},
        ],
    },
    "POST /api/v1/alerts/acknowledge": {
        "endpoint": "POST /api/v1/alerts/acknowledge",
        "description": "Reconoce una alerta por ID.",
        "parameters": [
            {"name": "alert_id", "type": "string", "required": True},
        ],
    },
    "GET /api/v1/status": {
        "endpoint": "GET /api/v1/status",
        "description": "Estado global del orquestador, última corrida, baselines y alertas.",
        "parameters": [],
    },
    "GET /api/v1/metrics": {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus del orquestador.",
        "parameters": [],
    },
    "POST /api/v1/reset": {
        "endpoint": "POST /api/v1/reset",
        "description": "Reinicia el estado del orquestador (dataset se recarga por defecto).",
        "parameters": [
            {"name": "reinitialize", "type": "boolean", "required": False, "default": True},
        ],
    },
    "POST /api/v1/cc-experiments": {
        "endpoint": "POST /api/v1/cc-experiments",
        "description": "Create a new Champion/Challenger experiment (deterministic paper-only).",
        "parameters": [
            {"name": "experiment_id", "type": "string", "required": False},
            {"name": "symbol", "type": "string", "required": False, "default": "DEMO"},
            {"name": "initial_cash", "type": "number", "required": False, "default": 1000000.0},
            {"name": "min_paired_samples", "type": "integer", "required": False, "default": 30},
            {"name": "walk_forward_samples", "type": "integer", "required": False, "default": 30},
            {"name": "shadow_samples", "type": "integer", "required": False, "default": 30},
            {"name": "paper_samples", "type": "integer", "required": False, "default": 30},
        ],
    },
    "GET /api/v1/cc-experiments": {
        "endpoint": "GET /api/v1/cc-experiments",
        "description": "List active Champion/Challenger experiments.",
        "parameters": [],
    },
    "GET /api/v1/cc-experiments/<id>": {
        "endpoint": "GET /api/v1/cc-experiments/<id>",
        "description": "Get experiment status.",
        "parameters": [],
    },
    "POST /api/v1/cc-experiments/<id>/register": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/register",
        "description": "Register deterministic demo champion/challenger predictors.",
        "parameters": [
            {"name": "champion_model_id", "type": "string", "required": False, "default": "champion"},
            {"name": "champion_version", "type": "string", "required": False, "default": "1.0.0"},
            {"name": "challenger_model_id", "type": "string", "required": False, "default": "challenger"},
            {"name": "challenger_version", "type": "string", "required": False, "default": "2.0.0"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/start": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/start",
        "description": "Start the experiment in a given stage.",
        "parameters": [
            {"name": "stage", "type": "string", "required": False, "default": "historical"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/ingest": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/ingest",
        "description": "Ingest one canonical market event.",
        "parameters": [
            {"name": "event_id", "type": "string", "required": True},
            {"name": "source_ts", "type": "number", "required": True},
            {"name": "receive_ts", "type": "number", "required": True},
            {"name": "symbol", "type": "string", "required": True},
            {"name": "bid", "type": "number", "required": True},
            {"name": "ask", "type": "number", "required": True},
            {"name": "bid_size", "type": "number", "required": True},
            {"name": "ask_size", "type": "number", "required": True},
            {"name": "reference_bid", "type": "number", "required": True},
            {"name": "reference_ask", "type": "number", "required": True},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/evaluate": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/evaluate",
        "description": "Evaluate current metrics and stage gate.",
        "parameters": [],
    },
    "POST /api/v1/cc-experiments/<id>/recommend": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/recommend",
        "description": "Generate a promotion recommendation (no auto-promotion).",
        "parameters": [],
    },
    "POST /api/v1/cc-experiments/<id>/approve": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/approve",
        "description": "Explicit human approval bound to report_hash + versions with TTL and anti-replay.",
        "parameters": [
            {"name": "report_hash", "type": "string", "required": True},
            {"name": "reviewer_id", "type": "string", "required": True},
            {"name": "request_id", "type": "string", "required": True},
            {"name": "ttl_seconds", "type": "number", "required": False, "default": 3600.0},
            {"name": "timestamp", "type": "number", "required": False},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/shutdown": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/shutdown",
        "description": "Safely shutdown the experiment: reject events, cancel paper orders, reconcile.",
        "parameters": [
            {"name": "reason", "type": "string", "required": False, "default": "api-request"},
        ],
    },
}

# ---------------------------------------------------------------------------
# OUTPUT Cards
# ---------------------------------------------------------------------------
OUTPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "GET /health": {
        "endpoint": "GET /health",
        "description": "Estado del servicio.",
        "fields": [
            {"name": "status", "type": "string"},
            {"name": "service", "type": "string"},
        ],
    },
    "GET /api/v1/schema": {
        "endpoint": "GET /api/v1/schema",
        "description": "Cards de entrada y salida.",
        "fields": [
            {"name": "input_cards", "type": "object"},
            {"name": "output_cards", "type": "object"},
        ],
    },
    "POST /api/v1/run-evaluation": {
        "endpoint": "POST /api/v1/run-evaluation",
        "description": "Resultado de la evaluación.",
        "fields": [
            {"name": "run_id", "type": "string"},
            {"name": "timestamp", "type": "number"},
            {"name": "trigger", "type": "string"},
            {"name": "dataset_version", "type": "string"},
            {"name": "dataset_hash", "type": "string"},
            {"name": "system_status", "type": "string"},
            {"name": "drift_signals", "type": "array"},
            {"name": "alert_ids", "type": "array"},
            {"name": "aggregate", "type": "object"},
            {"name": "duration_ms", "type": "number"},
        ],
    },
    "GET /api/v1/baseline": {
        "endpoint": "GET /api/v1/baseline",
        "description": "Lista de baselines.",
        "fields": [{"name": "baselines", "type": "array"}],
    },
    "POST /api/v1/baseline": {
        "endpoint": "POST /api/v1/baseline",
        "description": "Confirmación de creación de baseline.",
        "fields": [
            {"name": "created", "type": "array"},
            {"name": "count", "type": "integer"},
        ],
    },
    "GET /api/v1/datasets": {
        "endpoint": "GET /api/v1/datasets",
        "description": "Metadatos del golden dataset.",
        "fields": [
            {"name": "version", "type": "string"},
            {"name": "case_count", "type": "integer"},
            {"name": "public_case_count", "type": "integer"},
            {"name": "secret_case_count", "type": "integer"},
            {"name": "signature", "type": "object"},
            {"name": "public_cases", "type": "array"},
            {"name": "secret_cases_metadata", "type": "array"},
        ],
    },
    "GET /api/v1/history": {
        "endpoint": "GET /api/v1/history",
        "description": "Historial de corridas.",
        "fields": [{"name": "runs", "type": "array"}, {"name": "count", "type": "integer"}],
    },
    "GET /api/v1/alerts": {
        "endpoint": "GET /api/v1/alerts",
        "description": "Alertas.",
        "fields": [
            {"name": "alerts", "type": "array"},
            {"name": "active_count", "type": "integer"},
            {"name": "history", "type": "array"},
        ],
    },
    "POST /api/v1/alerts/acknowledge": {
        "endpoint": "POST /api/v1/alerts/acknowledge",
        "description": "Resultado del reconocimiento.",
        "fields": [
            {"name": "acknowledged", "type": "boolean"},
            {"name": "alert_id", "type": "string"},
        ],
    },
    "GET /api/v1/status": {
        "endpoint": "GET /api/v1/status",
        "description": "Estado global.",
        "fields": [
            {"name": "service", "type": "string"},
            {"name": "status", "type": "string"},
            {"name": "latest_run", "type": "object|null"},
            {"name": "run_count", "type": "integer"},
            {"name": "baseline_count", "type": "integer"},
            {"name": "active_alerts", "type": "integer"},
            {"name": "total_alerts", "type": "integer"},
            {"name": "scheduler", "type": "object"},
            {"name": "observability", "type": "object"},
        ],
    },
    "GET /api/v1/metrics": {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus.",
        "fields": [{"name": "text", "type": "string"}],
    },
    "POST /api/v1/reset": {
        "endpoint": "POST /api/v1/reset",
        "description": "Confirmación de reinicio.",
        "fields": [{"name": "status", "type": "string"}],
    },
    "POST /api/v1/cc-experiments": {
        "endpoint": "POST /api/v1/cc-experiments",
        "description": "Created experiment summary.",
        "fields": [
            {"name": "experiment_id", "type": "string"},
            {"name": "state", "type": "string"},
            {"name": "config", "type": "object"},
        ],
    },
    "GET /api/v1/cc-experiments": {
        "endpoint": "GET /api/v1/cc-experiments",
        "description": "List of experiments.",
        "fields": [{"name": "experiments", "type": "array"}],
    },
    "GET /api/v1/cc-experiments/<id>": {
        "endpoint": "GET /api/v1/cc-experiments/<id>",
        "description": "Experiment status.",
        "fields": [
            {"name": "experiment_id", "type": "string"},
            {"name": "state", "type": "string"},
            {"name": "samples_in_stage", "type": "integer"},
            {"name": "total_events", "type": "integer"},
            {"name": "audit_chain_valid", "type": "boolean"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/register": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/register",
        "description": "Registered champion/challenger models.",
        "fields": [
            {"name": "experiment_id", "type": "string"},
            {"name": "champion", "type": "object"},
            {"name": "challenger", "type": "object"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/start": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/start",
        "description": "Stage transition result.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "stage", "type": "string"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/ingest": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/ingest",
        "description": "Ingestion result.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "event_id", "type": "string"},
            {"name": "correlation_id", "type": "string"},
            {"name": "stage", "type": "string"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/evaluate": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/evaluate",
        "description": "Metrics and stage gate.",
        "fields": [
            {"name": "experiment_id", "type": "string"},
            {"name": "stage", "type": "string"},
            {"name": "gate", "type": "object"},
            {"name": "metrics", "type": "object"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/recommend": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/recommend",
        "description": "Promotion recommendation with report hash.",
        "fields": [
            {"name": "experiment_id", "type": "string"},
            {"name": "report_hash", "type": "string"},
            {"name": "recommended_action", "type": "string"},
            {"name": "reason", "type": "string"},
            {"name": "metrics_summary", "type": "object"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/approve": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/approve",
        "description": "Approval result.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "state", "type": "string"},
        ],
    },
    "POST /api/v1/cc-experiments/<id>/shutdown": {
        "endpoint": "POST /api/v1/cc-experiments/<id>/shutdown",
        "description": "Shutdown result.",
        "fields": [
            {"name": "success", "type": "boolean"},
            {"name": "final_state", "type": "string"},
            {"name": "reconciliation", "type": "object"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-308 Agent Drift Orchestrator"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-308 — Agent Drift / Environmental Degradation",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/run-evaluation"},
            {"method": "GET", "path": "/api/v1/baseline"},
            {"method": "POST", "path": "/api/v1/baseline"},
            {"method": "GET", "path": "/api/v1/datasets"},
            {"method": "GET", "path": "/api/v1/history"},
            {"method": "GET", "path": "/api/v1/alerts"},
            {"method": "POST", "path": "/api/v1/alerts/acknowledge"},
            {"method": "GET", "path": "/api/v1/status"},
            {"method": "GET", "path": "/api/v1/metrics"},
            {"method": "POST", "path": "/api/v1/reset"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/run-evaluation", methods=["POST"])
def run_evaluation():
    _ensure_baselines()
    payload = request.get_json(silent=True) or {}
    scenario = payload.get("scenario")
    scenario_params = payload.get("scenario_params")
    trigger = payload.get("trigger", "manual")
    run = _orchestrator.run_evaluation(
        trigger=trigger,
        scenario=scenario,
        scenario_params=scenario_params,
    )
    return jsonify(run.to_dict())


@app.route("/api/v1/baseline", methods=["GET"])
def list_baselines():
    return jsonify({"baselines": _orchestrator.baseline_manager.list_baselines()})


@app.route("/api/v1/baseline", methods=["POST"])
def create_baseline():
    _ensure_baselines()
    payload = request.get_json(silent=True) or {}
    if payload.get("from_last_run", True):
        if not _orchestrator.history:
            return jsonify({"error": "no evaluation runs available"}), 400
        last_run = _orchestrator.history[-1]
        created = _orchestrator.baseline_manager.record_baseline_from_run(
            last_run, _orchestrator.config, label="manual"
        )
    else:
        tool = payload.get("tool", "default")
        metrics = payload.get("metrics", {})
        created = [
            _orchestrator.baseline_manager.create_synthetic_baseline(
                agent_id=_orchestrator.config.agent_id,
                tool=tool,
                environment=_orchestrator.config.environment,
                agent_version=_orchestrator.config.agent_version,
                metrics=metrics,
            )
        ]
    return jsonify({"created": [b.to_dict() for b in created], "count": len(created)})


@app.route("/api/v1/datasets", methods=["GET"])
def datasets():
    include_secret = request.args.get("include_secret", "false").lower() == "true"
    return jsonify(_orchestrator.dataset.to_dict(include_secret=include_secret))


@app.route("/api/v1/history", methods=["GET"])
def history():
    limit = request.args.get("limit", 50, type=int)
    runs = _orchestrator.get_history()[-limit:]
    return jsonify({"runs": runs, "count": len(runs)})


@app.route("/api/v1/alerts", methods=["GET"])
def alerts():
    active_only = request.args.get("active_only", "false").lower() == "true"
    data = _orchestrator.get_alerts()
    if active_only:
        data = {
            "alerts": [a for a in data["alerts"] if not a.get("acknowledged")],
            "active_count": sum(1 for a in data["alerts"] if not a.get("acknowledged")),
            "history": data["history"],
        }
    return jsonify(data)


@app.route("/api/v1/alerts/acknowledge", methods=["POST"])
def acknowledge_alert():
    payload = request.get_json(silent=True) or {}
    alert_id = payload.get("alert_id")
    if not alert_id:
        return jsonify({"error": "alert_id is required"}), 400
    ok = _orchestrator.acknowledge_alert(alert_id)
    return jsonify({"acknowledged": ok, "alert_id": alert_id})


@app.route("/api/v1/status", methods=["GET"])
def status():
    _ensure_baselines()
    return jsonify(_orchestrator.get_status())


@app.route("/api/v1/metrics", methods=["GET"])
def metrics():
    return _orchestrator.get_metrics(), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/api/v1/reset", methods=["POST"])
def reset():
    payload = request.get_json(silent=True) or {}
    _orchestrator.reset()
    if payload.get("reinitialize", True):
        _orchestrator.initialize_baselines(scenario="healthy")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Champion/Challenger experiment endpoints
# ---------------------------------------------------------------------------

def _get_experiment(exp_id: str):
    exp = _cc_manager.get(exp_id)
    if exp is None:
        return None, (jsonify({"error": "experiment not found", "experiment_id": exp_id}), 404)
    return exp, None


@app.route("/api/v1/cc-experiments", methods=["POST"])
def cc_create():
    payload = request.get_json(silent=True) or {}
    try:
        cfg = ExperimentConfig(**payload) if payload else ExperimentConfig()
    except TypeError as exc:
        return jsonify({"error": f"invalid config: {exc}"}), 400
    exp = _cc_manager.create(config=cfg)
    return jsonify({"experiment_id": exp.experiment_id, "state": exp.state, "config": exp.config.to_dict()})


@app.route("/api/v1/cc-experiments", methods=["GET"])
def cc_list():
    return jsonify({"experiments": _cc_manager.list_experiments()})


@app.route("/api/v1/cc-experiments/<exp_id>", methods=["GET"])
def cc_status(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    return jsonify(exp.status())


@app.route("/api/v1/cc-experiments/<exp_id>/register", methods=["POST"])
def cc_register(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    champion_id = payload.get("champion_model_id", "champion")
    champion_version = payload.get("champion_version", "1.0.0")
    challenger_id = payload.get("challenger_model_id", "challenger")
    challenger_version = payload.get("challenger_version", "2.0.0")
    if exp.champion_reg is None:
        exp.register_champion(champion_id, champion_version, ChampionDemoPredictor(), metadata=payload.get("champion_metadata", {}))
    if exp.challenger_reg is None:
        exp.register_challenger(challenger_id, challenger_version, ChallengerDemoPredictor(), metadata=payload.get("challenger_metadata", {}))
    return jsonify({
        "experiment_id": exp_id,
        "champion": exp.champion_reg.to_dict() if exp.champion_reg else None,
        "challenger": exp.challenger_reg.to_dict() if exp.challenger_reg else None,
    })


@app.route("/api/v1/cc-experiments/<exp_id>/start", methods=["POST"])
def cc_start(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    stage = payload.get("stage", "historical")
    result = exp.start(stage)
    if not result.get("success"):
        return jsonify({"error": result.get("reason", "start failed"), "experiment_id": exp_id}), 400
    return jsonify(result)


@app.route("/api/v1/cc-experiments/<exp_id>/ingest", methods=["POST"])
def cc_ingest(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    try:
        event = MarketEvent(**payload)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"invalid market event: {exc}", "experiment_id": exp_id}), 400
    result = exp.ingest_event(event)
    return jsonify(result)


@app.route("/api/v1/cc-experiments/<exp_id>/evaluate", methods=["POST"])
def cc_evaluate(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    result = exp.evaluate_stage_gate()
    metrics = exp.compute_metrics()
    return jsonify({
        "experiment_id": exp_id,
        "stage": exp.state,
        "gate": result,
        "metrics": {role: m.to_dict() for role, m in metrics.items()},
    })


@app.route("/api/v1/cc-experiments/<exp_id>/recommend", methods=["POST"])
def cc_recommend(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    rec = exp.recommend_promotion()
    return jsonify(rec.to_dict())


@app.route("/api/v1/cc-experiments/<exp_id>/approve", methods=["POST"])
def cc_approve(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    report_hash = payload.get("report_hash")
    reviewer_id = payload.get("reviewer_id")
    request_id = payload.get("request_id")
    ttl = payload.get("ttl_seconds", 3600.0)
    ts = payload.get("timestamp")
    if not report_hash or not reviewer_id or not request_id:
        return jsonify({"error": "report_hash, reviewer_id and request_id are required", "experiment_id": exp_id}), 400
    result = exp.approve_promotion(report_hash, reviewer_id, request_id, ttl_seconds=ttl, timestamp=ts)
    return jsonify(result)


@app.route("/api/v1/cc-experiments/<exp_id>/shutdown", methods=["POST"])
def cc_shutdown(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    result = exp.shutdown_experiment(payload.get("reason", "api-request"))
    return jsonify(result)


@app.route("/api/v1/cc-experiments/<exp_id>/generate-events", methods=["POST"])
def cc_generate_events(exp_id: str):
    exp, err = _get_experiment(exp_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    n = int(payload.get("n", 100))
    if not (1 <= n <= 10_000):
        return jsonify({"error": "n must be between 1 and 10000", "experiment_id": exp_id}), 400
    symbol = payload.get("symbol", exp.config.symbol)
    seed = int(payload.get("seed", 42))
    events = generate_market_events(symbol=symbol, n=n, seed=seed)
    ingested = 0
    rejected = 0
    for event in events:
        result = exp.ingest_event(event)
        if result.get("success"):
            ingested += 1
        else:
            rejected += 1
    return jsonify({"experiment_id": exp_id, "generated": n, "ingested": ingested, "rejected": rejected})


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="UC-308 Agent Drift Orchestrator API")
    parser.add_argument("--port", type=int, default=5308)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
