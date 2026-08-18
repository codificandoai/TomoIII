"""UC-701 — Dashboards Grafana para riesgo financiero y predicción de declive.

Reutiliza el helper de UC-141 y añade paneles específicos de trackprice:
  - Score de riesgo financiero por empresa
  - Probabilidad de declive vs sostenimiento
  - Score proyectado a 1 año
  - Riesgo por categoría
  - Tendencias de indicadores clave
  - Cobertura de datos
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def _row(title: str, y: int) -> Dict[str, Any]:
    return {"title": title, "type": "row", "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}}


def _panel(
    title: str,
    ptype: str,
    datasource: str,
    targets: List[Dict[str, Any]],
    gridpos: Dict[str, int],
    field_config: Optional[Dict[str, Any]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    p: Dict[str, Any] = {
        "title": title,
        "type": ptype,
        "datasource": datasource,
        "targets": targets,
        "gridPos": gridpos,
    }
    if field_config:
        p["fieldConfig"] = field_config
    if thresholds:
        if "fieldConfig" not in p:
            p["fieldConfig"] = {"defaults": {}}
        p["fieldConfig"]["defaults"]["thresholds"] = thresholds
    if options:
        p["options"] = options
    return p


def _prom_target(expr: str, legend: str = "") -> Dict[str, Any]:
    return {"expr": expr, "legendFormat": legend}


def _common_templating() -> Dict[str, Any]:
    return {
        "list": [
            {
                "name": "empresa",
                "type": "query",
                "datasource": "Prometheus",
                "query": "label_values(uc701_score_riesgo_financiero, empresa)",
                "refresh": 1,
                "multi": True,
                "includeAll": True,
            }
        ]
    }


def build_financial_risk_dashboard() -> Dict[str, Any]:
    panels: List[Dict[str, Any]] = []
    y = 0

    panels.append(_row("Resumen de Riesgo Financiero", y))
    y += 1
    panels.append(
        _panel(
            "Score de Riesgo Promedio",
            "stat",
            "Prometheus",
            [_prom_target("avg(uc701_score_riesgo_financiero{empresa=~\"$empresa\"})", "Score")],
            {"h": 4, "w": 6, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 25, "color": "yellow"}, {"value": 50, "color": "orange"}, {"value": 75, "color": "red"}]},
        )
    )
    panels.append(
        _panel(
            "Score Proyectado a 1 Año",
            "stat",
            "Prometheus",
            [_prom_target("avg(uc701_score_proyectado_1y{empresa=~\"$empresa\"})", "Score 1y")],
            {"h": 4, "w": 6, "x": 6, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 25, "color": "yellow"}, {"value": 50, "color": "orange"}, {"value": 75, "color": "red"}]},
        )
    )
    panels.append(
        _panel(
            "Probabilidad de Declive",
            "stat",
            "Prometheus",
            [_prom_target("avg(uc701_probabilidad_declive_pct{empresa=~\"$empresa\"})", "% Declive")],
            {"h": 4, "w": 6, "x": 12, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 30, "color": "yellow"}, {"value": 50, "color": "orange"}, {"value": 70, "color": "red"}]},
        )
    )
    panels.append(
        _panel(
            "Probabilidad de Sostenimiento",
            "stat",
            "Prometheus",
            [_prom_target("avg(uc701_probabilidad_sostenimiento_pct{empresa=~\"$empresa\"})", "% Sostenimiento")],
            {"h": 4, "w": 6, "x": 18, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
            thresholds={"steps": [{"value": 0, "color": "red"}, {"value": 30, "color": "yellow"}, {"value": 50, "color": "green"}]},
        )
    )

    y += 5
    panels.append(_row("Riesgo por Categoría", y))
    y += 1
    panels.append(
        _panel(
            "Riesgo por Categoría",
            "barchart",
            "Prometheus",
            [_prom_target("avg by (categoria) (uc701_riesgo_categoria{empresa=~\"$empresa\"})", "{{categoria}}")],
            {"h": 8, "w": 24, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
        )
    )

    y += 9
    panels.append(_row("Tendencias de Indicadores Clave", y))
    y += 1
    panels.append(
        _panel(
            "Ingresos y EBIT (% variación)",
            "timeseries",
            "Prometheus",
            [
                _prom_target('uc701_indicador_valor{empresa=~"$empresa", indicador="Ingresos netos por ventas"}', "Ventas"),
                _prom_target('uc701_indicador_valor{empresa=~"$empresa", indicador="Ganancia operativa (EBIT)"}', "EBIT"),
            ],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent"}},
        )
    )
    panels.append(
        _panel(
            "Liquidez (Prueba Ácida y Coeficiente de Efectivo)",
            "timeseries",
            "Prometheus",
            [
                _prom_target('uc701_indicador_valor{empresa=~"$empresa", indicador="Prueba Ácida"}', "Prueba Ácida"),
                _prom_target('uc701_indicador_valor{empresa=~"$empresa", indicador="Coeficiente de Efectivo"}', "Coeficiente Efectivo"),
            ],
            {"h": 8, "w": 12, "x": 12, "y": y},
        )
    )

    y += 9
    panels.append(_row("Cobertura y Calidad de Datos", y))
    y += 1
    panels.append(
        _panel(
            "Cobertura de Datos (%)",
            "timeseries",
            "Prometheus",
            [_prom_target("avg(uc701_cobertura_datos_pct{empresa=~\"$empresa\"})", "Cobertura")],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
        )
    )
    panels.append(
        _panel(
            "Escenarios Esperados (Tabla)",
            "table",
            "Prometheus",
            [_prom_target('uc701_escenario_esperado_info{empresa=~"$empresa"}', "{{empresa}} — {{escenario}}")],
            {"h": 8, "w": 12, "x": 12, "y": y},
        )
    )

    return {
        "title": "UC-701 Financial Decline & Sustainability Risk",
        "tags": ["uc701", "trackprice", "financial", "risk", "forecasting"],
        "timezone": "browser",
        "refresh": "1m",
        "templating": _common_templating(),
        "panels": panels,
        "schemaVersion": 36,
        "version": 1,
    }


DASHBOARD_BUILDERS = {
    "uc701-financial-risk": build_financial_risk_dashboard,
}


def build_dashboard(name: str) -> Dict[str, Any]:
    builder = DASHBOARD_BUILDERS.get(name)
    if not builder:
        raise ValueError(f"dashboard {name} not found. Available: {', '.join(DASHBOARD_BUILDERS.keys())}")
    return builder()


def write_dashboards(output_dir: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    paths: List[str] = []
    for name in DASHBOARD_BUILDERS:
        path = os.path.join(output_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(build_dashboard(name), f, indent=2, ensure_ascii=False)
        paths.append(path)
    return paths
