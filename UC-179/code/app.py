"""
Codificando.AI - UC-179
API Flask que expone el pipeline de reentrenamiento continuo
(`pipeline_service.ContinuousLearningPipeline`): ingesta de datos,
disparo/ejecución de entrenamiento (completo o fine-tuning), validación,
despliegue, rollback, inferencia en producción y estado general.

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/data/ingest  (parámetros de ENTRADA)
────────────────────────────────────────────────────────────────────────
┌───────────┬─────────┬───────────┬─────────────────────────────────────┐
│ Campo      │ Tipo    │ Requerido │ Descripción                         │
├───────────┼─────────┼───────────┼─────────────────────────────────────┤
│ sources    │ array   │ sí        │ Lista de {"type", "data"}. type ∈   │
│            │         │           │ user_feedback|annotations|          │
│            │         │           │ external_api                        │
└───────────┴─────────┴───────────┴─────────────────────────────────────┘

CARD VIEW · POST /api/v1/data/ingest  (parámetros de SALIDA)
┌───────────┬─────────┬─────────────────────────────────────────────────┐
│ collected  │ int     │ Ítems normalizados desde las fuentes            │
│ filtered   │ int     │ Ítems que pasaron el filtro de calidad          │
│ stored     │ int     │ Ítems nuevos almacenados en la knowledge base   │
│ stored_ids │ array   │ IDs de los registros almacenados                │
└───────────┴─────────┴─────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/data/validate  (ENTRADA)
────────────────────────────────────────────────────────────────────────
┌────────────┬────────┬───────────┬───────────────────────────────────────┐
│ sample_ids  │ array   │ no        │ IDs a aprobar; si se omite, aprueba    │
│             │         │           │ todas las muestras pendientes          │
└────────────┴────────┴───────────┴───────────────────────────────────────┘

CARD VIEW · POST /api/v1/data/validate  (SALIDA)
┌─────────────────┬────────┬─────────────────────────────────────────────┐
│ validated_count  │ int    │ Cantidad de muestras aprobadas                │
│ sample_ids       │ array  │ IDs aprobados                                 │
└─────────────────┴────────┴─────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/training/run  (ENTRADA)
────────────────────────────────────────────────────────────────────────
┌───────────────┬────────┬───────────┬───────────────────────────────────┐
│ training_type  │ string │ no        │ full_retraining|fine_tuning; si se │
│                │        │           │ omite, se decide por umbrales      │
│ validate_after │ bool   │ no        │ Validar automáticamente (def: true)│
└───────────────┴────────┴───────────┴───────────────────────────────────┘

CARD VIEW · POST /api/v1/training/run  (SALIDA)
┌────────────────┬────────┬──────────────────────────────────────────────┐
│ status          │ string │ trained | skipped                            │
│ training_type   │ string │ Tipo de entrenamiento ejecutado               │
│ model_version   │ string │ Versión generada (si status=trained)          │
│ model_path      │ string │ Ruta del artefacto entrenado                  │
│ validation      │ object │ Resultado de `/models/validate` (si aplica)   │
└────────────────┴────────┴──────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/models/validate  (ENTRADA)
────────────────────────────────────────────────────────────────────────
┌───────────────┬────────┬───────────┬───────────────────────────────────┐
│ model_version  │ string │ no        │ Versión a validar; por defecto la  │
│                │        │           │ versión activa más reciente        │
└───────────────┴────────┴───────────┴───────────────────────────────────┘

CARD VIEW · POST /api/v1/models/validate  (SALIDA)
┌────────────────┬────────┬──────────────────────────────────────────────┐
│ model_version   │ string │ Versión evaluada                              │
│ metrics         │ object │ accuracy, f1_score, precision, recall,        │
│                 │        │ edge_cases, improvement (vs. baseline)        │
│ should_deploy   │ bool   │ Si cumple los umbrales de calidad             │
└────────────────┴────────┴──────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/models/deploy  (ENTRADA)
────────────────────────────────────────────────────────────────────────
┌───────────────┬────────┬───────────┬───────────────────────────────────┐
│ model_version  │ string │ sí        │ Versión a promover a producción    │
│ force          │ bool   │ no        │ Omitir re-validación (def: false)  │
└───────────────┴────────┴───────────┴───────────────────────────────────┘

CARD VIEW · POST /api/v1/models/deploy  (SALIDA)
┌────────────────┬────────┬──────────────────────────────────────────────┐
│ status          │ string │ deployed | rejected                           │
│ metadata        │ object │ Metadata del despliegue (si status=deployed)  │
│ validation      │ object │ Resultado de validación (si status=rejected)  │
└────────────────┴────────┴──────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────
CARD VIEW · POST /api/v1/predict  (ENTRADA)
────────────────────────────────────────────────────────────────────────
┌────────────────┬────────┬───────────┬─────────────────────────────────┐
│ text            │ string │ sí        │ Texto de entrada a clasificar    │
│ user_feedback   │ string │ no        │ Feedback opcional del usuario    │
└────────────────┴────────┴───────────┴─────────────────────────────────┘

CARD VIEW · POST /api/v1/predict  (SALIDA)
┌────────────────────┬────────┬──────────────────────────────────────────┐
│ prediction          │ string │ Etiqueta/respuesta predicha               │
│ confidence          │ float  │ Confianza (max. probabilidad), si aplica  │
│ processing_time_ms  │ int    │ Latencia de inferencia                    │
└────────────────────┴────────┴──────────────────────────────────────────┘

GET /api/v1/status → estado general del pipeline (última fecha de
entrenamiento, muestras nuevas, próximo disparador, modelo desplegado).
GET /api/v1/models/history → historial de versiones entrenadas.
POST /api/v1/models/rollback → revierte al respaldo anterior (o al
indicado por `backup_model_path`).
"""

