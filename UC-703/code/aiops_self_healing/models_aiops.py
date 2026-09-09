"""Modelos para AIOps Self-Healing Platform en UC-703."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AIOpsState(str, Enum):
    DETECTED = "detected"
    NORMALIZED = "normalized"
    CORRELATED = "correlated"
    DIAGNOSING = "diagnosing"
    REMEDIATING = "remediating"
    VALIDATING = "validating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class RemediationType(str, Enum):
    AUTOSCALE = "autoscale"
    RATE_LIMIT = "rate_limit"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK_MODEL = "fallback_model"
    FALLBACK_PROVIDER = "fallback_provider"
    ROLLBACK_PROMPT = "rollback_prompt"
    ROLLBACK_MODEL = "rollback_model"
    ROLLBACK_CONFIG = "rollback_config"
    SANDBOX_ISOLATION = "sandbox_isolation"
    HEALTH_TEST = "health_test"
    HUMAN_ESCALATION = "human_escalation"


@dataclass
class RawEvent:
    event_id: str = field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:8]}")
    source: str = ""  # prometheus, loki, security, quality, cost
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "raw_payload": self.raw_payload,
            "timestamp": self.timestamp,
        }


@dataclass
class NormalizedAlert:
    alert_id: str = field(default_factory=lambda: f"na-{uuid.uuid4().hex[:8]}")
    event_id: str = ""
    source: str = ""
    metric: str = ""
    value: float = 0.0
    threshold: float = 0.0
    severity: str = ""  # critical, high, medium, low
    category: str = ""  # availability, latency, quality, security, compliance, cost
    resource: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "event_id": self.event_id,
            "source": self.source,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity,
            "category": self.category,
            "resource": self.resource,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class CorrelationGroup:
    group_id: str = field(default_factory=lambda: f"cg-{uuid.uuid4().hex[:8]}")
    alert_ids: List[str] = field(default_factory=list)
    category: str = ""
    resource: str = ""
    severity: str = ""
    window_start: float = 0.0
    window_end: float = 0.0
    symptoms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "alert_ids": self.alert_ids,
            "category": self.category,
            "resource": self.resource,
            "severity": self.severity,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "symptoms": self.symptoms,
        }


@dataclass
class Diagnosis:
    diagnosis_id: str = field(default_factory=lambda: f"diag-{uuid.uuid4().hex[:8]}")
    group_id: str = ""
    summary: str = ""
    root_cause_hypothesis: str = ""
    confidence: float = 0.0
    proposed_remediations: List[RemediationType] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    requires_human_review: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "group_id": self.group_id,
            "summary": self.summary,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "confidence": self.confidence,
            "proposed_remediations": [r.value for r in self.proposed_remediations],
            "evidence": self.evidence,
            "requires_human_review": self.requires_human_review,
            "timestamp": self.timestamp,
        }


@dataclass
class RemediationAction:
    action_id: str = field(default_factory=lambda: f"rem-{uuid.uuid4().hex[:8]}")
    group_id: str = ""
    action_type: str = ""
    target: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, executing, succeeded, failed, rolled_back
    result: Dict[str, Any] = field(default_factory=dict)
    approved_by: str = ""
    requires_approval: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "group_id": self.group_id,
            "action_type": self.action_type,
            "target": self.target,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "approved_by": self.approved_by,
            "requires_approval": self.requires_approval,
            "timestamp": self.timestamp,
        }


@dataclass
class RemediationPolicy:
    policy_id: str = field(default_factory=lambda: f"pol-{uuid.uuid4().hex[:8]}")
    action_type: str = ""
    category: str = ""
    severity: str = ""
    max_frequency_minutes: float = 5.0
    requires_approval: bool = False
    conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "action_type": self.action_type,
            "category": self.category,
            "severity": self.severity,
            "max_frequency_minutes": self.max_frequency_minutes,
            "requires_approval": self.requires_approval,
            "conditions": self.conditions,
        }


@dataclass
class AIOpsAuditRecord:
    record_id: str = field(default_factory=lambda: f"aio-{uuid.uuid4().hex[:8]}")
    group_id: str = ""
    state: str = ""
    raw_event_ids: List[str] = field(default_factory=list)
    alert_ids: List[str] = field(default_factory=list)
    diagnosis_id: str = ""
    remediation_ids: List[str] = field(default_factory=list)
    decision: str = ""
    approvals: List[str] = field(default_factory=list)
    outcome: str = ""
    responsible: str = ""
    timestamp: float = field(default_factory=time.time)
    immutable_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "group_id": self.group_id,
            "state": self.state,
            "raw_event_ids": self.raw_event_ids,
            "alert_ids": self.alert_ids,
            "diagnosis_id": self.diagnosis_id,
            "remediation_ids": self.remediation_ids,
            "decision": self.decision,
            "approvals": self.approvals,
            "outcome": self.outcome,
            "responsible": self.responsible,
            "timestamp": self.timestamp,
            "immutable_hash": self.immutable_hash,
        }


@dataclass
class CommunicationRecord:
    comm_id: str = field(default_factory=lambda: f"comm-{uuid.uuid4().hex[:8]}")
    group_id: str = ""
    channel: str = ""
    recipient: str = ""
    template: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comm_id": self.comm_id,
            "group_id": self.group_id,
            "channel": "",
            "recipient": self.recipient,
            "template": self.template,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class SelfHealingReport:
    report_id: str = field(default_factory=lambda: f"shr-{uuid.uuid4().hex[:8]}")
    group_id: str = ""
    state: str = ""
    diagnosis: Optional[Diagnosis] = None
    actions: List[RemediationAction] = field(default_factory=list)
    audit_record: Optional[AIOpsAuditRecord] = None
    communications: List[CommunicationRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "group_id": self.group_id,
            "state": self.state,
            "diagnosis": self.diagnosis.to_dict() if self.diagnosis else None,
            "actions": [a.to_dict() for a in self.actions],
            "audit_record": self.audit_record.to_dict() if self.audit_record else None,
            "communications": [c.to_dict() for c in self.communications],
            "created_at": self.created_at,
        }
