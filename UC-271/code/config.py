"""Configuración centralizada para UC-271 — Multi-Agent K8s con Seguridad y HPA."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class SecurityConfig:
    """Configuración de seguridad para el cluster."""
    enable_mtls: bool = _env_bool("UC271_MTLS_ENABLED", True)
    enable_network_policies: bool = _env_bool("UC271_NETPOL_ENABLED", True)
    enable_rbac: bool = _env_bool("UC271_RBAC_ENABLED", True)
    secret_rotation_interval_hours: int = _env_int("UC271_SECRET_ROTATION_HOURS", 24)
    min_tls_version: str = _env("UC271_MIN_TLS_VERSION", "1.3")
    allowed_namespaces: List[str] = field(default_factory=lambda: ["agents", "monitoring"])
    pod_security_standard: str = _env("UC271_POD_SECURITY", "restricted")


@dataclass
class HPAConfig:
    """Configuración del Horizontal Pod Autoscaler."""
    min_replicas: int = _env_int("UC271_HPA_MIN_REPLICAS", 1)
    max_replicas: int = _env_int("UC271_HPA_MAX_REPLICAS", 10)
    target_cpu_percent: int = _env_int("UC271_HPA_CPU_TARGET", 70)
    target_memory_percent: int = _env_int("UC271_HPA_MEMORY_TARGET", 80)
    scale_up_cooldown_sec: int = _env_int("UC271_HPA_SCALEUP_COOLDOWN", 60)
    scale_down_cooldown_sec: int = _env_int("UC271_HPA_SCALEDOWN_COOLDOWN", 300)
    custom_metric_name: str = _env("UC271_HPA_CUSTOM_METRIC", "agent_queue_depth")
    custom_metric_target: int = _env_int("UC271_HPA_CUSTOM_METRIC_TARGET", 5)


@dataclass
class AgentConfig:
    """Configuración de un agente worker."""
    name: str = "worker"
    image: str = _env("UC271_AGENT_IMAGE", "ghcr.io/codificandoai/agent:latest")
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
    service_account: str = ""
    replicas: int = 1


@dataclass
class AppConfig:
    """Configuración principal de la aplicación."""
    port: int = _env_int("UC271_PORT", 5271)
    debug: bool = _env_bool("UC271_DEBUG", False)
    namespace: str = _env("UC271_NAMESPACE", "agents")
    cluster_name: str = _env("UC271_CLUSTER_NAME", "multi-agent-cluster")
    security: SecurityConfig = field(default_factory=SecurityConfig)
    hpa: HPAConfig = field(default_factory=HPAConfig)
    observability_enabled: bool = _env_bool("UC271_OBSERVABILITY", True)


def get_config() -> AppConfig:
    return AppConfig()
