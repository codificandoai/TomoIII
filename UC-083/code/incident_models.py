"""
UC-083 — Modelos de datos para Respuesta a Incidentes de Inferencia Batch.

Define estructuras para incidentes, causas raíz, mitigaciones, métricas,
validaciones, checkpoints y reportes post-incidente.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import uuid


class IncidentSeverity(Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IncidentStatus(Enum):
    DETECTED = "detected"
    TRIAGING = "triaging"
    MITIGATING = "mitigating"
    RECOVERING = "recovering"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


class RootCauseCategory(Enum):
    OOM = "out_of_memory"
    TIMEOUT = "timeout"
    DATA_VOLUME = "data_volume_spike"
    SCHEMA_DRIFT = "schema_drift"
    INFRASTRUCTURE = "infrastructure"
    MODEL_FAILURE = "model_failure"
    UNKNOWN = "unknown"


class MitigationType(Enum):
    STOP_RETRIES = "stop_retries"
    CHUNKING = "chunking"
    DISTRIBUTED = "distributed_processing"
    ROLLBACK = "rollback"
    SCALE_UP = "scale_up"
    REPROCESS = "reprocess_partitions"
    FAIL_FAST = "fail_fast"


@dataclass
class MetricSnapshot:
    """Instantánea de métrica de infraestructura."""
    timestamp: float
    metric_name: str
    value: float
    unit: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
        }


@dataclass
class LogEntry:
    """Entrada de log estructurada."""
    timestamp: float
    level: str
    source: str
    message: str
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }


@dataclass
class ValidationReport:
    """Reporte de validación de datos."""
    check_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class RootCause:
    """Causa raíz identificada."""
    category: RootCauseCategory
    confidence: float
    description: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    recommended_mitigations: List[MitigationType] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "confidence": round(self.confidence, 4),
            "description": self.description,
            "evidence": self.evidence,
            "recommended_mitigations": [m.value for m in self.recommended_mitigations],
        }


@dataclass
class Checkpoint:
    """Checkpoint idempotente de reprocesamiento."""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    partition_id: str = ""
    status: str = "pending"  # pending, completed, failed
    records_processed: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "partition_id": self.partition_id,
            "status": self.status,
            "records_processed": self.records_processed,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Mitigation:
    """Acción de mitigación aplicada."""
    mitigation_type: MitigationType
    description: str
    mitigation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    status: str = "applied"  # applied, failed, verified
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mitigation_id": self.mitigation_id,
            "mitigation_type": self.mitigation_type.value,
            "description": self.description,
            "status": self.status,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Incident:
    """Incidente completo."""
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: IncidentSeverity = IncidentSeverity.P2
    status: IncidentStatus = IncidentStatus.DETECTED
    title: str = ""
    description: str = ""
    affected_partitions: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    resolved_time: Optional[float] = None
    root_causes: List[RootCause] = field(default_factory=list)
    mitigations: List[Mitigation] = field(default_factory=list)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    validation_reports: List[ValidationReport] = field(default_factory=list)
    metrics: List[MetricSnapshot] = field(default_factory=list)
    logs: List[LogEntry] = field(default_factory=list)
    runbook_steps: List[Dict[str, Any]] = field(default_factory=list)
    postmortem: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "severity": self.severity.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "affected_partitions": self.affected_partitions,
            "start_time": self.start_time,
            "resolved_time": self.resolved_time,
            "root_causes": [r.to_dict() for r in self.root_causes],
            "mitigations": [m.to_dict() for m in self.mitigations],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "validation_reports": [v.to_dict() for v in self.validation_reports],
            "metrics": [m.to_dict() for m in self.metrics],
            "logs": [l.to_dict() for l in self.logs],
            "runbook_steps": self.runbook_steps,
            "postmortem": self.postmortem,
        }


@dataclass
class Postmortem:
    """Reporte post-incidente."""
    incident_id: str = ""
    summary: str = ""
    root_cause_summary: str = ""
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    runbook_updates: List[str] = field(default_factory=list)
    monitoring_updates: List[str] = field(default_factory=list)
    ansible_updates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "summary": self.summary,
            "root_cause_summary": self.root_cause_summary,
            "timeline": self.timeline,
            "improvements": self.improvements,
            "runbook_updates": self.runbook_updates,
            "monitoring_updates": self.monitoring_updates,
            "ansible_updates": self.ansible_updates,
        }


@dataclass
class IncidentResponseConfig:
    """Configuración del módulo de respuesta a incidentes."""
    max_allowed_rows: int = 1_000_000
    memory_threshold: float = 90.0
    cpu_threshold: float = 90.0
    duration_threshold_minutes: float = 120.0
    chunk_size_rows: int = 100_000
    max_concurrency: int = 4
    max_retries: int = 2
    retry_delay_seconds: int = 60
    baseline_window: int = 30
    anomaly_zscore: float = 3.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_allowed_rows": self.max_allowed_rows,
            "memory_threshold": self.memory_threshold,
            "cpu_threshold": self.cpu_threshold,
            "duration_threshold_minutes": self.duration_threshold_minutes,
            "chunk_size_rows": self.chunk_size_rows,
            "max_concurrency": self.max_concurrency,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "baseline_window": self.baseline_window,
            "anomaly_zscore": self.anomaly_zscore,
        }


@dataclass
class IncidentResponseResult:
    """Resultado completo del proceso de respuesta."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident: Optional[Incident] = None
    postmortem: Optional[Postmortem] = None
    runbook: Optional[Dict[str, Any]] = None
    ansible_playbook: Optional[str] = None
    monitoring_config: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "incident": self.incident.to_dict() if self.incident else None,
            "postmortem": self.postmortem.to_dict() if self.postmortem else None,
            "runbook": self.runbook,
            "ansible_playbook": self.ansible_playbook,
            "monitoring_config": self.monitoring_config,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }
