"""UC-320 — API REST Flask para exponer el pipeline de Hugging Face + UC-315/317/324.

AAA: Los usuarios se autentican con su cuenta de Hugging Face.
El token HF del usuario viene en el header `Authorization: Bearer hf_xxx`.
UTRON.AI accede al catálogo de HF sin restricciones. Los cargos de GPU
van a la cuenta HF del usuario, no a UTRON.AI.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from flask import Flask, g, jsonify, request

from hf_auth import (
    ENDPOINT_PERMISSIONS,
    HFAuth,
    UserSession,
    extract_hf_token,
    get_user_session,
    get_user_token,
    init_auth,
    require_permission,
)
from hf_script_generator import FineTuneConfig
from orchestrator import UC320Orchestrator

app = Flask(__name__)
orch = UC320Orchestrator()
auth = HFAuth(backend=os.environ.get("UC320_BACKEND", "mock"))
init_auth(app, auth)

# ---------------------------------------------------------------------------
# Cards de entrada
# ---------------------------------------------------------------------------
INPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/sentiment": {
        "endpoint": "POST /api/v1/sentiment",
        "description": "Analiza sentimiento de una noticia de mercado via HF Gateway + UC-324 gates.",
        "parameters": [
            {"name": "ticker", "type": "string", "required": True, "example": "AAPL"},
            {"name": "article", "type": "string", "required": True, "example": "Apple beats earnings expectations by 15%"},
            {"name": "model_id", "type": "string", "required": False, "default": "mock/sentiment-mock"},
        ],
    },
    "POST /api/v1/embedding": {
        "endpoint": "POST /api/v1/embedding",
        "description": "Genera embeddings semánticos via HF Gateway + UC-324 gates.",
        "parameters": [
            {"name": "text", "type": "string", "required": True, "example": "The market rallied today"},
            {"name": "model_id", "type": "string", "required": False, "default": "sentence-transformers/all-MiniLM-L6-v2"},
        ],
    },
    "POST /api/v1/classify": {
        "endpoint": "POST /api/v1/classify",
        "description": "Clasificación zero-shot via HF Gateway + UC-324 gates.",
        "parameters": [
            {"name": "text", "type": "string", "required": True},
            {"name": "candidate_labels", "type": "list[string]", "required": False, "default": []},
            {"name": "model_id", "type": "string", "required": False, "default": "facebook/bart-large-mnli"},
        ],
    },
    "POST /api/v1/benchmark": {
        "endpoint": "POST /api/v1/benchmark",
        "description": "Compara varios modelos con el mismo prompt en paralelo.",
        "parameters": [
            {"name": "prompt", "type": "string", "required": True},
            {"name": "models", "type": "list[[string,string]]", "required": False, "default": [["mock/sentiment-mock","mock"]]},
        ],
    },
    "POST /api/v1/training/submit": {
        "endpoint": "POST /api/v1/training/submit",
        "description": "Envía un job de entrenamiento (requiere aprobación UC-324).",
        "parameters": [
            {"name": "base_model", "type": "string", "required": True},
            {"name": "dataset_id", "type": "string", "required": True},
            {"name": "dataset_revision", "type": "string", "required": True},
            {"name": "objective", "type": "string", "required": True},
        ],
    },
    "POST /api/v1/training/run": {
        "endpoint": "POST /api/v1/training/run",
        "description": "Ejecuta un job de entrenamiento aprobado.",
        "parameters": [
            {"name": "job_id", "type": "string", "required": True},
        ],
    },
    "POST /api/v1/training/promote": {
        "endpoint": "POST /api/v1/training/promote",
        "description": "Promueve un modelo a producción (requiere aprobación humana).",
        "parameters": [
            {"name": "job_id", "type": "string", "required": True},
            {"name": "human_approved", "type": "boolean", "required": True},
        ],
    },
}

# ---------------------------------------------------------------------------
# Cards de salida
# ---------------------------------------------------------------------------
OUTPUT_CARDS: Dict[str, Dict[str, Any]] = {
    "POST /api/v1/sentiment": {
        "endpoint": "POST /api/v1/sentiment",
        "description": "Evidencia de sentimiento + decisión de UC-324 gates.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "operation", "type": "string"},
            {"name": "allowed", "type": "boolean"},
            {"name": "verdict", "type": "string"},
            {"name": "issues", "type": "list[string]"},
            {"name": "warnings", "type": "list[string]"},
            {"name": "evidence", "type": "object (SentimentEvidence)"},
            {"name": "audit_log", "type": "list[object]"},
            {"name": "latency_ms", "type": "float"},
        ],
    },
    "POST /api/v1/embedding": {
        "endpoint": "POST /api/v1/embedding",
        "description": "Embedding + decisión de UC-324 gates.",
        "fields": [
            {"name": "request_id", "type": "string"},
            {"name": "allowed", "type": "boolean"},
            {"name": "evidence", "type": "object (EmbeddingResult)"},
            {"name": "audit_log", "type": "list[object]"},
        ],
    },
    "POST /api/v1/benchmark": {
        "endpoint": "POST /api/v1/benchmark",
        "description": "Análisis comparativo de modelos.",
        "fields": [
            {"name": "total_models", "type": "int"},
            {"name": "successful", "type": "int"},
            {"name": "failed", "type": "int"},
            {"name": "fastest", "type": "object|null"},
            {"name": "cheapest", "type": "object|null"},
            {"name": "avg_latency_ms", "type": "float"},
            {"name": "avg_cost", "type": "float"},
            {"name": "results", "type": "list[object]"},
        ],
    },
    "POST /api/v1/training/submit": {
        "endpoint": "POST /api/v1/training/submit",
        "description": "Job creado o bloqueado por UC-324.",
        "fields": [
            {"name": "allowed", "type": "boolean"},
            {"name": "job_id", "type": "string (si allowed)"},
            {"name": "status", "type": "string (si allowed)"},
            {"name": "issues", "type": "list[string] (si blocked)"},
        ],
    },
    "POST /api/v1/training/promote": {
        "endpoint": "POST /api/v1/training/promote",
        "description": "Resultado de promoción.",
        "fields": [
            {"name": "promoted", "type": "boolean"},
            {"name": "reason", "type": "string (si no promoted)"},
            {"name": "checkpoint_hash", "type": "string (si promoted)"},
            {"name": "model_card", "type": "object (si promoted)"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health() -> Dict[str, Any]:
    return jsonify({"status": "ok", "service": "uc-320-hf-integration"})


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.route("/api/v1/auth/login", methods=["POST"])
def auth_login() -> Dict[str, Any]:
    """Autentica al usuario con su token de Hugging Face.

    El token viene en el header Authorization: Bearer hf_xxx
    o en el body como {"hf_token": "hf_xxx"}.
    """
    hf_token = extract_hf_token() or (request.get_json(silent=True) or {}).get("hf_token", "")
    if not hf_token:
        return jsonify({"error": "unauthorized", "message": "Hugging Face token required"}), 401
    success, session, error = auth.authenticate(hf_token)
    if not success:
        return jsonify({"error": "unauthorized", "message": error}), 401
    return jsonify({
        "authenticated": True,
        "session": session.to_dict(),
        "message": f"Welcome {session.hf_username}! You are logged into UTRON.AI via Hugging Face.",
    })


@app.route("/api/v1/auth/whoami", methods=["GET"])
def auth_whoami() -> Dict[str, Any]:
    """Retorna la identidad del usuario autenticado."""
    session = get_user_session()
    if not session:
        return jsonify({"error": "unauthorized", "message": "Not authenticated"}), 401
    return jsonify({
        "username": session.hf_username,
        "name": session.hf_name,
        "email": session.hf_email,
        "orgs": session.hf_orgs,
        "role": session.role.value,
        "permissions": list(sorted(__import__("hf_auth").ROLE_PERMISSIONS.get(session.role, set()))),
        "session_id": session.session_id,
    })


@app.route("/api/v1/auth/logout", methods=["POST"])
def auth_logout() -> Dict[str, Any]:
    """Cierra la sesión del usuario."""
    session = get_user_session()
    if not session:
        return jsonify({"error": "unauthorized", "message": "Not authenticated"}), 401
    auth.logout(session.session_id)
    return jsonify({"logged_out": True, "username": session.hf_username})


@app.route("/api/v1/auth/status", methods=["GET"])
def auth_status() -> Dict[str, Any]:
    """Estado del servicio de autenticación (público)."""
    return jsonify({
        "auth_backend": auth.backend,
        "active_sessions": len(auth.list_sessions()),
        "auth_method": "Hugging Face token (Authorization: Bearer hf_xxx)",
        "billing": "GPU charges go to the user's Hugging Face account, not UTRON.AI",
    })


@app.route("/api/v1/auth/sessions", methods=["GET"])
def auth_sessions() -> Dict[str, Any]:
    """Lista sesiones activas (solo admin)."""
    session = get_user_session()
    if not session or session.role.value != "admin":
        return jsonify({"error": "forbidden", "message": "Admin role required"}), 403
    return jsonify({"sessions": auth.list_sessions()})


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> Dict[str, Any]:
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/models", methods=["GET"])
@require_permission("catalog:browse")
def list_models() -> Dict[str, Any]:
    task = request.args.get("task")
    return jsonify({"models": orch.catalog.list_models(task=task)})


@app.route("/api/v1/templates", methods=["GET"])
@require_permission("catalog:browse")
def list_templates() -> Dict[str, Any]:
    return jsonify({"templates": orch.list_templates()})


@app.route("/api/v1/templates/<template_id>", methods=["GET"])
@require_permission("catalog:browse")
def get_template(template_id: str) -> Dict[str, Any]:
    t = orch.get_template(template_id)
    if not t:
        return jsonify({"error": f"Template {template_id} not found"}), 404
    return jsonify(t)


@app.route("/api/v1/sentiment", methods=["POST"])
@require_permission("inference:read")
def sentiment() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    ticker = payload.get("ticker")
    article = payload.get("article")
    if not ticker or not article:
        return jsonify({"error": "ticker and article are required"}), 400
    model_id = payload.get("model_id", "mock/sentiment-mock")
    # Crear gateway con token del usuario para billing al usuario
    user_token = get_user_token()
    if user_token and model_id != "mock/sentiment-mock":
        from hf_gateway import HuggingFaceModelGateway
        gw = HuggingFaceModelGateway(catalog=orch.catalog, backend=os.environ.get("UC320_BACKEND", "mock"), token=user_token)
        from skills import MarketSentimentSkill
        from contracts import ContractBuilder
        from uc324_gates import Verdict
        import time
        contract = ContractBuilder.sentiment_inference(ticker, article, model_id, orch.catalog.get(model_id).provider if orch.catalog.get(model_id) else "mock")
        entry = orch.catalog.get(model_id)
        gate_input = contract.to_gate_dict(
            allowed_models=orch.catalog.allowed_models(),
            estimated_cost=entry.cost_per_1k if entry else 0.0,
            estimated_latency=entry.latency_ms if entry else 500.0,
        )
        pre_results = orch.gates.gate_pre(gate_input)
        pre_issues = [r.message for r in pre_results if r.verdict.value == "block"]
        if pre_issues:
            return jsonify({"allowed": False, "verdict": "block", "issues": pre_issues, "request_id": contract.request_id})
        exec_results = orch.gates.gate_exec(gate_input)
        exec_issues = [r.message for r in exec_results if r.verdict.value == "block"]
        if exec_issues:
            return jsonify({"allowed": False, "verdict": "block", "issues": exec_issues, "request_id": contract.request_id})
        try:
            evidence = MarketSentimentSkill(gw, model_id).run(ticker, article, contract.request_id)
            evidence_dict = evidence.model_dump()
        except Exception as exc:
            return jsonify({"allowed": False, "verdict": "block", "issues": [f"Execution error: {exc}"], "request_id": contract.request_id})
        post_results = orch.gates.gate_post(gate_input, evidence_dict)
        all_issues = pre_issues + exec_issues + [r.message for r in post_results if r.verdict.value == "block"]
        allowed = len(all_issues) == 0
        return jsonify({
            "request_id": contract.request_id,
            "operation": contract.operation,
            "allowed": allowed,
            "verdict": "allow" if allowed else "block",
            "issues": all_issues,
            "evidence": evidence_dict,
            "billing": {"charged_to": get_user_session().hf_username if get_user_session() else "unknown", "note": "GPU charges go to your Hugging Face account"},
        })
    result = orch.sentiment(ticker, article, model_id)
    resp = result.to_dict()
    resp["billing"] = {"charged_to": get_user_session().hf_username if get_user_session() else "unknown", "note": "Mock backend: no charges"}
    return jsonify(resp)


@app.route("/api/v1/embedding", methods=["POST"])
@require_permission("inference:read")
def embedding() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    text = payload.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400
    model_id = payload.get("model_id", "sentence-transformers/all-MiniLM-L6-v2")
    result = orch.embedding(text, model_id)
    resp = result.to_dict()
    resp["billing"] = {"charged_to": get_user_session().hf_username if get_user_session() else "unknown"}
    return jsonify(resp)


@app.route("/api/v1/classify", methods=["POST"])
@require_permission("inference:read")
def classify() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    text = payload.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400
    labels = payload.get("candidate_labels", [])
    model_id = payload.get("model_id", "facebook/bart-large-mnli")
    result = orch.classify(text, labels, model_id)
    resp = result.to_dict()
    resp["billing"] = {"charged_to": get_user_session().hf_username if get_user_session() else "unknown"}
    return jsonify(resp)


@app.route("/api/v1/benchmark", methods=["POST"])
@require_permission("benchmark:run")
def benchmark() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    prompt = payload.get("prompt")
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    models = payload.get("models")
    result = orch.run_benchmark(prompt, models)
    return jsonify(result)


@app.route("/api/v1/training/submit", methods=["POST"])
@require_permission("models:train")
def training_submit() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    base_model = payload.get("base_model")
    dataset_id = payload.get("dataset_id")
    dataset_revision = payload.get("dataset_revision")
    objective = payload.get("objective")
    if not all([base_model, dataset_id, dataset_revision, objective]):
        return jsonify({"error": "base_model, dataset_id, dataset_revision, objective are required"}), 400
    result = orch.submit_training(base_model, dataset_id, dataset_revision, objective)
    return jsonify(result)


@app.route("/api/v1/training/run", methods=["POST"])
@require_permission("models:train")
def training_run() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    job_id = payload.get("job_id")
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    result = orch.run_training(job_id)
    return jsonify(result)


@app.route("/api/v1/training/promote", methods=["POST"])
@require_permission("training:promote")
def training_promote() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    job_id = payload.get("job_id")
    human_approved = payload.get("human_approved", False)
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    result = orch.promote_model(job_id, human_approved)
    return jsonify(result)


@app.route("/api/v1/training/jobs", methods=["GET"])
@require_permission("models:train")
def training_jobs() -> Dict[str, Any]:
    return jsonify({"jobs": orch.training.list_jobs()})


@app.route("/api/v1/audit", methods=["GET"])
@require_permission("catalog:browse")
def audit() -> Dict[str, Any]:
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"audit_log": orch.gateway.get_audit_log(limit=limit)})


# ---------------------------------------------------------------------------
# HF Services endpoints
# ---------------------------------------------------------------------------
@app.route("/api/v1/hf/status", methods=["GET"])
def hf_status() -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        status = user_svc.status()
    else:
        status = orch.hf_status()
    session = get_user_session()
    status["authenticated_user"] = session.hf_username if session else "unknown"
    status["billing"] = "GPU charges go to the user's Hugging Face account"
    return jsonify(status)


# --- Inference Endpoints ---
@app.route("/api/v1/endpoints", methods=["GET"])
@require_permission("catalog:browse")
def list_endpoints() -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify({"endpoints": user_svc.endpoints.list_endpoints(), "billing": "user_hf_account"})
    return jsonify({"endpoints": orch.list_endpoints()})


@app.route("/api/v1/endpoints", methods=["POST"])
@require_permission("endpoints:create")
def create_endpoint() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    model_id = payload.get("model_id")
    if not name or not model_id:
        return jsonify({"error": "name and model_id are required"}), 400
    kwargs = {k: v for k, v in payload.items() if k not in ("name", "model_id")}
    # Usar token del usuario: los cargos van a su cuenta HF
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        from hf_services import InferenceEndpointManager
        from contracts import SecureContract
        contract = SecureContract(
            operation="create_endpoint", model_id=model_id,
            action_class="execute", risk_level="high",
            requires_human_approval=True, input={"name": name, **kwargs},
        )
        decision = orch.gates.evaluate(contract.to_gate_dict(allowed_models=orch.catalog.allowed_models()))
        if not decision.allowed:
            return jsonify({"allowed": False, "issues": decision.issues})
        ep = user_svc.endpoints.create(name=name, model_id=model_id, **kwargs)
        return jsonify({
            "allowed": True, "endpoint": ep.to_dict(),
            "billing": {"charged_to": get_user_session().hf_username, "note": "Endpoint GPU charges go to your Hugging Face account"},
        })
    result = orch.create_endpoint(name=name, model_id=model_id, **kwargs)
    return jsonify(result)


@app.route("/api/v1/endpoints/<endpoint_id>/health", methods=["GET"])
@require_permission("endpoints:health")
def endpoint_health(endpoint_id: str) -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify(user_svc.endpoints.health_check(endpoint_id))
    return jsonify(orch.endpoint_health(endpoint_id))


@app.route("/api/v1/endpoints/<endpoint_id>/stop", methods=["POST"])
@require_permission("endpoints:stop")
def stop_endpoint(endpoint_id: str) -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify(user_svc.endpoints.stop(endpoint_id))
    return jsonify(orch.stop_endpoint(endpoint_id))


@app.route("/api/v1/endpoints/<endpoint_id>", methods=["DELETE"])
@require_permission("endpoints:delete")
def delete_endpoint(endpoint_id: str) -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        from contracts import SecureContract
        contract = SecureContract(
            operation="delete_endpoint", action_class="delete",
            risk_level="critical", requires_human_approval=True,
            input={"endpoint_id": endpoint_id},
        )
        decision = orch.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return jsonify({"allowed": False, "issues": decision.issues})
        return jsonify(user_svc.endpoints.delete(endpoint_id))
    return jsonify(orch.delete_endpoint(endpoint_id))


# --- Datasets ---
@app.route("/api/v1/datasets", methods=["GET"])
@require_permission("datasets:read")
def list_datasets() -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify({"datasets": user_svc.datasets.list_datasets()})
    return jsonify({"datasets": orch.list_datasets()})


@app.route("/api/v1/datasets/load", methods=["POST"])
@require_permission("datasets:load")
def load_dataset() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    dataset_id = payload.get("dataset_id")
    if not dataset_id:
        return jsonify({"error": "dataset_id is required"}), 400
    # Usar token del usuario para acceder a datasets privados
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        from contracts import SecureContract
        contract = SecureContract(
            operation="load_dataset", model_id=dataset_id,
            action_class="read", risk_level="medium",
            input={"dataset_id": dataset_id, "revision": payload.get("revision", "main"), "split": payload.get("split", "train")},
        )
        decision = orch.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return jsonify({"allowed": False, "issues": decision.issues})
        record = user_svc.datasets.load(
            dataset_id,
            payload.get("revision", "main"),
            payload.get("split", "train"),
            payload.get("pii_checked", False),
            payload.get("contamination_checked", False),
        )
        return jsonify({
            "allowed": True, "dataset": record.to_dict(),
            "billing": {"charged_to": get_user_session().hf_username, "note": "Dataset accessed with your Hugging Face token"},
        })
    result = orch.load_dataset(
        dataset_id,
        revision=payload.get("revision", "main"),
        split=payload.get("split", "train"),
        pii_checked=payload.get("pii_checked", False),
        contamination_checked=payload.get("contamination_checked", False),
    )
    return jsonify(result)


@app.route("/api/v1/datasets/validate", methods=["POST"])
@require_permission("datasets:read")
def validate_dataset() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify(user_svc.datasets.validate_for_training(
            payload.get("dataset_id", ""),
            payload.get("revision", "main"),
            payload.get("split", "train"),
        ))
    return jsonify(orch.validate_dataset(
        payload.get("dataset_id", ""),
        payload.get("revision", "main"),
        payload.get("split", "train"),
    ))


@app.route("/api/v1/datasets/transform", methods=["POST"])
@require_permission("datasets:transform")
def transform_dataset() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    return jsonify(orch.transform_dataset(
        payload.get("dataset_id", ""),
        payload.get("revision", "main"),
        payload.get("split", "train"),
        payload.get("fn_name", ""),
        payload.get("params", {}),
    ))


# --- Trainer ---
@app.route("/api/v1/trainer/train", methods=["POST"])
@require_permission("models:train")
def trainer_train() -> Dict[str, Any]:
    from hf_services import TrainingConfig
    payload = request.get_json(force=True) or {}
    config = TrainingConfig(
        base_model=payload.get("base_model", ""),
        dataset_id=payload.get("dataset_id", ""),
        dataset_revision=payload.get("dataset_revision", "main"),
        output_dir=payload.get("output_dir", "artifacts/model"),
        objective=payload.get("objective", ""),
        epochs=payload.get("epochs", 3),
        batch_size=payload.get("batch_size", 8),
        learning_rate=payload.get("learning_rate", 5e-5),
    )
    if not config.base_model or not config.dataset_id:
        return jsonify({"error": "base_model and dataset_id are required"}), 400
    # Usar token del usuario: los cargos de GPU van a su cuenta HF
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        from contracts import ContractBuilder
        contract = ContractBuilder.training(config.base_model, config.dataset_id, config.dataset_revision, config.objective)
        decision = orch.gates.evaluate(contract.to_gate_dict(estimated_cost=5.0, estimated_latency=600000))
        if not decision.allowed:
            return jsonify({"allowed": False, "issues": decision.issues})
        result = user_svc.trainer.train(config, user_svc.datasets, approved=payload.get("approved", True))
        result["billing"] = {
            "charged_to": get_user_session().hf_username,
            "note": "Training GPU charges go to your Hugging Face account, not UTRON.AI",
        }
        return jsonify({"allowed": True, **result})
    result = orch.train_model(config, approved=payload.get("approved", True))
    return jsonify(result)


@app.route("/api/v1/trainer/jobs", methods=["GET"])
@require_permission("models:train")
def trainer_jobs() -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify({"jobs": user_svc.trainer.list_jobs()})
    return jsonify({"jobs": orch.list_trainer_jobs()})


# --- PEFT ---
@app.route("/api/v1/peft/adapters", methods=["GET"])
@require_permission("models:adapt")
def list_peft() -> Dict[str, Any]:
    return jsonify({"adapters": orch.list_peft_adapters()})


@app.route("/api/v1/peft/adapters", methods=["POST"])
@require_permission("models:adapt")
def create_peft() -> Dict[str, Any]:
    from hf_services import PEFTConfig
    payload = request.get_json(force=True) or {}
    config = PEFTConfig(
        base_model=payload.get("base_model", ""),
        adapter_name=payload.get("adapter_name", "lora_adapter"),
        task_type=payload.get("task_type", "SEQ_CLS"),
        r=payload.get("r", 8),
        lora_alpha=payload.get("lora_alpha", 16),
    )
    if not config.base_model:
        return jsonify({"error": "base_model is required"}), 400
    result = orch.create_peft_adapter(config)
    return jsonify(result)


@app.route("/api/v1/peft/adapters/<adapter_id>/save", methods=["POST"])
@require_permission("models:push")
def save_peft(adapter_id: str) -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    if not repo_id:
        return jsonify({"error": "repo_id is required"}), 400
    return jsonify(orch.save_peft_adapter(adapter_id, repo_id))


# --- Evaluate ---
@app.route("/api/v1/evaluate/compute", methods=["POST"])
@require_permission("evaluate:compute")
def evaluate_compute() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    metric_name = payload.get("metric_name")
    predictions = payload.get("predictions", [])
    references = payload.get("references", [])
    if not metric_name:
        return jsonify({"error": "metric_name is required"}), 400
    return jsonify(orch.compute_metrics(metric_name, predictions, references))


@app.route("/api/v1/evaluate/compare", methods=["POST"])
@require_permission("evaluate:compute")
def evaluate_compare() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    return jsonify(orch.compare_models_metrics(
        payload.get("metric_name", ""),
        payload.get("candidates", {}),
    ))


@app.route("/api/v1/evaluate/results", methods=["GET"])
@require_permission("evaluate:compute")
def evaluate_results() -> Dict[str, Any]:
    return jsonify({"results": orch.list_eval_results()})


# --- Spaces ---
@app.route("/api/v1/spaces", methods=["GET"])
@require_permission("spaces:read")
def list_spaces() -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify({"spaces": user_svc.spaces.list_spaces()})
    return jsonify({"spaces": orch.list_spaces()})


@app.route("/api/v1/spaces", methods=["POST"])
@require_permission("spaces:create")
def create_space() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    # Usar token del usuario: el Space se crea en la cuenta HF del usuario
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        from contracts import SecureContract
        contract = SecureContract(
            operation="create_space", model_id=payload.get("model_id", ""),
            action_class="execute", risk_level="medium",
            input={"name": name, "sdk": payload.get("sdk", "gradio"), "public": payload.get("public", False)},
        )
        decision = orch.gates.evaluate(contract.to_gate_dict())
        if not decision.allowed:
            return jsonify({"allowed": False, "issues": decision.issues})
        space = user_svc.spaces.create(
            name=name, sdk=payload.get("sdk", "gradio"),
            model_id=payload.get("model_id", ""),
            hardware=payload.get("hardware", "cpu-basic"),
            description=payload.get("description", ""),
            public=payload.get("public", False),
        )
        return jsonify({
            "allowed": True, "space": space.to_dict(),
            "billing": {"charged_to": get_user_session().hf_username, "note": "Space created under your Hugging Face account"},
        })
    result = orch.create_space(
        name=name,
        sdk=payload.get("sdk", "gradio"),
        model_id=payload.get("model_id", ""),
        hardware=payload.get("hardware", "cpu-basic"),
        description=payload.get("description", ""),
        public=payload.get("public", False),
    )
    return jsonify(result)


@app.route("/api/v1/spaces/<space_id>/stop", methods=["POST"])
@require_permission("spaces:stop")
def stop_space(space_id: str) -> Dict[str, Any]:
    user_token = get_user_token()
    if user_token:
        user_svc = orch.get_user_services(user_token)
        return jsonify(user_svc.spaces.stop(space_id))
    return jsonify(orch.stop_space(space_id))


@app.route("/api/v1/spaces/<space_id>", methods=["DELETE"])
@require_permission("spaces:delete")
def delete_space(space_id: str) -> Dict[str, Any]:
    return jsonify(orch.delete_space(space_id))


# --- Model Cards ---
@app.route("/api/v1/model-cards", methods=["GET"])
@require_permission("model_cards:read")
def list_model_cards() -> Dict[str, Any]:
    return jsonify({"model_cards": orch.list_model_cards()})


@app.route("/api/v1/model-cards", methods=["POST"])
@require_permission("model_cards:create")
def create_model_card() -> Dict[str, Any]:
    from hf_services import ModelCardData
    payload = request.get_json(force=True) or {}
    model_id = payload.get("model_id")
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    data = ModelCardData(
        model_id=model_id,
        base_model=payload.get("base_model", ""),
        license=payload.get("license", "unknown"),
        language=payload.get("language", ["en"]),
        intended_use=payload.get("intended_use", ""),
        limitations=payload.get("limitations", []),
        risks=payload.get("risks", []),
    )
    return jsonify(orch.create_model_card(data))


@app.route("/api/v1/model-cards/<path:model_id>", methods=["GET"])
@require_permission("model_cards:read")
def get_model_card(model_id: str) -> Dict[str, Any]:
    card = orch.get_model_card(model_id)
    if not card:
        return jsonify({"error": "model card not found"}), 404
    return jsonify(card)


@app.route("/api/v1/model-cards/<path:model_id>/markdown", methods=["GET"])
@require_permission("model_cards:read")
def get_model_card_md(model_id: str) -> Dict[str, Any]:
    md = orch.get_model_card_markdown(model_id)
    if not md:
        return jsonify({"error": "model card not found"}), 404
    return jsonify({"model_id": model_id, "markdown": md})


@app.route("/api/v1/model-cards/<path:model_id>/approve", methods=["POST"])
@require_permission("model_cards:approve")
def approve_model_card(model_id: str) -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    return jsonify(orch.approve_model_card(
        model_id,
        payload.get("approved_by", ""),
        payload.get("red_team_passed", False),
    ))


@app.route("/api/v1/model-cards/<path:model_id>/push", methods=["POST"])
@require_permission("model_cards:push")
def push_model_card(model_id: str) -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    if not repo_id:
        return jsonify({"error": "repo_id is required"}), 400
    return jsonify(orch.push_model_card(model_id, repo_id))


# ===========================================================================
# Sección 18 — Exploración del Catálogo HF Hub (api/models, api/datasets, api/spaces)
# ===========================================================================

@app.route("/api/v1/catalog/models", methods=["GET"])
@require_permission("catalog:browse")
def catalog_models() -> Dict[str, Any]:
    """Lista modelos del catálogo de Hugging Face con filtros."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    models = browser.list_models(
        task=request.args.get("task", ""),
        search=request.args.get("search", ""),
        license=request.args.get("license", ""),
        author=request.args.get("author", ""),
        sort=request.args.get("sort", "downloads"),
        direction=request.args.get("direction", "desc"),
        limit=request.args.get("limit", 50, type=int),
        full=request.args.get("full", "false").lower() == "true",
    )
    return jsonify({"models": models, "count": len(models), "source": "huggingface_hub_api"})


