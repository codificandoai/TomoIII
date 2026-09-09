"""Modelos para Continuous Improvement & Feedback Loop Layer."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FeedbackItem:
    feedback_id: str = field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:8]}")
    source: str = ""  # explicit_rating, explicit_correction, complaint, implicit_reprompt, escalation, operator_annotation
    user_id: str = ""
    session_id: str = ""
    trace_id: str = ""
    model_version: str = ""
    prompt_version_id: str = ""
    category: str = ""  # quality, safety, hallucination, latency, compliance, other
    severity: str = "medium"  # low, medium, high, critical
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "source": self.source,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "model_version": self.model_version,
            "prompt_version_id": self.prompt_version_id,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionLogRef:
    log_id: str = ""
    tool_name: str = ""
    step_id: str = ""
    run_id: str = ""
    status: str = ""
    error_category: str = ""
    latency_ms: float = 0.0


@dataclass
class IncidentRef:
    incident_id: str = ""
    root_cause: str = ""
    resolution: str = ""
    recurring: bool = False


@dataclass
class FeedbackCluster:
    cluster_id: str = field(default_factory=lambda: f"cl-{uuid.uuid4().hex[:8]}")
    pattern: str = ""
    count: int = 0
    feedback_ids: List[str] = field(default_factory=list)
    log_refs: List[ExecutionLogRef] = field(default_factory=list)
    incident_refs: List[IncidentRef] = field(default_factory=list)
    systemic: bool = False
    dominant_category: str = ""
    dominant_severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "pattern": self.pattern,
            "count": self.count,
            "feedback_ids": self.feedback_ids,
            "log_refs": [l.__dict__ for l in self.log_refs],
            "incident_refs": [i.__dict__ for i in self.incident_refs],
            "systemic": self.systemic,
            "dominant_category": self.dominant_category,
            "dominant_severity": self.dominant_severity,
        }


@dataclass
class RootCauseHypothesis:
    hypothesis_id: str = field(default_factory=lambda: f"rch-{uuid.uuid4().hex[:8]}")
    cluster_id: str = ""
    cause_category: str = ""  # prompt, guardrail, data_knowledge, model_drift, infrastructure, unknown
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "cluster_id": self.cluster_id,
            "cause_category": self.cause_category,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "rationale": self.rationale,
        }


@dataclass
class ImprovementRecommendation:
    recommendation_id: str = field(default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}")
    cluster_id: str = ""
    root_cause_category: str = ""
    action_type: str = ""  # prompt_patch, guardrail_rule, data_curation, retrain, hitl_review, monitor
    target: str = ""
    description: str = ""
    expected_impact: str = ""
    confidence: float = 0.0
    status: str = "pending"  # pending, approved, rejected, implemented
    approved_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "cluster_id": self.cluster_id,
            "root_cause_category": self.root_cause_category,
            "action_type": self.action_type,
            "target": self.target,
            "description": self.description,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "status": self.status,
            "approved_by": self.approved_by,
        }


@dataclass
class ImprovementQueueItem:
    item_id: str = field(default_factory=lambda: f"qi-{uuid.uuid4().hex[:8]}")
    recommendation_id: str = ""
    submitted_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, rejected, deferred, implemented
    reviewer_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "recommendation_id": self.recommendation_id,
            "submitted_at": self.submitted_at,
            "status": self.status,
            "reviewer_notes": self.reviewer_notes,
        }


@dataclass
class EffectivenessMeasurement:
    measurement_id: str = field(default_factory=lambda: f"em-{uuid.uuid4().hex[:8]}")
    recommendation_id: str = ""
    metric_name: str = ""
    before_value: float = 0.0
    after_value: float = 0.0
    improvement_pct: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "recommendation_id": self.recommendation_id,
            "metric_name": self.metric_name,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "improvement_pct": self.improvement_pct,
            "timestamp": self.timestamp,
        }
