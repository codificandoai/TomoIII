"""
UC-087 — API REST Flask para MLSecOps / Defense in Depth.

Expone el guardian de seguridad ML como servicio REST.
Puerto por defecto: 5087
"""

from flask import Flask, request, jsonify
from typing import Dict, Any, List

from models_087 import MLSecOpsConfig, DataPoint
from model_guardian import ModelSecurityGuardian

app = Flask(__name__)

_guardian: ModelSecurityGuardian = ModelSecurityGuardian()

INPUT_CARDS = {
    "POST /api/v1/validate": {
        "description": "Valida provenance, integridad, outliers y squeezing de un batch.",
        "parameters": {
            "data": {"type": "array", "required": True, "description": "Lista de {features: [...], label: int, metadata: {}}."},
            "expected_hash": {"type": "string", "required": False},
            "signature": {"type": "object", "required": False, "description": "{hash, signature, timestamp, algorithm}"},
            "source": {"type": "string", "required": False, "default": "unknown"},
            "allowed_sources": {"type": "array", "required": False},
        },
    },
    "POST /api/v1/train-candidate": {
        "description": "Entrena un modelo candidato en sandbox con adversarial augmentation.",
        "parameters": {
            "data": {"type": "array", "required": True},
            "attack": {"type": "string", "required": False, "default": "pgd"},
        },
    },
    "POST /api/v1/evaluate-robustness": {
        "description": "Red teaming: evalúa robustez con FGSM y PGD.",
        "parameters": {
            "data": {"type": "array", "required": True},
            "attack": {"type": "string", "required": False, "default": "pgd"},
        },
    },
    "POST /api/v1/detect-backdoors": {
        "description": "Detecta triggers/backdoors por slices y entropía.",
        "parameters": {
            "data": {"type": "array", "required": True},
            "baseline_metrics": {"type": "object", "required": False, "description": "{entropy: float, trigger_slice_acc: float, slice_feature_N_acc: float}"},
        },
    },
    "POST /api/v1/process-batch": {
        "description": "Flujo completo: validar, entrenar, evaluar robustez, detectar backdoors, decidir.",
        "parameters": {
            "data": {"type": "array", "required": True},
            "expected_hash": {"type": "string", "required": False},
            "signature": {"type": "object", "required": False},
            "source": {"type": "string", "required": False, "default": "unknown"},
            "allowed_sources": {"type": "array", "required": False},
            "baseline_metrics": {"type": "object", "required": False},
        },
    },
    "POST /api/v1/approve-canary": {
        "description": "Aprobación humana: promociona versión canary a producción.",
        "parameters": {
            "version_id": {"type": "string", "required": True},
        },
    },
    "POST /api/v1/rollback": {
        "description": "Revierte a una versión segura o a la última promocionada.",
        "parameters": {
            "version_id": {"type": "string", "required": False},
        },
    },
    "POST /api/v1/reset": {
        "description": "Reinicia el guardian con configuración opcional.",
        "parameters": {
            "config": {"type": "object", "required": False},
        },
    },
    "GET /api/v1/status": {
        "description": "Estado del guardian: versiones, alertas, config.",
        "parameters": {},
    },
    "GET /api/v1/schema": {
        "description": "INPUT/OUTPUT cards de la API.",
        "parameters": {},
    },
    "GET /metrics": {
        "description": "Métricas Prometheus del guardian.",
        "parameters": {},
    },
}

OUTPUT_CARDS = {
    "POST /api/v1/validate": {"fields": {"report_id": "string", "all_passed": "boolean", "provenance_checks": "array", "outlier_dropped": "int", "squeezed_differences": "int"}},
    "POST /api/v1/train-candidate": {"fields": {"trained": "boolean", "dim": "int", "weights_sample": "array"}},
    "POST /api/v1/evaluate-robustness": {"fields": {"clean_accuracy": "float", "adversarial_accuracy": "float", "robustness_gap": "float", "passed": "boolean", "attack_type": "string"}},
    "POST /api/v1/detect-backdoors": {"fields": {"entropy_alert": "boolean", "entropy_zscore": "float", "slice_alerts": "array", "suspicious_features": "array"}},
    "POST /api/v1/process-batch": {"fields": {"trace_id": "string", "decision": "object", "alerts": "array", "duration_ms": "float"}},
    "POST /api/v1/approve-canary": {"fields": {"status": "string", "version_id": "string", "promoted": "boolean"}},
    "POST /api/v1/rollback": {"fields": {"status": "string", "version_id": "string", "promoted": "boolean"}},
    "POST /api/v1/reset": {"fields": {"status": "string"}},
    "GET /api/v1/status": {"fields": {"config": "object", "versions": "array", "alerts": "object", "promoted_version": "object"}},
    "GET /api/v1/schema": {"fields": {"input_cards": "object", "output_cards": "object"}},
    "GET /metrics": {"fields": {"text": "string"}},
}