@app.route("/api/v1/catalog/datasets", methods=["GET"])
@require_permission("catalog:browse")
def catalog_datasets() -> Dict[str, Any]:
    """Lista datasets del catálogo de Hugging Face con filtros."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    datasets = browser.list_datasets(
        search=request.args.get("search", ""),
        license=request.args.get("license", ""),
        author=request.args.get("author", ""),
        sort=request.args.get("sort", "downloads"),
        direction=request.args.get("direction", "desc"),
        limit=request.args.get("limit", 50, type=int),
    )
    return jsonify({"datasets": datasets, "count": len(datasets), "source": "huggingface_hub_api"})


@app.route("/api/v1/catalog/spaces", methods=["GET"])
@require_permission("catalog:browse")
def catalog_spaces() -> Dict[str, Any]:
    """Lista spaces del catálogo de Hugging Face con filtros."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    spaces = browser.list_spaces(
        search=request.args.get("search", ""),
        author=request.args.get("author", ""),
        sort=request.args.get("sort", "likes"),
        direction=request.args.get("direction", "desc"),
        limit=request.args.get("limit", 50, type=int),
    )
    return jsonify({"spaces": spaces, "count": len(spaces), "source": "huggingface_hub_api"})


@app.route("/api/v1/catalog/search", methods=["GET"])
@require_permission("catalog:browse")
def catalog_search() -> Dict[str, Any]:
    """Búsqueda global en modelos, datasets y spaces."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "q parameter is required"}), 400
    results = browser.search_all(query, limit=request.args.get("limit", 20, type=int))
    return jsonify({
        "query": query,
        "results": results,
        "counts": {k: len(v) for k, v in results.items()},
    })


@app.route("/api/v1/catalog/models/<path:model_id>", methods=["GET"])
@require_permission("catalog:browse")
def catalog_get_model(model_id: str) -> Dict[str, Any]:
    """Obtiene metadatos de un modelo específico del Hub."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    model = browser.get_model(model_id)
    if not model:
        return jsonify({"error": "not_found", "model_id": model_id}), 404
    return jsonify(model)


