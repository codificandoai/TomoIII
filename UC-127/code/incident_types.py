"""
Codificando.AI - UC-127
Tipos de datos centrales de la orquestación de respuesta a incidentes:
tipos de incidente, severidad, alertas de entrada, acciones de playbook
y el registro de auditoría de un incidente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class IncidentType(str, Enum):
    """Tipos de incidente de LLMOps cubiertos por UC-127."""

    HALLUCINATION = "HALLUCINATION"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    DATA_LEAK = "DATA_LEAK"
    QUALITY_DEGRADATION = "QUALITY_DEGRADATION"
    TOOL_FAILURE = "TOOL_FAILURE"
    LATENCY_ANOMALY = "LATENCY_ANOMALY"
    COST_ANOMALY = "COST_ANOMALY"
    UNSAFE_GENERATION = "UNSAFE_GENERATION"
    SYSTEM_OVERLOAD = "SYSTEM_OVERLOAD"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[self.value]

    def __ge__(self, other: "Severity") -> bool:
        return self.rank >= other.rank

    def __lt__(self, other: "Severity") -> bool:
        return self.rank < other.rank


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    RUNNING_PLAYBOOK = "RUNNING_PLAYBOOK"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REMEDIATED = "REMEDIATED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class ActionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REJECTED = "REJECTED"


@dataclass
class IncidentAlert:
    """Entrada normalizada al pipeline de respuesta a incidentes.

    Puede construirse a partir de un webhook de Alertmanager/Grafana, de
    una llamada directa del pipeline de monitoreo de LLMs (UC-119), o de
    un reporte manual de usuario/moderador."""

    incident_type: IncidentType
    severity: Severity
    model: str = "unknown"
    model_version: Optional[str] = None
    summary: str = ""
    source: str = "manual"
    metrics: Dict[str, float] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    starts_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "model": self.model,
            "model_version": self.model_version,
            "summary": self.summary,
            "source": self.source,
            "metrics": self.metrics,
            "labels": self.labels,
            "correlation_id": self.correlation_id,
            "starts_at": self.starts_at,
        }


@dataclass
class ActionResult:
    """Resultado de la ejecución de un paso individual de un playbook."""

    name: str
    status: ActionStatus
    detail: str = ""
    requires_approval: bool = False
    reversible: bool = True
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "requires_approval": self.requires_approval,
            "reversible": self.reversible,
            "executed_at": self.executed_at,
        }


@dataclass
class IncidentRecord:
    """Registro completo y trazable de un incidente y su remediación.

    Constituye la "memoria institucional" (ver `UC-127.md`, sección de
    Valor Operativo) que se persiste como historial de auditoría y se usa
    para alimentar Wiki.js, el dashboard de resiliencia y el ciclo de
    actualización de SOPs."""

    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert: Optional[IncidentAlert] = None
    playbook_name: Optional[str] = None
    status: IncidentStatus = IncidentStatus.DETECTED
    actions: List[ActionResult] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    mttr_seconds: Optional[float] = None
    root_cause: Optional[str] = None
    playbook_effective: Optional[bool] = None
    postmortem_notes: Optional[str] = None
    rolled_back: bool = False
    is_simulation: bool = False
    recurrence_count_7d: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "alert": self.alert.to_dict() if self.alert else None,
            "playbook_name": self.playbook_name,
            "status": self.status.value,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
            "mttr_seconds": self.mttr_seconds,
            "root_cause": self.root_cause,
            "playbook_effective": self.playbook_effective,
            "postmortem_notes": self.postmortem_notes,
            "rolled_back": self.rolled_back,
            "is_simulation": self.is_simulation,
            "recurrence_count_7d": self.recurrence_count_7d,
        }
