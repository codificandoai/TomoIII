"""
Codificando.AI - UC-129
Tipos de datos centrales del sistema de métricas de resiliencia LLMOps:
tipos de incidente, severidad, métodos de detección/resolución, trazas de
telemetría ingeridas y el registro completo de un incidente (usado tanto
para calcular MTTD/MTTR como para exponer el historial vía API).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class IncidentType(str, Enum):
    HALLUCINATION = "HALLUCINATION"
    JAILBREAK = "JAILBREAK"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    BIAS = "BIAS"
    TOXICITY = "TOXICITY"
    TOOL_FAILURE = "TOOL_FAILURE"
    SYSTEM_OVERLOAD = "SYSTEM_OVERLOAD"
    LATENCY_SPIKE = "LATENCY_SPIKE"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectionSource(str, Enum):
    AUTO_GUARDRAIL = "auto_guardrail"
    USER_FEEDBACK = "user_feedback"
    MONITORING_ALERT = "monitoring_alert"
    LANGFUSE = "langfuse"
    LANGSMITH = "langsmith"
    LANGGRAPH = "langgraph"
    MANUAL = "manual"


class ResolutionType(str, Enum):
    AUTO_REMEDIATION = "auto_remediation"
    HITL_MANUAL = "hitl_manual"
    ROLLBACK = "rollback"
    PROMPT_REVERT = "prompt_revert"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


@dataclass
class IngestedTrace:
    """Representación normalizada de una traza/observación proveniente de
    Langfuse, LangSmith o LangGraph (ver `connectors/`), independiente del
    formato nativo de cada plataforma."""
    source: DetectionSource
    trace_id: str
    model: str = "unknown"
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    status: str = "success"  # success | error | interrupted
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value,
            "trace_id": self.trace_id,
            "model": self.model,
            "latency_seconds": self.latency_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "status": self.status,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class IncidentRecord:
    """Registro completo del ciclo de vida de un incidente, usado para
    calcular MTTD/MTTR y para exponer el historial de auditoría vía API."""
    incident_type: IncidentType
    severity: Severity = Severity.MEDIUM
    source: DetectionSource = DetectionSource.MONITORING_ALERT
    model: str = "unknown"
    summary: str = ""
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: Optional[str] = None
    status: IncidentStatus = IncidentStatus.DETECTED

    event_time: float = 0.0
    detect_time: Optional[float] = None
    resolve_time: Optional[float] = None

    detection_method: Optional[str] = None
    resolution_type: Optional[ResolutionType] = None
    resolution_success: Optional[bool] = None

    is_false_positive: bool = False
    hitl_escalated: bool = False
    escalation_reason: Optional[str] = None
    reviewer_role: Optional[str] = None

    tokens_during_incident: int = 0
    latency_during_incident_s: Optional[float] = None

    root_cause: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def mttd_seconds(self) -> Optional[float]:
        if self.detect_time is None:
            return None
        return max(self.detect_time - self.event_time, 0.0)

    @property
    def mttr_seconds(self) -> Optional[float]:
        if self.resolve_time is None or self.detect_time is None:
            return None
        return max(self.resolve_time - self.detect_time, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "source": self.source.value,
            "model": self.model,
            "summary": self.summary,
            "trace_id": self.trace_id,
            "status": self.status.value,
            "event_time": self.event_time,
            "detect_time": self.detect_time,
            "resolve_time": self.resolve_time,
            "mttd_seconds": self.mttd_seconds,
            "mttr_seconds": self.mttr_seconds,
            "detection_method": self.detection_method,
            "resolution_type": self.resolution_type.value if self.resolution_type else None,
            "resolution_success": self.resolution_success,
            "is_false_positive": self.is_false_positive,
            "hitl_escalated": self.hitl_escalated,
            "escalation_reason": self.escalation_reason,
            "reviewer_role": self.reviewer_role,
            "tokens_during_incident": self.tokens_during_incident,
            "latency_during_incident_s": self.latency_during_incident_s,
            "root_cause": self.root_cause,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