@app.route("/api/v1/catalog/datasets/<path:dataset_id>", methods=["GET"])
@require_permission("catalog:browse")
def catalog_get_dataset(dataset_id: str) -> Dict[str, Any]:
    """Obtiene metadatos de un dataset específico del Hub."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    ds = browser.get_dataset(dataset_id)
    if not ds:
        return jsonify({"error": "not_found", "dataset_id": dataset_id}), 404
    return jsonify(ds)


@app.route("/api/v1/catalog/spaces/<path:space_id>", methods=["GET"])
@require_permission("catalog:browse")
def catalog_get_space(space_id: str) -> Dict[str, Any]:
    """Obtiene metadatos de un space específico del Hub."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    sp = browser.get_space(space_id)
    if not sp:
        return jsonify({"error": "not_found", "space_id": space_id}), 404
    return jsonify(sp)


# ===========================================================================
# Sección 19 — Gated Models
# ===========================================================================

@app.route("/api/v1/catalog/models/<path:model_id>/gated", methods=["GET"])
@require_permission("catalog:browse")
def catalog_check_gated(model_id: str) -> Dict[str, Any]:
    """Verifica si un modelo es gated y si el usuario tiene acceso."""
    user_token = get_user_token() or ""
    browser = orch.get_catalog_browser(user_token)
    result = browser.check_gated(model_id)
    return jsonify(result)


