"""Modelos para Continuous Evaluation Matrix (CEM) en UC-703."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StaticPrompt:
    prompt_id: str = field(default_factory=lambda: f"sp-{uuid.uuid4().hex[:8]}")
    name: str = ""
    prompt: str = ""
    category: str = ""  # use_case, edge_case, adversarial, safety, fairness
    risk_level: str = "medium"  # low, medium, high, critical
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "name": self.name,
            "prompt": self.prompt,
            "category": self.category,
            "risk_level": self.risk_level,
            "version": self.version,
            "tags": self.tags,
        }


@dataclass
class GoldenSet:
    set_id: str = field(default_factory=lambda: f"gs-{uuid.uuid4().hex[:8]}")
    name: str = ""
    version: str = "1.0.0"
    records: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "name": self.name,
            "version": self.version,
            "record_count": len(self.records),
            "records": self.records,
        }


@dataclass
class TestCell:
    cell_id: str = field(default_factory=lambda: f"cell-{uuid.uuid4().hex[:8]}")
    name: str = ""
    model_version: str = ""
    traffic_pct: float = 0.0
    prompts: List[StaticPrompt] = field(default_factory=list)
    golden_set_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "name": self.name,
            "model_version": self.model_version,
            "traffic_pct": self.traffic_pct,
            "prompt_ids": [p.prompt_id for p in self.prompts],
            "golden_set_id": self.golden_set_id,
        }


@dataclass
class Checkpoint:
    checkpoint_id: str = field(default_factory=lambda: f"ckpt-{uuid.uuid4().hex[:8]}")
    name: str = ""
    version: str = "1.0.0"
    static_prompts: List[StaticPrompt] = field(default_factory=list)
    golden_sets: List[GoldenSet] = field(default_factory=list)
    test_cells: List[TestCell] = field(default_factory=list)
    risk_signals: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "name": self.name,
            "version": self.version,
            "prompt_count": len(self.static_prompts),
            "golden_set_count": len(self.golden_sets),
            "test_cell_count": len(self.test_cells),
            "risk_signals": self.risk_signals,
            "created_at": self.created_at,
        }


@dataclass
class HumanReview:
    review_id: str = field(default_factory=lambda: f"hr-{uuid.uuid4().hex[:8]}")
    sample_id: str = ""
    reviewer_role: str = ""  # domain_expert, ethicist, end_user
    correctness: int = 0
    helpfulness: int = 0
    safety: int = 0
    fairness: int = 0
    comments: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "sample_id": self.sample_id,
            "reviewer_role": self.reviewer_role,
            "correctness": self.correctness,
            "helpfulness": self.helpfulness,
            "safety": self.safety,
            "fairness": self.fairness,
            "comments": self.comments,
            "timestamp": self.timestamp,
        }


@dataclass
class EvaluationSignal:
    signal_id: str = field(default_factory=lambda: f"sig-{uuid.uuid4().hex[:8]}")
    source: str = ""  # automatic, human, user_feedback, adversarial_audit
    metric_name: str = ""
    value: float = 0.0
    threshold: float = 0.0
    passed: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "source": self.source,
            "metric_name": self.metric_name,
            "value": self.value,
            "threshold": self.threshold,
            "passed": self.passed,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class FailureCluster:
    cluster_id: str = field(default_factory=lambda: f"fc-{uuid.uuid4().hex[:8]}")
    pattern: str = ""
    count: int = 0
    sample_ids: List[str] = field(default_factory=list)
    proposed_action: str = ""  # add_prompt, retrain, alert
    risk_signal: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "pattern": self.pattern,
            "count": self.count,
            "sample_ids": self.sample_ids,
            "proposed_action": self.proposed_action,
            "risk_signal": self.risk_signal,
        }


@dataclass
class RiskSignal:
    signal_id: str = field(default_factory=lambda: f"risk-{uuid.uuid4().hex[:8]}")
    name: str = ""
    severity: str = "medium"  # low, medium, high, critical
    category: str = ""  # safety, fairness, privacy, robustness, drift
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "name": self.name,
            "severity": self.severity,
            "category": self.category,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


@dataclass
class CEMReport:
    report_id: str = field(default_factory=lambda: f"cem-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    checkpoint_id: str = ""
    model_version: str = ""
    signals: List[EvaluationSignal] = field(default_factory=list)
    human_reviews: List[HumanReview] = field(default_factory=list)
    failure_clusters: List[FailureCluster] = field(default_factory=list)
    risk_signals: List[RiskSignal] = field(default_factory=list)
    overall_passed: bool = False
    prometheus_uri: str = ""
    loki_uri: str = ""
    wiki_uri: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "checkpoint_id": self.checkpoint_id,
            "model_version": self.model_version,
            "signals": [s.to_dict() for s in self.signals],
            "human_reviews": [r.to_dict() for r in self.human_reviews],
            "failure_clusters": [c.to_dict() for c in self.failure_clusters],
            "risk_signals": [r.to_dict() for r in self.risk_signals],
            "overall_passed": self.overall_passed,
            "prometheus_uri": self.prometheus_uri,
            "loki_uri": self.loki_uri,
            "wiki_uri": self.wiki_uri,
            "created_at": self.created_at,
        }


@dataclass
class UserFeedbackSignal:
    feedback_id: str = field(default_factory=lambda: f"uf-{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    trace_id: str = ""
    user_id: str = ""
    feedback_type: str = ""  # thumbs_down, re_prompt, escalation, explicit_report
    reason: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "feedback_type": self.feedback_type,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
