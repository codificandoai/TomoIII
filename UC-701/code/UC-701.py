"""
Codificando.AI
UC-701: trackprice predicción declive financiero y sostenimiento a futuro.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: ETL (batch-online-offline).
- cloudatasecure.com: Vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Este archivo es el punto de entrada CLI que expone:
  - análisis de una empresa por JSON
  - predicción de declive/sostenimiento a futuro
  - procesamiento batch CSV/Excel
  - generación de dashboards Grafana
  - inicio de la API REST Flask
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from api import app
from core import analizar_empresa, ejecutar_pipeline
from emis_scraper import EmisScraperError, scrape_multi_country, to_analyze_payload
from forecasting import predecir
from grafana_dashboards import write_dashboards


def _datos_ejemplo() -> dict:
    return {
        "empresa": "Empresa de ejemplo",
        "cortes": [
            {
                "fecha": "2023-12-31",
                "indicadores": {
                    "Ingresos netos por ventas": -10.0,
                    "Total Ingreso Operativo": -8.0,
                    "Ganancia operativa (EBIT)": -30.0,
                    "Activos Totales": -8.0,
                    "Total de patrimonio": -15.0,
                    "Margen Operacional": -4.0,
                    "Relación Deuda/Capital": 32.0,
                    "Prueba Ácida": 0.55,
                    "Coeficiente de Efectivo": 0.12,
                },
            },
            {
                "fecha": "2024-12-31",
                "indicadores": {
                    "Ingresos netos por ventas": -26.71,
                    "Total Ingreso Operativo": -26.59,
                    "Ganancia operativa (EBIT)": -90.97,
                    "Ganancia (Pérdida) Neta": "N/D",
                    "Activos Totales": -22.95,
                    "Total de patrimonio": -57.93,
                    "Margen Operacional": -11.32,
                    "Margen Neto": "N/D",
                    "Rendimiento Sobre El Patrimonio (ROE)": "N/D",
                    "Relación Deuda/Capital": 37.68,
                    "Prueba Ácida": 0.32,
                    "Coeficiente de Efectivo": -0.08,
                },
            },
        ],
    }


def cmd_analyze(args: argparse.Namespace) -> int:
    datos = _datos_ejemplo() if args.ejemplo else json.loads(args.datos or "{}")
    resultado = analizar_empresa(datos)
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    import pandas as pd
    from core import canonizar_indicador, parsear_numero

    datos = _datos_ejemplo() if args.ejemplo else json.loads(args.datos or "{}")
    filas = []
    empresa = str(datos.get("empresa", "Empresa sin nombre")).strip()
    for corte in datos.get("cortes", []):
        fecha = pd.to_datetime(corte.get("fecha"), errors="coerce")
        for nombre, valor in corte.get("indicadores", {}).items():
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
    prediccion = predecir(historial, horizonte_anios=args.horizonte)
    prediccion["analisis_actual"] = analizar_empresa(datos)
    print(json.dumps(prediccion, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    if not os.path.exists(args.archivo):
        print(f"Archivo no encontrado: {args.archivo}", file=sys.stderr)
        return 1
    payload = ejecutar_pipeline(
        ruta_entrada=args.archivo,
        directorio_salida=args.salida,
        hoja=args.hoja,
        generar_pdf=args.pdf,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_analyze_from_emis(args: argparse.Namespace) -> int:
    try:
        preferred = [args.pais.upper(), None] if args.pais else None
        scrape_result = scrape_multi_country(args.empresa, preferred_countries=preferred)
        payload = to_analyze_payload(scrape_result, fecha_corte=args.fecha)
        resultado = analizar_empresa(payload)
        print(json.dumps({
            "empresa": scrape_result["empresa"],
            "pais": scrape_result["pais"],
            "url_emis": scrape_result["url"],
            "moneda": scrape_result["moneda"],
            "indicadores_extraidos": scrape_result["indicadores"],
            "analisis": resultado,
        }, ensure_ascii=False, indent=2, default=str))
        return 0
    except EmisScraperError as e:
        print(f"Error EMIS: {e}", file=sys.stderr)
        return 1


def cmd_predict_from_emis(args: argparse.Namespace) -> int:
    import pandas as pd
    from core import canonizar_indicador, parsear_numero

    try:
        preferred = [args.pais.upper(), None] if args.pais else None
        scrape_result = scrape_multi_country(args.empresa, preferred_countries=preferred)
        payload = to_analyze_payload(scrape_result, fecha_corte=args.fecha)
        resultado = analizar_empresa(payload)

        filas = []
        for corte in payload.get("cortes", []):
            fecha = pd.to_datetime(corte.get("fecha"), errors="coerce")
            for nombre, valor in corte.get("indicadores", {}).items():
                canonico = canonizar_indicador(nombre)
                if canonico:
                    filas.append({
                        "empresa": scrape_result["empresa"],
                        "fecha": fecha,
                        "indicador": canonico,
                        "valor": parsear_numero(valor),
                        "unidad": None,
                    })
        historial = pd.DataFrame(filas)
        prediccion = predecir(historial, horizonte_anios=args.horizonte)
        prediccion["analisis_actual"] = resultado

        print(json.dumps({
            "empresa": scrape_result["empresa"],
            "pais": scrape_result["pais"],
            "url_emis": scrape_result["url"],
            "moneda": scrape_result["moneda"],
            "indicadores_extraidos": scrape_result["indicadores"],
            "analisis": resultado,
            "prediccion": prediccion,
        }, ensure_ascii=False, indent=2, default=str))
        return 0
    except EmisScraperError as e:
        print(f"Error EMIS: {e}", file=sys.stderr)
        return 1


def cmd_dashboards(_args: argparse.Namespace) -> int:
    output_dir = os.path.join(os.path.dirname(__file__), "dashboards")
    paths = write_dashboards(output_dir)
    print("Dashboards generados:")
    for p in paths:
        print(f"  - {p}")
    return 0


def cmd_api(_args: argparse.Namespace) -> int:
    port = int(os.environ.get("UC701_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-701 Financial Decline Predictor CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Analiza una empresa desde JSON")
    p_analyze.add_argument("--datos", type=str, default=None, help="JSON con datos de la empresa")
    p_analyze.add_argument("--ejemplo", action="store_true", help="Usar datos de ejemplo")
    p_analyze.set_defaults(func=cmd_analyze)

    p_predict = sub.add_parser("predict", help="Predice declive/sostenimiento financiero")
    p_predict.add_argument("--datos", type=str, default=None, help="JSON con datos de la empresa")
    p_predict.add_argument("--ejemplo", action="store_true", help="Usar datos de ejemplo")
    p_predict.add_argument("--horizonte", type=int, default=1, help="Horizonte de proyección en años")
    p_predict.set_defaults(func=cmd_predict)

    p_analyze_emis = sub.add_parser("analyze-from-emis", help="Scrapea EMIS y analiza")
    p_analyze_emis.add_argument("empresa", help="Nombre de la empresa")
    p_analyze_emis.add_argument("--pais", default=None, help="Código de país preferido (ej: CO)")
    p_analyze_emis.add_argument("--fecha", default=None, help="Fecha del corte (YYYY-MM-DD)")
    p_analyze_emis.set_defaults(func=cmd_analyze_from_emis)

    p_predict_emis = sub.add_parser("predict-from-emis", help="Scrapea EMIS y predice")
    p_predict_emis.add_argument("empresa", help="Nombre de la empresa")
    p_predict_emis.add_argument("--pais", default=None, help="Código de país preferido (ej: CO)")
    p_predict_emis.add_argument("--fecha", default=None, help="Fecha del corte (YYYY-MM-DD)")
    p_predict_emis.add_argument("--horizonte", type=int, default=1, help="Horizonte de proyección en años")
    p_predict_emis.set_defaults(func=cmd_predict_from_emis)

    p_batch = sub.add_parser("batch", help="Procesa CSV/Excel multiempresa")
    p_batch.add_argument("archivo", help="Ruta al archivo CSV/Excel")
    p_batch.add_argument("--salida", default="output_financiero", help="Directorio de salida")
    p_batch.add_argument("--hoja", default=0, help="Hoja del Excel")
    p_batch.add_argument("--pdf", action="store_true", help="Generar PDF (requiere weasyprint)")
    p_batch.set_defaults(func=cmd_batch)

    p_dash = sub.add_parser("dashboards", help="Genera dashboards de Grafana")
    p_dash.set_defaults(func=cmd_dashboards)

    p_api = sub.add_parser("api", help="Inicia la API REST Flask")
    p_api.set_defaults(func=cmd_api)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
