"""Modelos de dominio para PreProductionQualityGate."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvalSample:
    sample_id: str = field(default_factory=lambda: f"sample-{uuid.uuid4().hex[:8]}")
    category: str = ""  # use_case, edge_case, adversarial, real_user
    risk_level: str = "medium"  # low, medium, high, critical
    input_text: str = ""
    expected_output: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "category": self.category,
            "risk_level": self.risk_level,
            "input_text": self.input_text,
            "expected_output": self.expected_output,
            "metadata": self.metadata,
        }


@dataclass
class EvalDataset:
    dataset_id: str = field(default_factory=lambda: f"evalds-{uuid.uuid4().hex[:8]}")
    name: str = ""
    samples: List[EvalSample] = field(default_factory=list)
    baseline_version: str = ""
    previous_version: str = ""
    created_at: float = field(default_factory=time.time)

    def by_category(self) -> Dict[str, List[EvalSample]]:
        out: Dict[str, List[EvalSample]] = {}
        for s in self.samples:
            out.setdefault(s.category, []).append(s)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "sample_count": len(self.samples),
            "baseline_version": self.baseline_version,
            "previous_version": self.previous_version,
            "created_at": self.created_at,
            "samples": [s.to_dict() for s in self.samples],
        }


@dataclass
class QuantitativeMetrics:
    metrics_id: str = field(default_factory=lambda: f"qm-{uuid.uuid4().hex[:8]}")
    accuracy: float = 0.0
    relevance: float = 0.0
    safety: float = 0.0  # rejection of toxic/jailbreak
    toxicity_rate: float = 0.0
    jailbreak_rejection_rate: float = 0.0
    bias_score: float = 0.0
    latency_ms_p95: float = 0.0
    cost_per_1k_tokens: float = 0.0
    framework: str = "mock"  # ragas, deepeval, langsmith
    passed: bool = False
    failures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics_id": self.metrics_id,
            "accuracy": self.accuracy,
            "relevance": self.relevance,
            "safety": self.safety,
            "toxicity_rate": self.toxicity_rate,
            "jailbreak_rejection_rate": self.jailbreak_rejection_rate,
            "bias_score": self.bias_score,
            "latency_ms_p95": self.latency_ms_p95,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "framework": self.framework,
            "passed": self.passed,
            "failures": self.failures,
        }


@dataclass
class QualitativeReview:
    review_id: str = field(default_factory=lambda: f"qr-{uuid.uuid4().hex[:8]}")
    reviewer_role: str = ""  # domain_expert, target_user, ethicist
    sample_id: str = ""
    correctness: int = 0  # 1-5
    helpfulness: int = 0
    safety: int = 0
    comments: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "reviewer_role": self.reviewer_role,
            "sample_id": self.sample_id,
            "correctness": self.correctness,
            "helpfulness": self.helpfulness,
            "safety": self.safety,
            "comments": self.comments,
        }


@dataclass
class QualitativeSummary:
    summary_id: str = field(default_factory=lambda: f"qs-{uuid.uuid4().hex[:8]}")
    avg_correctness: float = 0.0
    avg_helpfulness: float = 0.0
    avg_safety: float = 0.0
    review_count: int = 0
    passed: bool = False
    failures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "avg_correctness": self.avg_correctness,
            "avg_helpfulness": self.avg_helpfulness,
            "avg_safety": self.avg_safety,
            "review_count": self.review_count,
            "passed": self.passed,
            "failures": self.failures,
        }


@dataclass
class BaselineComparison:
    comparison_id: str = field(default_factory=lambda: f"cmp-{uuid.uuid4().hex[:8]}")
    current_metrics: Dict[str, float] = field(default_factory=dict)
    baseline_metrics: Dict[str, float] = field(default_factory=dict)
    previous_metrics: Dict[str, float] = field(default_factory=dict)
    deltas_vs_baseline: Dict[str, float] = field(default_factory=dict)
    deltas_vs_previous: Dict[str, float] = field(default_factory=dict)
    regressions: List[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "current_metrics": self.current_metrics,
            "baseline_metrics": self.baseline_metrics,
            "previous_metrics": self.previous_metrics,
            "deltas_vs_baseline": self.deltas_vs_baseline,
            "deltas_vs_previous": self.deltas_vs_previous,
            "regressions": self.regressions,
            "passed": self.passed,
        }


@dataclass
class ApprovalSignature:
    team: str = ""  # engineering, compliance, business
    signed_by: str = ""
    signed_at: float = field(default_factory=time.time)
    comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team": self.team,
            "signed_by": self.signed_by,
            "signed_at": self.signed_at,
            "comment": self.comment,
        }


@dataclass
class CrossTeamApproval:
    approval_id: str = field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:8]}")
    required_teams: List[str] = field(default_factory=lambda: ["engineering", "compliance", "business"])
    signatures: List[ApprovalSignature] = field(default_factory=list)
    status: str = "pending"  # pending, approved, rejected
    paused_workflow_id: str = ""
    expires_at: Optional[float] = None

    def missing_teams(self) -> List[str]:
        signed = {s.team for s in self.signatures}
        return [t for t in self.required_teams if t not in signed]

    def is_approved(self) -> bool:
        signed = {s.team for s in self.signatures}
        return self.required_teams and all(t in signed for t in self.required_teams)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "required_teams": self.required_teams,
            "signatures": [s.to_dict() for s in self.signatures],
            "status": self.status,
            "paused_workflow_id": self.paused_workflow_id,
            "missing_teams": self.missing_teams(),
            "expires_at": self.expires_at,
        }


@dataclass
class QualityGateReport:
    report_id: str = field(default_factory=lambda: f"qgr-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    model_version: str = ""
    dataset_id: str = ""
    quantitative: Optional[QuantitativeMetrics] = None
    qualitative: Optional[QualitativeSummary] = None
    baseline: Optional[BaselineComparison] = None
    cross_team_approval: Optional[CrossTeamApproval] = None
    status: str = "pending"  # pending, blocked, awaiting_approval, approved, rejected
    findings: List[str] = field(default_factory=list)
    evidence_uris: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "model_version": self.model_version,
            "dataset_id": self.dataset_id,
            "quantitative": self.quantitative.to_dict() if self.quantitative else None,
            "qualitative": self.qualitative.to_dict() if self.qualitative else None,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "cross_team_approval": self.cross_team_approval.to_dict() if self.cross_team_approval else None,
            "status": self.status,
            "findings": self.findings,
            "evidence_uris": self.evidence_uris,
            "created_at": self.created_at,
        }