# ===========================================================================
# Sección 20 — Descarga de Pesos y Code Snippets
# ===========================================================================

@app.route("/api/v1/download/<path:repo_id>/resolve", methods=["GET"])
@require_permission("models:download")
def download_resolve(repo_id: str) -> Dict[str, Any]:
    """Genera URL de descarga directa de un archivo del repo."""
    user_token = get_user_token() or ""
    dl = orch.get_download_manager(user_token)
    filename = request.args.get("filename", "")
    revision = request.args.get("revision", "main")
    if not filename:
        return jsonify({"error": "filename parameter is required"}), 400
    return jsonify(dl.resolve_url(repo_id, filename, revision))


@app.route("/api/v1/download/<path:repo_id>/files", methods=["GET"])
@require_permission("models:download")
def download_files(repo_id: str) -> Dict[str, Any]:
    """Lista archivos disponibles en un repo con URLs de descarga."""
    user_token = get_user_token() or ""
    dl = orch.get_download_manager(user_token)
    revision = request.args.get("revision", "main")
    return jsonify(dl.list_files(repo_id, revision))


@app.route("/api/v1/download/<path:repo_id>/info", methods=["GET"])
@require_permission("models:download")
def download_info(repo_id: str) -> Dict[str, Any]:
    """Información completa de descarga: archivos, URLs, snippets de código."""
    user_token = get_user_token() or ""
    dl = orch.get_download_manager(user_token)
    revision = request.args.get("revision", "main")
    return jsonify(dl.get_download_info(repo_id, revision))


