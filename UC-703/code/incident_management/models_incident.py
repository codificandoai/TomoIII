"""Modelos para Incident Management LLMOps."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    CONTAINED = "contained"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    POST_MORTEM = "post_mortem"


@dataclass
class Incident:
    incident_id: str = field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    source: str = ""  # monitoring, alerting, user_feedback, audit, security_scan
    category: str = ""  # availability, latency, quality, security, compliance, cost
    severity: str = ""
    impact: Dict[str, Any] = field(default_factory=dict)
    urgency: str = ""  # immediate, high, normal, low
    affected_users: int = 0
    regulatory_criticality: str = ""  # none, low, medium, high, critical
    status: str = IncidentStatus.DETECTED.value
    detected_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    assigned_team: str = ""
    owner: str = ""
    runbook_id: str = ""
    containment_actions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "category": self.category,
            "severity": self.severity,
            "impact": self.impact,
            "urgency": self.urgency,
            "affected_users": self.affected_users,
            "regulatory_criticality": self.regulatory_criticality,
            "status": self.status,
            "detected_at": self.detected_at,
            "resolved_at": self.resolved_at,
            "assigned_team": self.assigned_team,
            "owner": self.owner,
            "runbook_id": self.runbook_id,
            "containment_actions": self.containment_actions,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class SLIDefinition:
    sli_id: str = ""
    name: str = ""
    metric: str = ""
    unit: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sli_id": self.sli_id,
            "name": self.name,
            "metric": self.metric,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass
class SLODefinition:
    slo_id: str = field(default_factory=lambda: f"slo-{uuid.uuid4().hex[:8]}")
    sli_id: str = ""
    target: float = 0.0  # e.g. 0.99
    window_seconds: float = 86400.0
    description: str = ""

    def error_budget(self) -> float:
        return round(1.0 - self.target, 6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slo_id": self.slo_id,
            "sli_id": self.sli_id,
            "target": self.target,
            "window_seconds": self.window_seconds,
            "description": self.description,
            "error_budget": self.error_budget(),
        }


@dataclass
class ErrorBudget:
    slo_id: str = ""
    window_start: float = 0.0
    window_end: float = 0.0
    total_budget: float = 0.0
    consumed: float = 0.0
    remaining: float = 0.0
    burn_rate: float = 0.0  # fraction per hour

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slo_id": self.slo_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "total_budget": self.total_budget,
            "consumed": self.consumed,
            "remaining": self.remaining,
            "burn_rate": self.burn_rate,
        }


@dataclass
class Alert:
    alert_id: str = field(default_factory=lambda: f"al-{uuid.uuid4().hex[:8]}")
    incident_id: str = ""
    metric: str = ""
    value: float = 0.0
    threshold: float = 0.0
    severity: str = ""
    team: str = ""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "incident_id": self.incident_id,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity,
            "team": self.team,
            "message": self.message,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


@dataclass
class OnCallPerson:
    name: str = ""
    team: str = ""
    phone: str = ""
    email: str = ""
    active: bool = True


@dataclass
class Runbook:
    runbook_id: str = ""
    title: str = ""
    category: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runbook_id": self.runbook_id,
            "title": self.title,
            "category": self.category,
            "steps": self.steps,
            "version": self.version,
        }


@dataclass
class PostMortem:
    post_mortem_id: str = field(default_factory=lambda: f"pm-{uuid.uuid4().hex[:8]}")
    incident_id: str = ""
    summary: str = ""
    root_cause: str = ""
    impact: Dict[str, Any] = field(default_factory=dict)
    detection_time_minutes: float = 0.0
    mitigation_time_minutes: float = 0.0
    recovery_time_minutes: float = 0.0
    failed_controls: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    lessons_learned: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_mortem_id": self.post_mortem_id,
            "incident_id": self.incident_id,
            "summary": self.summary,
            "root_cause": self.root_cause,
            "impact": self.impact,
            "detection_time_minutes": self.detection_time_minutes,
            "mitigation_time_minutes": self.mitigation_time_minutes,
            "recovery_time_minutes": self.recovery_time_minutes,
            "failed_controls": self.failed_controls,
            "action_items": self.action_items,
            "lessons_learned": self.lessons_learned,
            "created_at": self.created_at,
        }


@dataclass
class CommunicationRecord:
    comm_id: str = field(default_factory=lambda: f"comm-{uuid.uuid4().hex[:8]}")
    incident_id: str = ""
    channel: str = ""  # email, slack, pager, wiki
    recipient_team: str = ""
    template_name: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comm_id": self.comm_id,
            "incident_id": self.incident_id,
            "channel": self.channel,
            "recipient_team": self.recipient_team,
            "template_name": self.template_name,
            "content": self.content,
            "timestamp": self.timestamp,
        }