import logging
from typing import Any, Dict

from flask import Flask, Response, jsonify, request

from logging_utils import configure_logging
from pipeline_service import ContinuousLearningPipeline

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
pipeline = ContinuousLearningPipeline()


@app.route("/health", methods=["GET"])
def health() -> Response:
    return jsonify({"status": "ok"}), 200


@app.route("/api/v1/data/ingest", methods=["POST"])
def ingest_data() -> Response:
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    sources = data.get("sources")
    if not sources or not isinstance(sources, list):
        return jsonify({"error": "El campo 'sources' (lista) es requerido"}), 400

    try:
        result = pipeline.ingest(sources)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result), 201


@app.route("/api/v1/data/validate", methods=["POST"])
def validate_data() -> Response:
    data = request.get_json(silent=True) or {}
    result = pipeline.approve_samples(sample_ids=data.get("sample_ids"))
    return jsonify(result), 200


@app.route("/api/v1/training/run", methods=["POST"])
def run_training() -> Response:
    data = request.get_json(silent=True) or {}
    training_type = data.get("training_type")
    if training_type is not None and training_type not in ("full_retraining", "fine_tuning"):
        return jsonify({"error": "training_type debe ser 'full_retraining' o 'fine_tuning'"}), 400

    result = pipeline.train(training_type=training_type, validate_after=bool(data.get("validate_after", True)))
    return jsonify(result), 201


@app.route("/api/v1/models/validate", methods=["POST"])
def validate_model_endpoint() -> Response:
    data = request.get_json(silent=True) or {}
    try:
        result = pipeline.validate(model_version=data.get("model_version"))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(result), 200


@app.route("/api/v1/models/deploy", methods=["POST"])
def deploy_model_endpoint() -> Response:
    data = request.get_json(silent=True) or {}
    model_version = data.get("model_version")
    if not model_version:
        return jsonify({"error": "El campo 'model_version' es requerido"}), 400

    try:
        result = pipeline.deploy(model_version, force=bool(data.get("force", False)))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    status_code = 201 if result["status"] == "deployed" else 409
    return jsonify(result), status_code


@app.route("/api/v1/models/rollback", methods=["POST"])
def rollback_model_endpoint() -> Response:
    data = request.get_json(silent=True) or {}
    try:
        result = pipeline.rollback(backup_model_path=data.get("backup_model_path"))
    except (RuntimeError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 404
    return jsonify(result), 200


@app.route("/api/v1/models/history", methods=["GET"])
def model_history() -> Response:
    limit = request.args.get("limit", default=20, type=int)
    return jsonify(pipeline.kb.get_model_history(limit=limit)), 200


@app.route("/api/v1/predict", methods=["POST"])
def predict() -> Response:
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if not text:
        return jsonify({"error": "El campo 'text' es requerido"}), 400

    try:
        result = pipeline.predict(text, user_feedback=data.get("user_feedback"))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify(result), 200


@app.route("/api/v1/status", methods=["GET"])
def status() -> Response:
    return jsonify(pipeline.status()), 200


@app.errorhandler(404)
def not_found(_e) -> Response:
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.errorhandler(405)
def method_not_allowed(_e) -> Response:
    return jsonify({"error": "Método no permitido"}), 405


if __name__ == "__main__":
    import os
    port = int(os.getenv("APP_PORT", "8003"))
    app.run(host="0.0.0.0", port=port, debug=False)