@app.route("/api/v1/download/<path:repo_id>/snippets", methods=["GET"])
@require_permission("models:download")
def download_snippets(repo_id: str) -> Dict[str, Any]:
    """Genera snippets de código (transformers, diffusers, huggingface_hub)."""
    user_token = get_user_token() or ""
    dl = orch.get_download_manager(user_token)
    task = request.args.get("task", "text-generation")
    snippets = dl.get_all_snippets(repo_id, task)
    return jsonify({"snippets": [s.to_dict() for s in snippets]})


# ===========================================================================
# Sección 21 — Generador de Scripts de Fine-Tuning (LoRA/PEFT)
# ===========================================================================

@app.route("/api/v1/finetune/generate", methods=["POST"])
@require_permission("models:adapt")
def finetune_generate() -> Dict[str, Any]:
    """Genera script y notebook de fine-tuning LoRA/PEFT."""
    payload = request.get_json(force=True) or {}
    config = FineTuneConfig(
        base_model=payload.get("base_model", ""),
        dataset_id=payload.get("dataset_id", ""),
        output_dir=payload.get("output_dir", "./fine_tuned_model"),
        method=payload.get("method", "lora"),
        task=payload.get("task", "text-generation"),
        epochs=payload.get("epochs", 3),
        batch_size=payload.get("batch_size", 4),
        learning_rate=payload.get("learning_rate", 2e-4),
        lora_r=payload.get("lora_r", 16),
        lora_alpha=payload.get("lora_alpha", 32),
        push_to_hub=payload.get("push_to_hub", False),
        hub_repo_id=payload.get("hub_repo_id", ""),
    )
    if not config.base_model or not config.dataset_id:
        return jsonify({"error": "base_model and dataset_id are required"}), 400
    result = orch.script_generator.generate(config)
    result["billing_note"] = "GPU charges go to your Hugging Face account, not UTRON.AI"
    return jsonify(result)


