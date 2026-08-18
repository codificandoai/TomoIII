"""UC-701 — API REST Flask para análisis y predicción financiera.

Endpoints:
  GET  /health
  GET  /api/v1/schema
  POST /api/v1/analyze          -> análisis rule-based
  POST /api/v1/predict          -> análisis + proyección de declive/sostenimiento
  POST /api/v1/batch            -> procesar CSV/XLSX multiempresa
  POST /api/v1/ingest           -> ingesta de métricas para Prometheus
  GET  /api/v1/metrics          -> métricas Prometheus
  GET  /api/v1/dashboards       -> dashboards Grafana generados
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from core import analizar_empresa, ejecutar_pipeline, leer_datos
from forecasting import predecir
from grafana_dashboards import write_dashboards
from prometheus_metrics import UC701Metrics, CONTENT_TYPE_LATEST

app = Flask(__name__)
metrics = UC701Metrics()


# -----------------------------------------------------------------------------
# Card Views de esquema de API
# -----------------------------------------------------------------------------
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/analyze",
        "description": "Análisis financiero rule-based de una empresa.",
        "parameters": [
            {"name": "empresa", "type": "string", "required": True, "example": "Empresa S.A."},
            {"name": "cortes", "type": "list[object]", "required": True, "example": [{"fecha": "2024-12-31", "indicadores": {"Ingresos netos por ventas": -26.71}}]},
        ],
    },
    {
        "endpoint": "POST /api/v1/predict",
        "description": "Análisis + proyección de declive o sostenimiento financiero a futuro.",
        "parameters": [
            {"name": "empresa", "type": "string", "required": True, "example": "Empresa S.A."},
            {"name": "cortes", "type": "list[object]", "required": True, "example": [{"fecha": "2023-12-31", "indicadores": {}}, {"fecha": "2024-12-31", "indicadores": {}}]},
            {"name": "horizonte_anios", "type": "integer", "required": False, "example": 1},
        ],
    },
    {
        "endpoint": "POST /api/v1/batch",
        "description": "Procesa archivo CSV/Excel multiempresa y genera reportes.",
        "parameters": [
            {"name": "file", "type": "file", "required": True, "description": "CSV o Excel con datos financieros"},
            {"name": "hoja", "type": "string|int", "required": False, "example": "Datos"},
            {"name": "generar_pdf", "type": "boolean", "required": False, "example": True},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/analyze",
        "description": "Resultado del análisis financiero.",
        "fields": [
            {"name": "empresa", "type": "string"},
            {"name": "fecha_analisis", "type": "string"},
            {"name": "score_riesgo_financiero", "type": "float"},
            {"name": "nivel_riesgo", "type": "string"},
            {"name": "semaforo", "type": "string"},
            {"name": "diagnosticos", "type": "list"},
            {"name": "riesgo_por_categoria", "type": "object"},
            {"name": "tendencias", "type": "object"},
            {"name": "alertas_priorizadas", "type": "list"},
            {"name": "recomendaciones", "type": "list"},
        ],
    },
    {
        "endpoint": "POST /api/v1/predict",
        "description": "Predicción de declive o sostenimiento financiero.",
        "fields": [
            {"name": "score_riesgo_actual", "type": "float"},
            {"name": "score_proyectado_1y", "type": "float"},
            {"name": "probabilidad_declive_pct", "type": "float"},
            {"name": "probabilidad_sostenimiento_pct", "type": "float"},
            {"name": "escenario_esperado", "type": "string"},
            {"name": "nivel_riesgo_proyectado", "type": "string"},
            {"name": "proyecciones_por_indicador", "type": "object"},
            {"name": "indicadores_en_declive", "type": "list"},
        ],
    },
]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _ok(data: Any, status: int = 200):
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat(), "data": data}), status


def _err(message: str, status: int = 400):
    return jsonify({"status": "error", "message": message}), status


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc701-financial-predictor"})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


@app.route("/api/v1/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(silent=True)
    if not payload:
        return _err("Se requiere un JSON en el body.")
    try:
        resultado = analizar_empresa(payload)
        metrics.record_analysis(resultado)
        return _ok(resultado)
    except Exception as e:
        return _err(str(e), 500)


@app.route("/api/v1/predict", methods=["POST"])
def predict():
    payload = request.get_json(silent=True)
    if not payload:
        return _err("Se requiere un JSON en el body.")
    try:
        from core import estandarizar_datos
        import pandas as pd

        horizonte = int(payload.get("horizonte_anios", 1))
        resultado_analisis = analizar_empresa(payload)

        # Reconstruir historial a partir del payload para forecasting
        filas = []
        empresa = str(payload.get("empresa", "Empresa sin nombre")).strip()
        for corte in payload.get("cortes", []):
            fecha = pd.to_datetime(corte.get("fecha"), errors="coerce")
            for nombre, valor in corte.get("indicadores", {}).items():
                from core import canonizar_indicador, parsear_numero
                canonico = canonizar_indicador(nombre)
                if canonico:
                    filas.append({
                        "empresa": empresa,
                        "fecha": fecha,
                        "indicador": canonico,
                        "valor": parsear_numero(valor),
                        "unidad": None,
                    })
        historial = pd.DataFrame(filas)

        prediccion = predecir(historial, horizonte_anios=horizonte)
        prediccion["analisis_actual"] = resultado_analisis
        metrics.record_prediction(prediccion)
        return _ok(prediccion)
    except Exception as e:
        return _err(str(e), 500)


@app.route("/api/v1/batch", methods=["POST"])
def batch():
    if "file" not in request.files:
        return _err("Se requiere un archivo 'file'.")
    uploaded = request.files["file"]
    if uploaded.filename == "":
        return _err("Nombre de archivo vacío.")

    hoja = request.form.get("hoja", 0)
    if isinstance(hoja, str) and hoja.isdigit():
        hoja = int(hoja)
    generar_pdf = request.form.get("generar_pdf", "true").lower() == "true"

    suffix = Path(uploaded.filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name

    try:
        salida = os.path.join(tempfile.gettempdir(), "uc701_output")
        payload = ejecutar_pipeline(tmp_path, directorio_salida=salida, hoja=hoja, generar_pdf=generar_pdf)
        for r in payload.get("resultados", []):
            metrics.record_analysis(r)
        return _ok(payload)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@app.route("/api/v1/metrics", methods=["GET"])
def prometheus_metrics():
    return metrics.render(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/api/v1/dashboards", methods=["GET"])
def dashboards():
    output_dir = os.path.join(os.path.dirname(__file__), "dashboards")
    paths = write_dashboards(output_dir)
    return _ok({
        "dashboards": [
            {"name": "uc701-financial-risk", "title": "UC-701 Financial Decline & Sustainability Risk"},
        ],
        "paths": paths,
    })


def main():
    port = int(os.environ.get("UC701_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
