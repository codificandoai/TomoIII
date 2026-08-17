"""UC-700 — Dashboards Grafana para autosanación avanzada del entrenamiento.

Reutiliza el helper de UC-141 y añade paneles específicos de Qbex.ai:
  - Nodos, GPUs, memoria, temperatura
  - Anomalías y severidad
  - Pipeline de autosanación (detección -> validación -> eficiencia)
  - Checkpoints y eficiencia post-recuperación
  - Escalamientos y auditoría
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
                "name": "node",
                "type": "query",
                "datasource": "Prometheus",
                "query": "label_values(uc700_anomaly_score, node_id)",
                "refresh": 1,
                "multi": True,
                "includeAll": True,
            },
            {
                "name": "job",
                "type": "query",
                "datasource": "Prometheus",
                "query": "label_values(uc700_efficiency_pct, job_id)",
                "refresh": 1,
                "multi": True,
                "includeAll": True,
            },
        ]
    }


def build_self_healing_overview_dashboard() -> Dict[str, Any]:
    panels: List[Dict[str, Any]] = []
    y = 0

    panels.append(_row("Estado del Sistema de Autosanación", y))
    y += 1
    panels.append(
        _panel(
            "Incidentes Activos",
            "stat",
            "Prometheus",
            [_prom_target("sum(uc700_incident_state{node_id=~\"$node\"})", "Active Incidents")],
            {"h": 4, "w": 6, "x": 0, "y": y},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 1, "color": "red"}]},
        )
    )
    panels.append(
        _panel(
            "Score de Anomalía Máximo",
            "stat",
            "Prometheus",
            [_prom_target("max(uc700_anomaly_score{node_id=~\"$node\"})", "Max Anomaly Score")],
            {"h": 4, "w": 6, "x": 6, "y": y},
            field_config={"defaults": {"unit": "percentunit", "min": 0, "max": 1}},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 0.75, "color": "yellow"}, {"value": 0.95, "color": "red"}]},
        )
    )
    panels.append(
        _panel(
            "Escalamientos a Operador",
            "stat",
            "Prometheus",
            [_prom_target("sum(increase(uc700_escalations_total[1h]))", "Escalations/h")],
            {"h": 4, "w": 6, "x": 12, "y": y},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 1, "color": "red"}]},
        )
    )
    panels.append(
        _panel(
            "Eficiencia Promedio Post-Recuperación",
            "stat",
            "Prometheus",
            [_prom_target("avg(uc700_efficiency_pct{job_id=~\"$job\"})", "Avg Efficiency %")],
            {"h": 4, "w": 6, "x": 18, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
            thresholds={"steps": [{"value": 0, "color": "red"}, {"value": 90, "color": "green"}]},
        )
    )

    y += 5
    panels.append(_row("Infraestructura GPU", y))
    y += 1
    panels.append(
        _panel(
            "Utilización y VRAM por Nodo",
            "timeseries",
            "Prometheus",
            [
                _prom_target("avg by (node_id) (uc700_device_state{node_id=~\"$node\"}) * 25", "Health Index"),
            ],
            {"h": 8, "w": 12, "x": 0, "y": y},
        )
    )
    panels.append(
        _panel(
            "Estado de Dispositivos",
            "table",
            "Prometheus",
            [_prom_target("uc700_device_state{node_id=~\"$node\"}", "{{node_id}} / {{device_id}}")],
            {"h": 8, "w": 12, "x": 12, "y": y},
        )
    )

    y += 9
    panels.append(_row("Pipeline de Autosanación", y))
    y += 1
    panels.append(
        _panel(
            "Incidentes por Severidad y Alcance",
            "timeseries",
            "Prometheus",
            [_prom_target("sum by (severity, scope) (rate(uc700_incidents_total[5m]))", "{{severity}} / {{scope}}")],
            {"h": 8, "w": 12, "x": 0, "y": y},
        )
    )
    panels.append(
        _panel(
            "Duración de Remediación por Estrategia",
            "timeseries",
            "Prometheus",
            [
                _prom_target(
                    "histogram_quantile(0.95, sum(rate(uc700_remediation_duration_seconds_bucket[5m])) by (le, strategy))",
                    "{{strategy}}",
                )
            ],
            {"h": 8, "w": 12, "x": 12, "y": y},
            field_config={"defaults": {"unit": "s"}},
        )
    )

    y += 9
    panels.append(_row("Validación y Eficiencia del Entrenamiento", y))
    y += 1
    panels.append(
        _panel(
            "Eficiencia por Job",
            "timeseries",
            "Prometheus",
            [_prom_target("uc700_efficiency_pct{job_id=~\"$job\"}", "{{job_id}}")],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
            thresholds={"steps": [{"value": 0, "color": "red"}, {"value": 90, "color": "green"}]},
        )
    )
    panels.append(
        _panel(
            "Validaciones Exitosas vs Fallidas",
            "timeseries",
            "Prometheus",
            [
                _prom_target('sum by (check) (rate(uc700_validation_checks_total{result="pass"}[5m]))', "pass {{check}}"),
                _prom_target('sum by (check) (rate(uc700_validation_checks_total{result="fail"}[5m]))', "fail {{check}}"),
            ],
            {"h": 8, "w": 12, "x": 12, "y": y},
        )
    )

    y += 9
    panels.append(_row("Logs y Auditoría", y))
    y += 1
    panels.append(
        _panel(
            "Logs del Orquestador de Autosanación",
            "logs",
            "Loki",
            [{"expr": '{app="uc700-self-healing"} |= `INC` or `remediation` or `escalation` | json', "refId": "A"}],
            {"h": 8, "w": 24, "x": 0, "y": y},
            options={"showLabels": True, "showTime": True, "wrapLogMessage": True},
        )
    )

    return {
        "title": "UC-700 Self-Healing Training Overview",
        "tags": ["uc700", "self-healing", "training", "gpu", "qbex"],
        "timezone": "browser",
        "refresh": "10s",
        "templating": _common_templating(),
        "panels": panels,
        "schemaVersion": 36,
        "version": 1,
    }


def build_training_health_dashboard() -> Dict[str, Any]:
    panels: List[Dict[str, Any]] = []
    y = 0
    panels.append(_row("Salud del Entrenamiento", y))
    y += 1
    panels.append(
        _panel(
            "Samples por Segundo",
            "timeseries",
            "Prometheus",
            [
                _prom_target(
                    'avg by (node_id) (DCGM_FI_DEV_GPU_UTIL{node_id=~"$node"}) * 1000',
                    "{{node_id}} samples/s proxy",
                )
            ],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "ops"}},
        )
    )
    panels.append(
        _panel(
            "Tiempo por Paso (ms)",
            "timeseries",
            "Prometheus",
            [
                _prom_target(
                    'avg by (job_id) (uc700_training_step_time_ms{job_id=~"$job"})',
                    "{{job_id}}",
                )
            ],
            {"h": 8, "w": 12, "x": 12, "y": y},
            field_config={"defaults": {"unit": "ms"}},
        )
    )

    y += 9
    panels.append(_row("Checkpoints", y))
    y += 1
    panels.append(
        _panel(
            "Edad del Último Checkpoint (s)",
            "timeseries",
            "Prometheus",
            [_prom_target('avg by (job_id) (uc700_checkpoint_age_seconds{job_id=~"$job"})', "{{job_id}}")],
            {"h": 8, "w": 24, "x": 0, "y": y},
            field_config={"defaults": {"unit": "s"}},
            thresholds={"steps": [{"value": 0, "color": "green"}, {"value": 1800, "color": "red"}]},
        )
    )

    return {
        "title": "UC-700 Training Health & Checkpoints",
        "tags": ["uc700", "training", "checkpoints", "qbex"],
        "timezone": "browser",
        "refresh": "10s",
        "templating": _common_templating(),
        "panels": panels,
        "schemaVersion": 36,
        "version": 1,
    }


DASHBOARD_BUILDERS = {
    "uc700-overview": build_self_healing_overview_dashboard,
    "uc700-training-health": build_training_health_dashboard,
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


def validate_dashboard(dashboard: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not dashboard.get("title"):
        errors.append("missing title")
    if "panels" not in dashboard or not isinstance(dashboard["panels"], list):
        errors.append("missing or invalid panels")
    elif not dashboard["panels"]:
        errors.append("empty panels")
    for idx, p in enumerate(dashboard.get("panels", [])):
        if p.get("type") != "row" and ("gridPos" not in p or "datasource" not in p):
            errors.append(f"panel {idx} missing gridPos or datasource")
    return errors
