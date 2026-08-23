"""UC-702 — Dashboards Grafana.

Reutiliza el patrón de helpers de UC-700/UC-701 y añade paneles para:
  - Overview consolidado del clúster (cluster-aware)
  - CPU, GPU, memoria, red y disco por nodo
  - Capacidad subutilizada disponible en el pool compartido
  - Interrupciones de instancias spot
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
        p.setdefault("fieldConfig", {"defaults": {}})
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
                "query": "label_values(uc702_cpu_usage_percent, node_id)",
                "refresh": 1,
                "multi": True,
                "includeAll": True,
            }
        ]
    }


def build_cluster_overview_dashboard() -> Dict[str, Any]:
    panels: List[Dict[str, Any]] = []
    y = 0
    panels.append(_row("Overview del Clúster", y))
    y += 1
    panels.append(
        _panel(
            "CPU disponible (núcleos)",
            "stat",
            "Prometheus",
            [_prom_target("uc702_pool_cpu_cores_available", "CPU disponible")],
            {"h": 4, "w": 6, "x": 0, "y": y},
        )
    )
    panels.append(
        _panel(
            "Memoria disponible (MB)",
            "stat",
            "Prometheus",
            [_prom_target("uc702_pool_memory_available_mb", "Memoria disponible")],
            {"h": 4, "w": 6, "x": 6, "y": y},
            field_config={"defaults": {"unit": "decmbytes"}},
        )
    )
    panels.append(
        _panel(
            "Disco disponible (GB)",
            "stat",
            "Prometheus",
            [_prom_target("uc702_pool_disk_available_gb", "Disco disponible")],
            {"h": 4, "w": 6, "x": 12, "y": y},
            field_config={"defaults": {"unit": "decgbytes"}},
        )
    )
    panels.append(
        _panel(
            "GPUs disponibles",
            "stat",
            "Prometheus",
            [_prom_target("uc702_pool_gpu_count_available", "GPUs disponibles")],
            {"h": 4, "w": 6, "x": 18, "y": y},
        )
    )

    y += 5
    panels.append(_row("Utilización por Nodo", y))
    y += 1
    panels.append(
        _panel(
            "CPU % por nodo",
            "timeseries",
            "Prometheus",
            [_prom_target("uc702_cpu_usage_percent{node_id=~\"$node\"}", "{{node_id}}")],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
        )
    )
    panels.append(
        _panel(
            "Núcleos CPU subutilizados disponibles",
            "timeseries",
            "Prometheus",
            [_prom_target("uc702_cpu_cores_available{node_id=~\"$node\"}", "{{node_id}}")],
            {"h": 8, "w": 12, "x": 12, "y": y},
        )
    )

    y += 9
    panels.append(
        _panel(
            "Memoria disponible por nodo (MB)",
            "timeseries",
            "Prometheus",
            [_prom_target("uc702_memory_available_mb{node_id=~\"$node\"}", "{{node_id}}")],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "decmbytes"}},
        )
    )
    panels.append(
        _panel(
            "Disco disponible por nodo (GB)",
            "timeseries",
            "Prometheus",
            [_prom_target("uc702_disk_available_gb{node_id=~\"$node\"}", "{{node_id}}")],
            {"h": 8, "w": 12, "x": 12, "y": y},
            field_config={"defaults": {"unit": "decgbytes"}},
        )
    )

    y += 9
    panels.append(_row("GPU y Red", y))
    y += 1
    panels.append(
        _panel(
            "Utilización de GPU",
            "timeseries",
            "Prometheus",
            [_prom_target("uc702_gpu_utilization_percent{node_id=~\"$node\"}", "{{node_id}}/{{gpu_index}}")],
            {"h": 8, "w": 12, "x": 0, "y": y},
            field_config={"defaults": {"unit": "percent", "min": 0, "max": 100}},
        )
    )
    panels.append(
        _panel(
            "Memoria libre de GPU (MB)",
            "timeseries",
            "Prometheus",
            [_prom_target("uc702_gpu_memory_free_mb{node_id=~\"$node\"}", "{{node_id}}/{{gpu_index}}")],
            {"h": 8, "w": 12, "x": 12, "y": y},
            field_config={"defaults": {"unit": "decmbytes"}},
        )
    )

    y += 9
    panels.append(
        _panel(
            "Red enviada/recibida (bps)",
            "timeseries",
            "Prometheus",
            [
                _prom_target("uc702_net_sent_bps{node_id=~\"$node\"}", "{{node_id}} tx"),
                _prom_target("uc702_net_recv_bps{node_id=~\"$node\"}", "{{node_id}} rx"),
            ],
            {"h": 8, "w": 24, "x": 0, "y": y},
            field_config={"defaults": {"unit": "bps"}},
        )
    )

    y += 9
    panels.append(_row("Interrupciones Spot", y))
    y += 1
    panels.append(
        _panel(
            "Interrupciones spot detectadas",
            "timeseries",
            "Prometheus",
            [_prom_target("sum by (node_id, provider) (increase(uc702_spot_interruptions_total[1h]))", "{{node_id}}/{{provider}}")],
            {"h": 8, "w": 24, "x": 0, "y": y},
        )
    )

    return {
        "title": "UC-702 Cluster Capacity Overview",
        "tags": ["uc702", "capacity", "spot", "cluster", "qbex"],
        "timezone": "browser",
        "refresh": "5s",
        "templating": _common_templating(),
        "panels": panels,
        "schemaVersion": 36,
        "version": 1,
    }


def build_node_detail_dashboard() -> Dict[str, Any]:
    panels: List[Dict[str, Any]] = []
    y = 0
    panels.append(_row("Detalle del Nodo Seleccionado", y))
    y += 1
    panels.append(
        _panel(
            "Estado de subutilización",
            "table",
            "Prometheus",
            [_prom_target("uc702_node_subutilized{node_id=~\"$node\"}", "{{node_id}}")],
            {"h": 8, "w": 24, "x": 0, "y": y},
        )
    )
    return {
        "title": "UC-702 Node Detail",
        "tags": ["uc702", "node", "qbex"],
        "timezone": "browser",
        "refresh": "5s",
        "templating": _common_templating(),
        "panels": panels,
        "schemaVersion": 36,
        "version": 1,
    }


DASHBOARD_BUILDERS = {
    "uc702-cluster-overview": build_cluster_overview_dashboard,
    "uc702-node-detail": build_node_detail_dashboard,
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