# ===========================================================================
# Sección 22 — OAuth Login con Hugging Face
# ===========================================================================

@app.route("/api/v1/auth/oauth/login", methods=["GET"])
def oauth_login() -> Dict[str, Any]:
    """Inicia flujo OAuth: retorna URL de autorización de HF."""
    scopes = request.args.getlist("scope") or None
    redirect_uri = request.args.get("redirect_uri", "")
    result = orch.oauth.get_authorization_url(scopes=scopes, redirect_uri=redirect_uri or None)
    return jsonify(result)


@app.route("/api/v1/auth/oauth/callback", methods=["GET"])
def oauth_callback() -> Dict[str, Any]:
    """Callback de OAuth: intercambia code por access_token."""
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    if not code or not state:
        return jsonify({"error": "code and state parameters are required"}), 400
    result = orch.oauth.exchange_code(code, state)
    if not result.get("success"):
        return jsonify(result), 400
    user_info = result["user_info"]
    # Autenticar al usuario con el token OAuth obtenido
    success, session, error = auth.authenticate(user_info.access_token)
    if not success:
        # En modo mock el token OAuth puede no estar en MOCK_HF_USERS
        # Crear sesión directamente
        from hf_auth import UserSession, HFRole
        import hashlib
        token_hash = hashlib.sha256(user_info.access_token.encode()).hexdigest()[:16]
        session = UserSession(
            session_id=f"sess_{uuid.uuid4().hex[:12]}",
            hf_token=user_info.access_token,
            hf_username=user_info.hf_username,
            hf_name=user_info.hf_name,
            hf_email=user_info.hf_email,
            role=HFRole.USER,
            token_hash=token_hash,
        )
        auth._sessions[session.session_id] = session
        auth._token_to_session[token_hash] = session.session_id
    return jsonify({
        "success": True,
        "session": session.to_dict(),
        "user_info": user_info.to_dict(),
        "scopes_granted": user_info.scopes_granted,
        "message": f"Welcome {user_info.hf_username}! You are now logged into UTRON.AI via Hugging Face OAuth.",
    })


@app.route("/api/v1/auth/oauth/scopes", methods=["GET"])
def oauth_scopes() -> Dict[str, Any]:
    """Información sobre los scopes OAuth requeridos."""
    return jsonify(orch.oauth.get_scopes_info())


# ===========================================================================
# Sección 23 — Panel Interactivo de Modelos (6 funcionalidades)
# ===========================================================================

from hf_model_panel import (
    BenchmarkAnalyzer,
    K8sManifestGenerator,
    LicenseAnalyzer,
    LineageTracker,
    ModelPanel,
    PlaygroundFinder,
    QuantMode,
    ComputeMode,
    VRAMCalculator,
)

_model_panel = ModelPanel()


@app.route("/api/v1/panel/<path:model_id>", methods=["GET"])
@require_permission("catalog:browse")
def model_panel(model_id: str) -> Dict[str, Any]:
    """Panel completo de un modelo con las 6 secciones."""
    license_str = request.args.get("license", "")
    gated = request.args.get("gated", "false").lower() == "true"
    param_count = request.args.get("params", type=float)
    return jsonify(_model_panel.get_model_card_panel(
        model_id, license_str=license_str, gated=gated, param_count_b=param_count
    ))


# --- 1. Calculadora VRAM ---
@app.route("/api/v1/panel/<path:model_id>/vram", methods=["GET"])
@require_permission("catalog:browse")
def panel_vram(model_id: str) -> Dict[str, Any]:
    """Calcula VRAM estimada para todos los modos."""
    params = request.args.get("params", type=float)
    return jsonify(_model_panel.vram_calc.estimate_all_modes(model_id, params))


@app.route("/api/v1/panel/<path:model_id>/vram/estimate", methods=["POST"])
@require_permission("catalog:browse")
def panel_vram_estimate(model_id: str) -> Dict[str, Any]:
    """Calcula VRAM para un modo específico."""
    payload = request.get_json(silent=True) or {}
    quant = QuantMode(payload.get("quant_mode", "fp16"))
    compute = ComputeMode(payload.get("compute_mode", "inference"))
    params = payload.get("param_count_b")
    result = _model_panel.vram_calc.estimate(model_id, params, quant, compute)
    return jsonify(result.to_dict())


# --- 2. Playground ---
@app.route("/api/v1/panel/<path:model_id>/playground", methods=["GET"])
@require_permission("catalog:browse")
def panel_playground(model_id: str) -> Dict[str, Any]:
    """Retorna Spaces embebidos y widgets de inferencia."""
    return jsonify(_model_panel.playground.get_playground(model_id))


# --- 3. Licencia ---
@app.route("/api/v1/panel/<path:model_id>/license", methods=["GET"])
@require_permission("catalog:browse")
def panel_license(model_id: str) -> Dict[str, Any]:
    """Ficha de licencia y compatibilidad comercial."""
    license_str = request.args.get("license", "")
    gated = request.args.get("gated", "false").lower() == "true"
    info = _model_panel.license_analyzer.analyze(license_str, gated, model_id)
    return jsonify(info.to_dict())


# --- 4. K8s Manifest ---
@app.route("/api/v1/panel/<path:model_id>/k8s-manifest", methods=["GET"])
@require_permission("catalog:browse")
def panel_k8s(model_id: str) -> Dict[str, Any]:
    """Genera manifiesto YAML de Kubernetes para desplegar el modelo."""
    engine = request.args.get("engine", "vllm")
    gpu_type = request.args.get("gpu", "A10G")
    gpu_count = request.args.get("gpu_count", 1, type=int)
    namespace = request.args.get("namespace", "utron-ai")
    autoscale = request.args.get("autoscale", "true").lower() == "true"
    return jsonify(_model_panel.k8s_gen.generate_full_deploy(
        model_id, engine=engine, gpu_type=gpu_type,
        gpu_count=gpu_count, namespace=namespace, autoscale=autoscale
    ))


# --- 5. Benchmarks ---
@app.route("/api/v1/panel/<path:model_id>/benchmarks", methods=["GET"])
@require_permission("catalog:browse")
def panel_benchmarks(model_id: str) -> Dict[str, Any]:
    """Métricas de rendimiento real del modelo."""
    return jsonify(_model_panel.benchmarks.get_benchmarks(model_id).to_dict())


