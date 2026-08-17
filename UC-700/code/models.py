"""UC-700 — Modelos de dominio para autosanación avanzada del entrenamiento."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import FailureClass, HealthState, RemediationStrategy, SeverityLevel


@dataclass
class Device:
    """Acelerador o dispositivo dentro de un nodo."""

    id: str
    kind: str  # gpu, nic, fpga, etc.
    vendor: str
    index: int
    node_id: str
    state: str = HealthState.HEALTHY
    vram_total_gb: float = 80.0
    vram_used_gb: float = 0.0
    temperature_c: float = 40.0
    util_pct: float = 0.0
    memory_errors: int = 0


@dataclass
class Node:
    """Nodo de computo con dispositivos y metadatos de topología."""

    id: str
    campus: str
    zone: str
    room: str
    rack: str
    devices: List[Device] = field(default_factory=list)
    state: str = HealthState.HEALTHY
    labels: Dict[str, str] = field(default_factory=dict)
    taints: List[str] = field(default_factory=list)


@dataclass
class TrainingJob:
    """Job de entrenamiento distribuido."""

    id: str
    name: str
    replicas: int
    nodes: List[str] = field(default_factory=list)
    checkpoint_path: Optional[str] = None
    samples_per_sec_baseline: float = 100000.0
    loss_baseline: float = 2.0
    framework: str = "pytorch"
    priority: str = "normal"


@dataclass
class Checkpoint:
    """Checkpoint válido de entrenamiento."""

    id: str
    job_id: str
    path: str
    timestamp: datetime
    global_step: int
    verified: bool = False
    size_bytes: int = 0
    checksum: Optional[str] = None


@dataclass
class TelemetrySnapshot:
    """Instantánea de telemetría de un nodo/dispositivo."""

    node_id: str
    timestamp: datetime
    metrics: Dict[str, float] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)
    device_id: Optional[str] = None
    source: str = "dcgm"


@dataclass
class AnomalySignal:
    """Señal de anomalía detectada."""

    node_id: str
    score: float
    features: Dict[str, float]
    contributing_metrics: List[str]
    timestamp: datetime
    confidence: float


@dataclass
class Diagnosis:
    """Resultado del motor de diagnóstico."""

    failure_class: str
    evidence: List[Dict[str, Any]]
    confidence: float
    suspected_devices: List[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class ImpactReport:
    """Análisis de impacto de un fallo."""

    scope: str  # device, node, rack, zone, domain, region
    affected_nodes: List[str]
    affected_devices: List[str]
    affected_jobs: List[str]
    affected_tenants: List[str]
    affected_models: List[str]
    blast_radius_score: float


@dataclass
class RemediationPlan:
    """Plan de remediación aprobado."""

    strategy: str
    target_node_id: str
    target_device_ids: List[str]
    affected_jobs: List[str]
    checkpoint_id: Optional[str] = None
    replacement_node_id: Optional[str] = None
    requires_approval: bool = False
    estimated_downtime_sec: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Incident:
    """Incidente de autosanación."""

    id: str = field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:8].upper()}")
    node_id: str = ""
    device_ids: List[str] = field(default_factory=list)
    severity: str = SeverityLevel.S0
    failure_class: str = FailureClass.UNKNOWN
    state: str = HealthState.SUSPECTED
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    diagnosis: Optional[Diagnosis] = None
    impact: Optional[ImpactReport] = None
    plan: Optional[RemediationPlan] = None
    validation: Optional[Dict[str, Any]] = None
    efficiency: Optional[Dict[str, Any]] = None
    escalated: bool = False
    trace: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_trace(self, step: str, agent: str, details: Dict[str, Any]) -> None:
        self.trace.append(
            {
                "step": step,
                "agent": agent,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details,
            }
        )


@dataclass
class AgentResponse:
    """Respuesta estructurada de un agente del sistema."""

    agent: str
    status: str
    decision: str
    confidence: float
    payload: Dict[str, Any] = field(default_factory=dict)
    trace: List[Dict[str, Any]] = field(default_factory=list)
