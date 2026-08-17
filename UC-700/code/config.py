"""UC-700 — Configuración central del sistema de autosanación avanzada.

Qbex.ai autosanación avanzada del entrenamiento distribuido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


class HealthState:
    """Estados explícitos de salud de cualquier componente del grafo."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    SUSPECTED = "SUSPECTED"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    VALIDATING = "VALIDATING"
    AVAILABLE = "AVAILABLE"


class FailureClass:
    """Tipos de fallo que el motor de diagnóstico debe distinguir."""

    HARDWARE = "HARDWARE"
    TRANSIENT = "TRANSIENT"
    DRIVER = "DRIVER"
    NETWORK = "NETWORK"
    THERMAL = "THERMAL"
    STORAGE = "STORAGE"
    CONTAINER = "CONTAINER"
    TRAINING_CODE = "TRAINING_CODE"
    MODEL_DEGRADATION = "MODEL_DEGRADATION"
    DATA_ISSUE = "DATA_ISSUE"
    UNKNOWN = "UNKNOWN"


class SeverityLevel:
    """Niveles de severidad S0..S4."""

    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


class RemediationStrategy:
    """Estrategias de continuidad del entrenamiento."""

    NONE = "NONE"
    ADJUST_LOAD = "ADJUST_LOAD"
    QUARANTINE_DEVICE = "QUARANTINE_DEVICE"
    ELASTIC_TRAINING = "ELASTIC_TRAINING"
    REPLACE_NODE = "REPLACE_NODE"
    CHECKPOINT_RECOVERY = "CHECKPOINT_RECOVERY"
    DOMAIN_FAILOVER = "DOMAIN_FAILOVER"


@dataclass
class Thresholds:
    """Umbrales operativos del sistema."""

    gpu_temperature_c: float = 85.0
    gpu_vram_used_pct: float = 95.0
    gpu_util_low_pct: float = 10.0
    gpu_memory_error_rate: float = 1e-6
    network_packet_loss_pct: float = 1.0
    thermal_throttle: bool = True
    anomaly_score: float = 0.75
    efficiency_degradation_pct: float = 10.0
    allowed_throughput_drop_pct: float = 5.0
    checkpoint_max_age_min: float = 30.0
    validation_loss_delta_pct: float = 5.0
    validation_samples_per_sec_delta_pct: float = 10.0


@dataclass
class AgentConfig:
    """Configuración del set de agentes AI."""

    thresholds: Thresholds = field(default_factory=Thresholds)
    history_window_min: int = 30
    min_evidence_signals: int = 2
    auto_approve_severity: List[str] = field(default_factory=lambda: [SeverityLevel.S0, SeverityLevel.S1])
    require_human_approval: List[str] = field(default_factory=lambda: [SeverityLevel.S3, SeverityLevel.S4])
    backup_domain: str = "zone-b"
    max_retry_attempts: int = 3
    metrics_port: int = 9100
    api_port: int = 5000
    labels: Dict[str, str] = field(default_factory=lambda: {"app": "uc700-self-healing", "version": "1.0.0"})
