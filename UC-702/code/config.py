"""UC-702 — Configuración global.

Umbrales de subutilización, intervalos de sondeo y parámetros de
notificación para el detector de interrupción de instancias spot.
Todos los valores pueden sobreescribirse mediante variables de entorno,
lo que facilita adaptar el mismo código a on-premise, nube o free-tier.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: Optional[List[str]] = None) -> List[str]:
    raw = os.environ.get(name)
    if not raw:
        return default or []
    return [v.strip() for v in raw.split(",") if v.strip()]


@dataclass
class UnderutilizationThresholds:
    """Umbrales usados para decidir si un recurso está subutilizado."""

    cpu_idle_pct_min: float = _env_float("UC702_CPU_IDLE_MIN", 40.0)
    memory_available_pct_min: float = _env_float("UC702_MEM_AVAILABLE_MIN", 30.0)
    gpu_idle_pct_min: float = _env_float("UC702_GPU_IDLE_MIN", 30.0)
    gpu_memory_free_pct_min: float = _env_float("UC702_GPU_MEM_FREE_MIN", 25.0)
    disk_available_pct_min: float = _env_float("UC702_DISK_AVAILABLE_MIN", 15.0)
    network_idle_pct_min: float = _env_float("UC702_NET_IDLE_MIN", 50.0)


@dataclass
class MonitorConfig:
    """Configuración del recolector de métricas y del agente de nodo."""

    poll_interval_seconds: float = _env_float("UC702_POLL_INTERVAL", 5.0)
    thresholds: UnderutilizationThresholds = field(default_factory=UnderutilizationThresholds)
    node_stale_after_seconds: float = _env_float("UC702_NODE_STALE_AFTER", 60.0)
    api_base_url: str = os.environ.get("UC702_API_BASE_URL", "http://127.0.0.1:5000")


@dataclass
class SpotWatcherConfig:
    """Configuración del vigilante de interrupción de instancias spot."""

    metadata_url: str = os.environ.get(
        "UC702_SPOT_METADATA_URL",
        "http://169.254.169.254/latest/meta-data/spot/instance-action",
    )
    token_url: str = os.environ.get(
        "UC702_IMDS_TOKEN_URL", "http://169.254.169.254/latest/api/token"
    )
    poll_interval_seconds: float = _env_float("UC702_SPOT_POLL_INTERVAL", 5.0)
    request_timeout_seconds: float = _env_float("UC702_SPOT_TIMEOUT", 2.0)
    use_imdsv2: bool = os.environ.get("UC702_USE_IMDSV2", "true").lower() != "false"
    sns_topic_arn: Optional[str] = os.environ.get("UC702_SNS_TOPIC_ARN")
    slack_webhook_url: Optional[str] = os.environ.get("UC702_SLACK_WEBHOOK_URL")
    generic_webhook_urls: List[str] = field(default_factory=lambda: _env_list("UC702_WEBHOOK_URLS"))
    checkpoint_script: Optional[str] = os.environ.get("UC702_CHECKPOINT_SCRIPT")
    cleanup_script: Optional[str] = os.environ.get("UC702_CLEANUP_SCRIPT")
    checkpoint_storage_path: str = os.environ.get(
        "UC702_CHECKPOINT_PATH", os.path.join(os.sep, "tmp", "uc702-checkpoints")
    )
    lead_time_seconds: float = _env_float("UC702_SPOT_LEAD_TIME", 120.0)


@dataclass
class APIConfig:
    port: int = _env_int("UC702_PORT", 5000)
    host: str = os.environ.get("UC702_HOST", "0.0.0.0")
