"""UC-702 — API REST Flask: capacidad de clúster subutilizada + spot watch.

Expone el pipeline completo: identificación de disponibilidad de CPU,
GPU, memoria y disco por nodo en tiempo real, sumarización a un pool
compartido, asignación de esa capacidad a aplicaciones/servicios y
detección/despacho de interrupciones de instancias spot. También sirve
el frontend unificado (dashboard web) que integra toda la
funcionalidad.

Endpoints:
  GET  /health
  GET  /api/v1/schema
  POST /api/v1/nodes/register
  GET  /api/v1/nodes
  GET  /api/v1/nodes/<node_id>
  DELETE /api/v1/nodes/<node_id>
  POST /api/v1/nodes/<node_id>/telemetry
  GET  /api/v1/cluster/summary
  POST /api/v1/pool/allocate
  POST /api/v1/pool/release
  GET  /api/v1/pool/allocations
  POST /api/v1/spot/events
  GET  /api/v1/spot/events
  POST /api/v1/spot/check
  GET  /api/v1/metrics
  GET  /api/v1/dashboards
  GET  /                       (frontend unificado)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Flask, jsonify, request, send_from_directory

from capacity_pool import CapacityPool, InsufficientCapacityError
from config import APIConfig, MonitorConfig, SpotWatcherConfig
from grafana_dashboards import DASHBOARD_BUILDERS, build_dashboard, write_dashboards
from models import NodeInfo, ProviderKind, ResourceDemand, ResourceSnapshot, SpotInterruptionEvent
from prometheus_metrics import CONTENT_TYPE_LATEST, UC702Metrics
from spot_watcher import AWSSpotWatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc702-api")

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")

pool = CapacityPool(config=MonitorConfig())
metrics = UC702Metrics()
_spot_events: List[SpotInterruptionEvent] = []


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _ok(data: Any, status: int = 200):
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}), status


def _err(message: str, status: int = 400):
    return jsonify({"status": "error", "message": message}), status


# ─────────────────────────────────────────────────────────────────────────────
# Card Views de esquema de API (entrada / salida)
# ─────────────────────────────────────────────────────────────────────────────
INPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "POST /api/v1/nodes/register",
        "description": "Registra o actualiza un nodo (server/nodo/rack) en el pool.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "node-macbook-01"},
            {"name": "hostname", "type": "string", "required": False, "example": "macbook-pro.local"},
            {"name": "platform", "type": "string", "required": False, "example": "macos", "enum": ["linux", "macos", "windows"]},
            {"name": "architecture", "type": "string", "required": False, "example": "arm64"},
            {"name": "provider", "type": "string", "required": False, "example": "on-premise", "enum": ["on-premise", "aws", "gcp", "azure"]},
            {"name": "lifecycle", "type": "string", "required": False, "example": "spot", "enum": ["on-demand", "spot", "free-tier", "reserved"]},
            {"name": "region", "type": "string", "required": False, "example": "us-east-1"},
            {"name": "zone", "type": "string", "required": False, "example": "us-east-1a"},
            {"name": "rack", "type": "string", "required": False, "example": "rack-07"},
            {"name": "site", "type": "string", "required": False, "example": "campus-a"},
            {"name": "tags", "type": "object", "required": False, "example": {"team": "ml-platform"}},
        ],
    },
    {
        "endpoint": "POST /api/v1/nodes/<node_id>/telemetry",
        "description": "Ingesta la foto instantánea de CPU, GPU, memoria, disco y red del nodo.",
        "parameters": [
            {"name": "cpu_percent", "type": "float", "required": True, "example": 12.5},
            {"name": "cpu_count_logical", "type": "int", "required": True, "example": 8},
            {"name": "cpu_count_physical", "type": "int", "required": False, "example": 4},
            {"name": "memory_total_mb", "type": "float", "required": True, "example": 16384.0},
            {"name": "memory_available_mb", "type": "float", "required": True, "example": 9000.0},
            {"name": "disk_total_gb", "type": "float", "required": True, "example": 512.0},
            {"name": "disk_free_gb", "type": "float", "required": True, "example": 300.0},
            {"name": "net_bytes_sent", "type": "int", "required": False, "example": 102400},
            {"name": "net_bytes_recv", "type": "int", "required": False, "example": 204800},
            {"name": "gpus", "type": "list[object]", "required": False, "example": [{"index": 0, "name": "NVIDIA A100", "utilization_pct": 5.0, "memory_total_mb": 40960, "memory_free_mb": 39000}]},
        ],
    },
    {
        "endpoint": "POST /api/v1/pool/allocate",
        "description": "Solicita capacidad subutilizada del pool para una aplicación/servicio.",
        "parameters": [
            {"name": "requester", "type": "string", "required": True, "example": "batch-inference-job-42"},
            {"name": "cpu_cores", "type": "float", "required": False, "example": 2.0},
            {"name": "memory_mb", "type": "float", "required": False, "example": 2048.0},
            {"name": "disk_gb", "type": "float", "required": False, "example": 10.0},
            {"name": "gpu_count", "type": "int", "required": False, "example": 1},
            {"name": "gpu_memory_mb", "type": "float", "required": False, "example": 8192.0},
            {"name": "preferred_site", "type": "string", "required": False, "example": "campus-a"},
        ],
    },
    {
        "endpoint": "POST /api/v1/pool/release",
        "description": "Libera una asignación previamente realizada, devolviendo la capacidad al pool.",
        "parameters": [
            {"name": "allocation_id", "type": "string", "required": True, "example": "b1f2c3d4-..."},
        ],
    },
    {
        "endpoint": "POST /api/v1/spot/check",
        "description": "Ejecuta una consulta puntual al endpoint de metadatos de interrupción spot (AWS) para un nodo.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "node-ec2-spot-01"},
        ],
    },
    {
        "endpoint": "POST /api/v1/spot/events",
        "description": "Reporta un evento de interrupción spot detectado por un agente de nodo.",
        "parameters": [
            {"name": "node_id", "type": "string", "required": True, "example": "node-ec2-spot-01"},
            {"name": "provider", "type": "string", "required": False, "example": "aws"},
            {"name": "action", "type": "string", "required": False, "example": "terminate"},
            {"name": "termination_time", "type": "string", "required": False, "example": "2026-08-21T12:00:00Z"},
        ],
    },
]

OUTPUT_CARDS: List[Dict[str, Any]] = [
    {
        "endpoint": "GET /api/v1/cluster/summary",
        "description": "Capacidad subutilizada disponible, sumarizada por clúster/sitio/rack.",
        "fields": [
            {"name": "nodes_total", "type": "int"},
            {"name": "nodes_active", "type": "int"},
            {"name": "nodes_subutilized", "type": "int"},
            {"name": "capacity_available", "type": "object", "note": "cpu_cores, memory_mb, disk_gb, gpu_count, gpu_memory_mb"},
            {"name": "by_site", "type": "object"},
            {"name": "by_rack", "type": "object"},
        ],
    },
    {
        "endpoint": "GET /api/v1/nodes/<node_id>",
        "description": "Estado del nodo: telemetría en tiempo real y capacidad disponible.",
        "fields": [
            {"name": "node_id", "type": "string"},
            {"name": "platform", "type": "string"},
            {"name": "provider", "type": "string"},
            {"name": "lifecycle", "type": "string"},
            {"name": "last_seen", "type": "string"},
            {"name": "stale", "type": "boolean"},
            {"name": "snapshot", "type": "object"},
            {"name": "available_capacity", "type": "object"},
        ],
    },
    {
        "endpoint": "POST /api/v1/pool/allocate",
        "description": "Asignación resuelta contra el nodo con mejor ajuste.",
        "fields": [
            {"name": "allocation_id", "type": "string"},
            {"name": "node_id", "type": "string"},
            {"name": "cpu_cores", "type": "float"},
            {"name": "memory_mb", "type": "float"},
            {"name": "disk_gb", "type": "float"},
            {"name": "gpu_count", "type": "int"},
            {"name": "gpu_memory_mb", "type": "float"},
            {"name": "created_at", "type": "string"},
        ],
    },
    {
        "endpoint": "POST /api/v1/spot/check",
        "description": "Resultado de la vigilancia de interrupción spot y acciones disparadas.",
        "fields": [
            {"name": "interrupted", "type": "boolean"},
            {"name": "event", "type": "object"},
            {"name": "notifications_delivered", "type": "list[string]"},
            {"name": "checkpoint", "type": "object"},
        ],
    },
    {
        "endpoint": "GET /api/v1/metrics",
        "description": "Métricas Prometheus para scraping.",
        "fields": [{"name": "content", "type": "text/plain", "note": "Expone uc702_* metrics"}],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — salud y esquema
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return _ok({"service": "uc702-capacity-pool", "nodes_registered": len(pool.list_nodes())})


@app.route("/api/v1/schema", methods=["GET"])
def schema():
    return _ok({"input_cards": INPUT_CARDS, "output_cards": OUTPUT_CARDS})


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — nodos y telemetría
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/v1/nodes/register", methods=["POST"])
def register_node():
    payload = request.get_json(silent=True) or {}
    if not payload.get("node_id"):
        return _err("node_id is required")
    try:
        info = NodeInfo.from_dict(payload)
    except (KeyError, TypeError) as exc:
        return _err(f"payload inválido: {exc}")
    record = pool.register_node(info)
    return _ok(record.to_dict())


@app.route("/api/v1/nodes", methods=["GET"])
def list_nodes():
    now = datetime.now(timezone.utc)
    stale_after = pool.config.node_stale_after_seconds
    return _ok([r.to_dict(now, stale_after) for r in pool.list_nodes()])


@app.route("/api/v1/nodes/<node_id>", methods=["GET"])
def get_node(node_id: str):
    record = pool.get_node(node_id)
    if not record:
        return _err(f"node {node_id} not found", 404)
    now = datetime.now(timezone.utc)
    return _ok(record.to_dict(now, pool.config.node_stale_after_seconds))


@app.route("/api/v1/nodes/<node_id>", methods=["DELETE"])
def delete_node(node_id: str):
    removed = pool.remove_node(node_id)
    if not removed:
        return _err(f"node {node_id} not found", 404)
    return _ok({"node_id": node_id, "removed": True})


@app.route("/api/v1/nodes/<node_id>/telemetry", methods=["POST"])
def ingest_telemetry(node_id: str):
    payload = request.get_json(silent=True) or {}
    if not pool.get_node(node_id):
        # auto-registro mínimo si el agente aún no llamó a /register
        pool.register_node(NodeInfo.from_dict({"node_id": node_id}))
    try:
        snapshot = ResourceSnapshot.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return _err(f"snapshot inválido: {exc}")

    capacity = pool.ingest_snapshot(node_id, snapshot)
    metrics.record_node_snapshot(node_id, snapshot.to_dict(), capacity.to_dict())
    return _ok({"node_id": node_id, "snapshot": snapshot.to_dict(), "available_capacity": capacity.to_dict()})


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — pool compartido de capacidad
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/v1/cluster/summary", methods=["GET"])
def cluster_summary():
    summary = pool.cluster_summary()
    metrics.record_pool_summary(summary)
    return _ok(summary)


@app.route("/api/v1/pool/allocate", methods=["POST"])
def allocate():
    payload = request.get_json(silent=True) or {}
    if not payload.get("requester"):
        return _err("requester is required")
    demand = ResourceDemand(
        requester=payload["requester"],
        cpu_cores=float(payload.get("cpu_cores", 0.0)),
        memory_mb=float(payload.get("memory_mb", 0.0)),
        disk_gb=float(payload.get("disk_gb", 0.0)),
        gpu_count=int(payload.get("gpu_count", 0)),
        gpu_memory_mb=float(payload.get("gpu_memory_mb", 0.0)),
        preferred_site=payload.get("preferred_site"),
    )
    try:
        allocation = pool.allocate(demand)
    except InsufficientCapacityError as exc:
        return _err(str(exc), 409)
    return _ok(allocation.to_dict())


@app.route("/api/v1/pool/release", methods=["POST"])
def release():
    payload = request.get_json(silent=True) or {}
    allocation_id = payload.get("allocation_id")
    if not allocation_id:
        return _err("allocation_id is required")
    try:
        allocation = pool.release(allocation_id)
    except KeyError as exc:
        return _err(str(exc), 404)
    return _ok(allocation.to_dict())


@app.route("/api/v1/pool/allocations", methods=["GET"])
def list_allocations():
    requester = request.args.get("requester")
    return _ok([a.to_dict() for a in pool.list_allocations(requester)])


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — interrupción de instancias spot
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/v1/spot/check", methods=["POST"])
def spot_check():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id")
    if not node_id:
        return _err("node_id is required")
    watcher = AWSSpotWatcher(node_id, config=SpotWatcherConfig())
    event = watcher.check_once()
    if not event:
        return _ok({"interrupted": False, "node_id": node_id})
    result = watcher.handle_event(event)
    _spot_events.append(event)
    metrics.record_spot_interruption(node_id, event.provider.value)
    return _ok({"interrupted": True, **result})


@app.route("/api/v1/spot/events", methods=["POST"])
def report_spot_event():
    payload = request.get_json(silent=True) or {}
    node_id = payload.get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        provider = ProviderKind(payload.get("provider", "aws"))
    except ValueError:
        provider = ProviderKind.UNKNOWN
    event = SpotInterruptionEvent(
        node_id=node_id,
        provider=provider,
        detected_at=datetime.now(timezone.utc),
        action=payload.get("action", "terminate"),
        termination_time=payload.get("termination_time"),
        lead_time_seconds=payload.get("lead_time_seconds"),
        raw=payload.get("raw"),
    )
    _spot_events.append(event)
    metrics.record_spot_interruption(node_id, provider.value)
    return _ok(event.to_dict())


@app.route("/api/v1/spot/events", methods=["GET"])
def list_spot_events():
    return _ok([e.to_dict() for e in _spot_events])


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints — métricas y dashboards
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/v1/metrics", methods=["GET"])
def prometheus_metrics_endpoint():
    return metrics.render(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/api/v1/dashboards", methods=["GET"])
def list_dashboards():
    return _ok({name: build_dashboard(name) for name in DASHBOARD_BUILDERS})


@app.route("/api/v1/dashboards/<name>", methods=["GET"])
def get_dashboard(name: str):
    try:
        return _ok(build_dashboard(name))
    except ValueError as exc:
        return _err(str(exc), 404)


# ─────────────────────────────────────────────────────────────────────────────
# Frontend unificado
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def frontend_index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/<path:filename>", methods=["GET"])
def frontend_assets(filename: str):
    if os.path.exists(os.path.join(WEB_DIR, filename)):
        return send_from_directory(WEB_DIR, filename)
    return _err("not found", 404)