@app.route("/api/v1/panel/benchmarks/compare", methods=["POST"])
@require_permission("catalog:browse")
def panel_benchmarks_compare() -> Dict[str, Any]:
    """Compara benchmarks de múltiples modelos lado a lado."""
    payload = request.get_json(force=True) or {}
    model_ids = payload.get("model_ids", [])
    if not model_ids:
        return jsonify({"error": "model_ids list is required"}), 400
    return jsonify(_model_panel.benchmarks.compare_benchmarks(model_ids))


# --- 6. Linaje ---
@app.route("/api/v1/panel/<path:model_id>/lineage", methods=["GET"])
@require_permission("catalog:browse")
def panel_lineage(model_id: str) -> Dict[str, Any]:
    """Árbol de linaje del modelo (padre → derivados)."""
    return jsonify(_model_panel.lineage.get_lineage(model_id))


@app.route("/api/v1/panel/<path:model_id>/lineage/register", methods=["POST"])
@require_permission("models:push")
def panel_lineage_register(model_id: str) -> Dict[str, Any]:
    """Registra un modelo derivado (reentrenado via UTRON.AI)."""
    payload = request.get_json(force=True) or {}
    node = _model_panel.lineage.register_derivation(
        model_id=model_id,
        parent_model=payload.get("parent_model", ""),
        dataset_id=payload.get("dataset_id", ""),
        dataset_revision=payload.get("dataset_revision", ""),
        training_params=payload.get("training_params", {}),
        k8s_config=payload.get("k8s_config", {}),
        node_type=payload.get("node_type", "fine_tuned"),
        author=payload.get("author", ""),
    )
    return jsonify(node.to_dict())


@app.route("/api/v1/panel/<path:model_id>/training-history", methods=["GET"])
@require_permission("catalog:browse")
def panel_training_history(model_id: str) -> Dict[str, Any]:
    """Historial de reentrenamientos de un modelo."""
    return jsonify(_model_panel.lineage.get_training_history(model_id))


def run_server(port: int = 5320) -> None:
    app.run(host="0.0.0.0", port=port, debug=True)


# ===========================================================================
# Sección 24 — Pipeline K8s (6 pasos: auth → preflight → deploy → cache → exec → publish)
# ===========================================================================

from hf_k8s_pipeline import K8sPipeline, PKCEVerifier, JWTValidator

_k8s_pipeline = K8sPipeline(backend=os.environ.get("UC320_BACKEND", "mock"))


@app.route("/api/v1/pipeline/execute", methods=["POST"])
@require_permission("models:train")
def pipeline_execute() -> Dict[str, Any]:
    """Ejecuta el pipeline completo de 6 pasos en Kubernetes."""
    payload = request.get_json(force=True) or {}
    user_token = get_user_token() or ""
    model_id = payload.get("model_id", "")
    operation = payload.get("operation", "inference")
    dataset_id = payload.get("dataset_id", "")
    gpu_type = payload.get("gpu_type", "A10G")
    gpu_count = payload.get("gpu_count", 1)
    push_repo_id = payload.get("push_repo_id", "")
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    result = _k8s_pipeline.execute_pipeline(
        hf_token=user_token, model_id=model_id, operation=operation,
        dataset_id=dataset_id, gpu_type=gpu_type, gpu_count=gpu_count,
        push_repo_id=push_repo_id,
    )
    return jsonify(result)


# --- Paso 1: PKCE + JWT + Secret ---

