"""UC-320 — API REST Flask para exponer el pipeline de Hugging Face + UC-315/317/324."""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Flask, jsonify, request

from orchestrator import UC320Orchestrator

app = Flask(__name__)
orch = UC320Orchestrator()

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


@app.route("/api/v1/schema", methods=["GET"])
def schema() -> Dict[str, Any]:
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/models", methods=["GET"])
def list_models() -> Dict[str, Any]:
    task = request.args.get("task")
    return jsonify({"models": orch.catalog.list_models(task=task)})


@app.route("/api/v1/templates", methods=["GET"])
def list_templates() -> Dict[str, Any]:
    return jsonify({"templates": orch.list_templates()})


@app.route("/api/v1/templates/<template_id>", methods=["GET"])
def get_template(template_id: str) -> Dict[str, Any]:
    t = orch.get_template(template_id)
    if not t:
        return jsonify({"error": f"Template {template_id} not found"}), 404
    return jsonify(t)


@app.route("/api/v1/sentiment", methods=["POST"])
def sentiment() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    ticker = payload.get("ticker")
    article = payload.get("article")
    if not ticker or not article:
        return jsonify({"error": "ticker and article are required"}), 400
    model_id = payload.get("model_id", "mock/sentiment-mock")
    result = orch.sentiment(ticker, article, model_id)
    return jsonify(result.to_dict())


@app.route("/api/v1/embedding", methods=["POST"])
def embedding() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    text = payload.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400
    model_id = payload.get("model_id", "sentence-transformers/all-MiniLM-L6-v2")
    result = orch.embedding(text, model_id)
    return jsonify(result.to_dict())


@app.route("/api/v1/classify", methods=["POST"])
def classify() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    text = payload.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400
    labels = payload.get("candidate_labels", [])
    model_id = payload.get("model_id", "facebook/bart-large-mnli")
    result = orch.classify(text, labels, model_id)
    return jsonify(result.to_dict())


@app.route("/api/v1/benchmark", methods=["POST"])
def benchmark() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    prompt = payload.get("prompt")
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    models = payload.get("models")
    result = orch.run_benchmark(prompt, models)
    return jsonify(result)


@app.route("/api/v1/training/submit", methods=["POST"])
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
def training_run() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    job_id = payload.get("job_id")
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    result = orch.run_training(job_id)
    return jsonify(result)


@app.route("/api/v1/training/promote", methods=["POST"])
def training_promote() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    job_id = payload.get("job_id")
    human_approved = payload.get("human_approved", False)
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400
    result = orch.promote_model(job_id, human_approved)
    return jsonify(result)


@app.route("/api/v1/training/jobs", methods=["GET"])
def training_jobs() -> Dict[str, Any]:
    return jsonify({"jobs": orch.training.list_jobs()})


@app.route("/api/v1/audit", methods=["GET"])
def audit() -> Dict[str, Any]:
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"audit_log": orch.gateway.get_audit_log(limit=limit)})


# ---------------------------------------------------------------------------
# HF Services endpoints
# ---------------------------------------------------------------------------
@app.route("/api/v1/hf/status", methods=["GET"])
def hf_status() -> Dict[str, Any]:
    return jsonify(orch.hf_status())


# --- Inference Endpoints ---
@app.route("/api/v1/endpoints", methods=["GET"])
def list_endpoints() -> Dict[str, Any]:
    return jsonify({"endpoints": orch.list_endpoints()})


@app.route("/api/v1/endpoints", methods=["POST"])
def create_endpoint() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    model_id = payload.get("model_id")
    if not name or not model_id:
        return jsonify({"error": "name and model_id are required"}), 400
    kwargs = {k: v for k, v in payload.items() if k not in ("name", "model_id")}
    result = orch.create_endpoint(name=name, model_id=model_id, **kwargs)
    return jsonify(result)


@app.route("/api/v1/endpoints/<endpoint_id>/health", methods=["GET"])
def endpoint_health(endpoint_id: str) -> Dict[str, Any]:
    return jsonify(orch.endpoint_health(endpoint_id))


@app.route("/api/v1/endpoints/<endpoint_id>/stop", methods=["POST"])
def stop_endpoint(endpoint_id: str) -> Dict[str, Any]:
    return jsonify(orch.stop_endpoint(endpoint_id))


@app.route("/api/v1/endpoints/<endpoint_id>", methods=["DELETE"])
def delete_endpoint(endpoint_id: str) -> Dict[str, Any]:
    return jsonify(orch.delete_endpoint(endpoint_id))


# --- Datasets ---
@app.route("/api/v1/datasets", methods=["GET"])
def list_datasets() -> Dict[str, Any]:
    return jsonify({"datasets": orch.list_datasets()})