def _to_data_points(items: List[Dict[str, Any]]) -> List[DataPoint]:
    return [
        DataPoint(
            features=item.get("features", []),
            label=item.get("label"),
            metadata=item.get("metadata", {}),
        )
        for item in items
    ]


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "UC-087 MLSecOps Guardian"})


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "UC-087 — MLSecOps / Defense in Depth",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/api/v1/schema"},
            {"method": "POST", "path": "/api/v1/validate"},
            {"method": "POST", "path": "/api/v1/train-candidate"},
            {"method": "POST", "path": "/api/v1/evaluate-robustness"},
            {"method": "POST", "path": "/api/v1/detect-backdoors"},
            {"method": "POST", "path": "/api/v1/process-batch"},
            {"method": "POST", "path": "/api/v1/approve-canary"},
            {"method": "POST", "path": "/api/v1/rollback"},
            {"method": "POST", "path": "/api/v1/reset"},
            {"method": "GET", "path": "/api/v1/status"},
            {"method": "GET", "path": "/metrics"},
        ],
    })


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return jsonify({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True)
    points = _to_data_points(data.get("data", []))
    report = _guardian.validate_and_sanitize(
        points,
        expected_hash=data.get("expected_hash"),
        signature_envelope=data.get("signature"),
        source=data.get("source", "unknown"),
        allowed_sources=data.get("allowed_sources"),
    )
    return jsonify(report.to_dict())


@app.route("/api/v1/train-candidate", methods=["POST"])
def train_candidate():
    data = request.get_json(force=True)
    points = _to_data_points(data.get("data", []))
    candidate = _guardian.train_candidate(points, attack=data.get("attack", "pgd"))
    return jsonify({
        "trained": candidate.trained,
        "dim": candidate.dim,
        "weights_sample": candidate.weights[:3] if candidate.weights else [],
    })


@app.route("/api/v1/evaluate-robustness", methods=["POST"])
def evaluate_robustness():
    data = request.get_json(force=True)
    points = _to_data_points(data.get("data", []))
    candidate = _guardian.train_candidate(points, attack=data.get("attack", "pgd"))
    report = _guardian.evaluate_robustness(candidate, points, attacks=[data.get("attack", "pgd")])
    return jsonify(report.to_dict())


@app.route("/api/v1/detect-backdoors", methods=["POST"])
def detect_backdoors():
    data = request.get_json(force=True)
    points = _to_data_points(data.get("data", []))
    candidate = _guardian.train_candidate(points)
    baseline = data.get("baseline_metrics") or {"entropy": 0.5, "trigger_slice_acc": 0.85}
    report = _guardian.detect_backdoors(candidate, points, baseline)
    return jsonify(report.to_dict())


@app.route("/api/v1/process-batch", methods=["POST"])
def process_batch():
    data = request.get_json(force=True)
    if "data" not in data:
        return jsonify({"error": "data is required"}), 400
    points = _to_data_points(data["data"])
    result = _guardian.process_training_batch(
        points,
        expected_hash=data.get("expected_hash"),
        signature_envelope=data.get("signature"),
        source=data.get("source", "unknown"),
        allowed_sources=data.get("allowed_sources"),
        baseline_metrics=data.get("baseline_metrics"),
    )
    return jsonify(result.to_dict())


@app.route("/api/v1/approve-canary", methods=["POST"])
def approve_canary():
    data = request.get_json(force=True)
    version_id = data.get("version_id")
    if not version_id:
        return jsonify({"error": "version_id is required"}), 400
    promoted = _guardian.approve_canary(version_id)
    if promoted:
        return jsonify({"status": "approved", "version_id": version_id, "promoted": True})
    return jsonify({"status": "not_found", "version_id": version_id, "promoted": False}), 404


@app.route("/api/v1/rollback", methods=["POST"])
def rollback():
    data = request.get_json(force=True)
    result = _guardian.rollback(data.get("version_id"))
    if result:
        return jsonify({"status": "rolled_back", **result})
    return jsonify({"status": "no_safe_version"}), 409


@app.route("/api/v1/reset", methods=["POST"])
def reset():
    global _guardian
    data = request.get_json(force=True)
    config = None
    if data.get("config"):
        config = MLSecOpsConfig(**data["config"])
    _guardian = ModelSecurityGuardian(config=config)
    return jsonify({"status": "reset"})


@app.route("/api/v1/status", methods=["GET"])
def status():
    return jsonify(_guardian.get_status())


@app.route("/metrics", methods=["GET"])
def prometheus_metrics():
    return _guardian.observability.export_prometheus(), 200, {"Content-Type": "text/plain"}


def run_server(port: int = 5087) -> None:
    print(f"UC-087 MLSecOps Guardian API — http://localhost:{port}")
    print(f"  Schema: http://localhost:{port}/api/v1/schema")
    print(f"  Health: http://localhost:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run_server()