@app.route("/api/v1/pipeline/pkce", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_pkce() -> Dict[str, Any]:
    """Genera par PKCE (code_verifier, code_challenge)."""
    return jsonify(PKCEVerifier.generate_pair())


@app.route("/api/v1/pipeline/jwt/validate", methods=["POST"])
@require_permission("catalog:browse")
def pipeline_jwt_validate() -> Dict[str, Any]:
    """Valida un token JWT de Hugging Face."""
    payload = request.get_json(force=True) or {}
    token = payload.get("token", "")
    validator = JWTValidator(backend=os.environ.get("UC320_BACKEND", "mock"))
    return jsonify(validator.validate(token))


@app.route("/api/v1/pipeline/secrets", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_secrets_list() -> Dict[str, Any]:
    """Lista Secrets efímeros activos."""
    return jsonify({"secrets": _k8s_pipeline.secrets.list_secrets()})


@app.route("/api/v1/pipeline/secrets", methods=["POST"])
@require_permission("models:train")
def pipeline_secret_create() -> Dict[str, Any]:
    """Crea un Secret efímero para el token del usuario."""
    user_token = get_user_token() or ""
    if not user_token:
        return jsonify({"error": "HF token required"}), 400
    secret = _k8s_pipeline.secrets.create_secret(user_token)
    return jsonify(secret.to_dict())


@app.route("/api/v1/pipeline/secrets/<secret_name>", methods=["DELETE"])
@require_permission("models:train")
def pipeline_secret_delete(secret_name: str) -> Dict[str, Any]:
    """Elimina un Secret efímero."""
    if _k8s_pipeline.secrets.delete_secret(secret_name):
        return jsonify({"deleted": True, "secret_name": secret_name})
    return jsonify({"deleted": False, "error": "Secret not found"}), 404


# --- Paso 2: Pre-flight check ---

@app.route("/api/v1/pipeline/preflight", methods=["POST"])
@require_permission("catalog:browse")
def pipeline_preflight() -> Dict[str, Any]:
    """Ejecuta pre-flight check: valida VRAM vs capacidad del clúster."""
    payload = request.get_json(force=True) or {}
    model_id = payload.get("model_id", "")
    vram_required = payload.get("vram_required_gb", 0)
    require_gpu = payload.get("require_gpu", True)
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    result = _k8s_pipeline.cluster.pre_flight_check(model_id, vram_required, require_gpu)
    return jsonify(result.to_dict())


@app.route("/api/v1/pipeline/cluster/nodes", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_cluster_nodes() -> Dict[str, Any]:
    """Lista los nodos del clúster K8s con sus recursos."""
    nodes = _k8s_pipeline.cluster.get_nodes()
    return jsonify({"nodes": [n.to_dict() for n in nodes]})


# --- Paso 3: Manifiestos ---

@app.route("/api/v1/pipeline/manifest/vllm", methods=["POST"])
@require_permission("catalog:browse")
def pipeline_manifest_vllm() -> Dict[str, Any]:
    """Genera manifiesto YAML de Deployment vLLM con env vars + PVC."""
    payload = request.get_json(force=True) or {}
    model_id = payload.get("model_id", "")
    secret_name = payload.get("secret_name", "hf-token")
    gpu_type = payload.get("gpu_type", "A10G")
    gpu_count = payload.get("gpu_count", 1)
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    yaml = _k8s_pipeline.manifests.build_vllm_deployment(
        model_id, secret_name, gpu_type, gpu_count
    )
    return jsonify({"yaml": yaml, "engine": "vllm", "env_vars": ["HF_TOKEN", "HF_HUB_ENABLE_HF_TRANSFER", "HF_HOME"]})


@app.route("/api/v1/pipeline/manifest/pytorchjob", methods=["POST"])
@require_permission("models:train")
def pipeline_manifest_pytorchjob() -> Dict[str, Any]:
    """Genera manifiesto YAML de PyTorchJob CRD para entrenamiento."""
    payload = request.get_json(force=True) or {}
    model_id = payload.get("model_id", "")
    dataset_id = payload.get("dataset_id", "")
    secret_name = payload.get("secret_name", "hf-token")
    gpu_type = payload.get("gpu_type", "A10G")
    gpu_count = payload.get("gpu_count", 1)
    epochs = payload.get("epochs", 3)
    method = payload.get("method", "lora")
    if not model_id or not dataset_id:
        return jsonify({"error": "model_id and dataset_id are required"}), 400
    yaml = _k8s_pipeline.manifests.build_pytorchjob_crd(
        model_id, dataset_id, secret_name, gpu_type, gpu_count, epochs=epochs, method=method
    )
    return jsonify({"yaml": yaml, "crd": "PyTorchJob", "engine": "pytorch"})


@app.route("/api/v1/pipeline/manifest/rayjob", methods=["POST"])
@require_permission("models:train")
def pipeline_manifest_rayjob() -> Dict[str, Any]:
    """Genera manifiesto YAML de RayJob CRD para entrenamiento distribuido."""
    payload = request.get_json(force=True) or {}
    model_id = payload.get("model_id", "")
    dataset_id = payload.get("dataset_id", "")
    secret_name = payload.get("secret_name", "hf-token")
    gpu_type = payload.get("gpu_type", "A10G")
    gpu_count = payload.get("gpu_count", 2)
    if not model_id or not dataset_id:
        return jsonify({"error": "model_id and dataset_id are required"}), 400
    yaml = _k8s_pipeline.manifests.build_rayjob_crd(
        model_id, dataset_id, secret_name, gpu_type, gpu_count
    )
    return jsonify({"yaml": yaml, "crd": "RayJob", "engine": "ray"})


@app.route("/api/v1/pipeline/manifest/pvc", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_manifest_pvc() -> Dict[str, Any]:
    """Genera manifiesto YAML de PVC ReadWriteMany para caché compartida."""
    size = request.args.get("size", "500Gi")
    storage_class = request.args.get("storage_class", "nfs-client")
    yaml = _k8s_pipeline.manifests.build_pvc(size=size, storage_class=storage_class)
    return jsonify({"yaml": yaml, "access_mode": "ReadWriteMany"})


@app.route("/api/v1/pipeline/apply", methods=["POST"])
@require_permission("models:train")
def pipeline_apply() -> Dict[str, Any]:
    """Aplica un manifiesto YAML al clúster K8s."""
    payload = request.get_json(force=True) or {}
    yaml = payload.get("yaml", "")
    namespace = payload.get("namespace", "utron-ai")
    if not yaml:
        return jsonify({"error": "yaml is required"}), 400
    result = _k8s_pipeline.k8s_api.apply_manifest(yaml, namespace)
    return jsonify(result)


# --- Paso 4: Caché ---

@app.route("/api/v1/pipeline/cache/check", methods=["POST"])
@require_permission("catalog:browse")
def pipeline_cache_check() -> Dict[str, Any]:
    """Verifica si un archivo está en caché (lookaside cache verification)."""
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    filename = payload.get("filename", "")
    sha256 = payload.get("sha256", "")
    if not repo_id or not filename:
        return jsonify({"error": "repo_id and filename are required"}), 400
    return jsonify(_k8s_pipeline.cache.check_cache(repo_id, filename, sha256))


@app.route("/api/v1/pipeline/cache", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_cache_list() -> Dict[str, Any]:
    """Lista archivos en caché del PVC compartido."""
    return jsonify({"cache": _k8s_pipeline.cache.list_cache(), "stats": _k8s_pipeline.cache.cache_stats()})


@app.route("/api/v1/pipeline/cache/prefetch", methods=["POST"])
@require_permission("models:download")
def pipeline_cache_prefetch() -> Dict[str, Any]:
    """Pre-descarga archivos al caché PVC (descarga paralela via CDN)."""
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    files = payload.get("files", [])
    if not repo_id or not files:
        return jsonify({"error": "repo_id and files are required"}), 400
    return jsonify(_k8s_pipeline.cache.prefetch_model(repo_id, [(f["filename"], f.get("sha256", ""), f.get("size_bytes", 0)) for f in files]))


# --- Paso 5: Métricas ---

@app.route("/api/v1/pipeline/jobs", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_jobs_list() -> Dict[str, Any]:
    """Lista jobs de K8s activos."""
    return jsonify({"jobs": _k8s_pipeline.k8s_api.list_jobs()})


@app.route("/api/v1/pipeline/jobs/<job_name>/metrics", methods=["GET"])
@require_permission("catalog:browse")
def pipeline_job_metrics(job_name: str) -> Dict[str, Any]:
    """Retorna métricas en tiempo real de un job (via WebSocket)."""
    limit = request.args.get("limit", 100, type=int)
    history = _k8s_pipeline.metrics.get_metrics_history(job_name, limit)
    return jsonify({"job_name": job_name, "metrics_history": history, "websocket_event": f"metrics:{job_name}"})


@app.route("/api/v1/pipeline/jobs/<job_name>/metrics/subscribe", methods=["POST"])
@require_permission("catalog:browse")
def pipeline_job_metrics_subscribe(job_name: str) -> Dict[str, Any]:
    """Suscribe a métricas en tiempo real via WebSocket."""
    sub_id = _k8s_pipeline.metrics.subscribe(job_name)
    return jsonify({"subscription_id": sub_id, "job_name": job_name, "websocket_channel": f"metrics:{job_name}"})


# --- Paso 6: Publicación + Limpieza ---

@app.route("/api/v1/pipeline/package", methods=["POST"])
@require_permission("models:adapt")
def pipeline_package() -> Dict[str, Any]:
    """Empaqueta pesos resultantes + model card."""
    payload = request.get_json(force=True) or {}
    model_id = payload.get("model_id", "")
    adapter_only = payload.get("adapter_only", True)
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    pkg = _k8s_pipeline.packager.package(model_id, adapter_only=adapter_only)
    return jsonify(pkg.to_dict())


@app.route("/api/v1/pipeline/publish", methods=["POST"])
@require_permission("models:push")
def pipeline_publish() -> Dict[str, Any]:
    """Publica modelo reentrenado al Hub via upload_folder()."""
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    folder_path = payload.get("folder_path", "/root/.cache/huggingface/outputs")
    if not repo_id:
        return jsonify({"error": "repo_id is required"}), 400
    user_token = get_user_token() or ""
    result = _k8s_pipeline.publisher.upload_folder(repo_id, folder_path, token=user_token)
    return jsonify(result)


@app.route("/api/v1/pipeline/cleanup", methods=["POST"])
@require_permission("models:train")
def pipeline_cleanup() -> Dict[str, Any]:
    """Garbage collection: limpia jobs completados y libera GPUs."""
    payload = request.get_json(force=True) or {}
    job_name = payload.get("job_name", "")
    secret_name = payload.get("secret_name", "")
    if job_name:
        return jsonify(_k8s_pipeline.gc.cleanup_job(job_name, secret_name))
    return jsonify(_k8s_pipeline.gc.cleanup_all_completed())


if __name__ == "__main__":
    run_server()