@app.route("/api/v1/datasets/load", methods=["POST"])
def load_dataset() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    dataset_id = payload.get("dataset_id")
    if not dataset_id:
        return jsonify({"error": "dataset_id is required"}), 400
    result = orch.load_dataset(
        dataset_id,
        revision=payload.get("revision", "main"),
        split=payload.get("split", "train"),
        pii_checked=payload.get("pii_checked", False),
        contamination_checked=payload.get("contamination_checked", False),
    )
    return jsonify(result)


@app.route("/api/v1/datasets/validate", methods=["POST"])
def validate_dataset() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    return jsonify(orch.validate_dataset(
        payload.get("dataset_id", ""),
        payload.get("revision", "main"),
        payload.get("split", "train"),
    ))


@app.route("/api/v1/datasets/transform", methods=["POST"])
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
    result = orch.train_model(config, approved=payload.get("approved", True))
    return jsonify(result)


@app.route("/api/v1/trainer/jobs", methods=["GET"])
def trainer_jobs() -> Dict[str, Any]:
    return jsonify({"jobs": orch.list_trainer_jobs()})


# --- PEFT ---
@app.route("/api/v1/peft/adapters", methods=["GET"])
def list_peft() -> Dict[str, Any]:
    return jsonify({"adapters": orch.list_peft_adapters()})


@app.route("/api/v1/peft/adapters", methods=["POST"])
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
def save_peft(adapter_id: str) -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    if not repo_id:
        return jsonify({"error": "repo_id is required"}), 400
    return jsonify(orch.save_peft_adapter(adapter_id, repo_id))


# --- Evaluate ---
@app.route("/api/v1/evaluate/compute", methods=["POST"])
def evaluate_compute() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    metric_name = payload.get("metric_name")
    predictions = payload.get("predictions", [])
    references = payload.get("references", [])
    if not metric_name:
        return jsonify({"error": "metric_name is required"}), 400
    return jsonify(orch.compute_metrics(metric_name, predictions, references))


@app.route("/api/v1/evaluate/compare", methods=["POST"])
def evaluate_compare() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    return jsonify(orch.compare_models_metrics(
        payload.get("metric_name", ""),
        payload.get("candidates", {}),
    ))


@app.route("/api/v1/evaluate/results", methods=["GET"])
def evaluate_results() -> Dict[str, Any]:
    return jsonify({"results": orch.list_eval_results()})


# --- Spaces ---
@app.route("/api/v1/spaces", methods=["GET"])
def list_spaces() -> Dict[str, Any]:
    return jsonify({"spaces": orch.list_spaces()})


@app.route("/api/v1/spaces", methods=["POST"])
def create_space() -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
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
def stop_space(space_id: str) -> Dict[str, Any]:
    return jsonify(orch.stop_space(space_id))


@app.route("/api/v1/spaces/<space_id>", methods=["DELETE"])
def delete_space(space_id: str) -> Dict[str, Any]:
    return jsonify(orch.delete_space(space_id))


# --- Model Cards ---
@app.route("/api/v1/model-cards", methods=["GET"])
def list_model_cards() -> Dict[str, Any]:
    return jsonify({"model_cards": orch.list_model_cards()})


@app.route("/api/v1/model-cards", methods=["POST"])
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
def get_model_card(model_id: str) -> Dict[str, Any]:
    card = orch.get_model_card(model_id)
    if not card:
        return jsonify({"error": "model card not found"}), 404
    return jsonify(card)


@app.route("/api/v1/model-cards/<path:model_id>/markdown", methods=["GET"])
def get_model_card_md(model_id: str) -> Dict[str, Any]:
    md = orch.get_model_card_markdown(model_id)
    if not md:
        return jsonify({"error": "model card not found"}), 404
    return jsonify({"model_id": model_id, "markdown": md})


@app.route("/api/v1/model-cards/<path:model_id>/approve", methods=["POST"])
def approve_model_card(model_id: str) -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    return jsonify(orch.approve_model_card(
        model_id,
        payload.get("approved_by", ""),
        payload.get("red_team_passed", False),
    ))


@app.route("/api/v1/model-cards/<path:model_id>/push", methods=["POST"])
def push_model_card(model_id: str) -> Dict[str, Any]:
    payload = request.get_json(force=True) or {}
    repo_id = payload.get("repo_id", "")
    if not repo_id:
        return jsonify({"error": "repo_id is required"}), 400
    return jsonify(orch.push_model_card(model_id, repo_id))


def run_server(port: int = 5320) -> None:
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    run_server()
