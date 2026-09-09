"""Modelos para Compliance as Code (CaC) layer en UC-703."""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptVersion:
    version_id: str = field(default_factory=lambda: f"pv-{uuid.uuid4().hex[:8]}")
    prompt_name: str = ""
    content: str = ""
    author: str = ""
    parent_version_id: str = ""
    commit_message: str = ""
    regulatory_change: bool = False
    approved_by: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    diff_summary: str = ""

    @property
    def git_like_uri(self) -> str:
        digest = hashlib.sha256(self.content.encode()).hexdigest()[:12]
        return f"git://prompts/{self.prompt_name}/{self.version_id}-{digest}.md"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "prompt_name": self.prompt_name,
            "content": self.content,
            "author": self.author,
            "parent_version_id": self.parent_version_id,
            "commit_message": self.commit_message,
            "regulatory_change": self.regulatory_change,
            "approved_by": self.approved_by,
            "timestamp": self.timestamp,
            "diff_summary": self.diff_summary,
            "git_like_uri": self.git_like_uri,
        }


@dataclass
class DatasetLineage:
    dataset_id: str = ""
    source: str = ""
    transformations: List[Dict[str, Any]] = field(default_factory=list)
    consent_tags: List[str] = field(default_factory=list)
    retention_hours: float = 0.0
    purpose: str = ""
    privacy_controls: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "source": self.source,
            "transformations": self.transformations,
            "consent_tags": self.consent_tags,
            "retention_hours": self.retention_hours,
            "purpose": self.purpose,
            "privacy_controls": self.privacy_controls,
            "created_at": self.created_at,
        }


@dataclass
class ArtifactBundle:
    """Artefacto compuesto exacto usado en inferencia."""
    bundle_id: str = field(default_factory=lambda: f"bundle-{uuid.uuid4().hex[:8]}")
    base_weights: str = ""
    adapter: str = ""
    prompt_version_id: str = ""
    generation_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "base_weights": self.base_weights,
            "adapter": self.adapter,
            "prompt_version_id": self.prompt_version_id,
            "generation_params": self.generation_params,
        }


@dataclass
class InferenceAuditRecord:
    record_id: str = field(default_factory=lambda: f"iar-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    request_id: str = ""
    session_id: str = ""
    requester_id: str = ""
    requester_roles: List[str] = field(default_factory=list)
    artifact_bundle: Optional[ArtifactBundle] = None
    input_redacted: str = ""
    output_redacted: str = ""
    access_decision: str = ""  # allowed, denied, escalated
    policies_applied: List[str] = field(default_factory=list)
    pii_detected: bool = False
    guardrail_violations: List[str] = field(default_factory=list)
    hash_chain: str = ""
    e_discovery_tag: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "requester_id": self.requester_id,
            "requester_roles": self.requester_roles,
            "artifact_bundle": self.artifact_bundle.to_dict() if self.artifact_bundle else None,
            "input_redacted": self.input_redacted,
            "output_redacted": self.output_redacted,
            "access_decision": self.access_decision,
            "policies_applied": self.policies_applied,
            "pii_detected": self.pii_detected,
            "guardrail_violations": self.guardrail_violations,
            "hash_chain": self.hash_chain,
            "e_discovery_tag": self.e_discovery_tag,
        }


@dataclass
class AccessDecision:
    decision_id: str = field(default_factory=lambda: f"ad-{uuid.uuid4().hex[:8]}")
    requester_id: str = ""
    resource: str = ""
    action: str = ""
    environment: str = ""
    decision: str = "deny"  # allow, deny, escalate
    reason: str = ""
    oidc_claims: Dict[str, Any] = field(default_factory=dict)
    cmk_key_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "requester_id": self.requester_id,
            "resource": self.resource,
            "action": self.action,
            "environment": self.environment,
            "decision": self.decision,
            "reason": self.reason,
            "oidc_claims": self.oidc_claims,
            "cmk_key_id": self.cmk_key_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ComplianceRule:
    rule_id: str = field(default_factory=lambda: f"rule-{uuid.uuid4().hex[:8]}")
    framework: str = ""  # GDPR, CCPA, HIPAA, EU_AI_Act, DORA, BCBS239
    article: str = ""
    control: str = ""
    technical_metric: str = ""
    threshold_operator: str = ""  # lt, le, gt, ge, eq, ne
    threshold_value: float = 0.0
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "framework": self.framework,
            "article": self.article,
            "control": self.control,
            "technical_metric": self.technical_metric,
            "threshold_operator": self.threshold_operator,
            "threshold_value": self.threshold_value,
            "severity": self.severity,
        }


@dataclass
class ComplianceAlert:
    alert_id: str = field(default_factory=lambda: f"alert-{uuid.uuid4().hex[:8]}")
    rule_id: str = ""
    framework: str = ""
    article: str = ""
    message: str = ""
    metric_value: float = 0.0
    threshold_value: float = 0.0
    timestamp: float = field(default_factory=time.time)
    status: str = "open"  # open, acknowledged, resolved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "framework": self.framework,
            "article": self.article,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "timestamp": self.timestamp,
            "status": self.status,
        }


@dataclass
class ComplianceReport:
    report_id: str = field(default_factory=lambda: f"cr-{uuid.uuid4().hex[:8]}")
    generated_at: float = field(default_factory=time.time)
    overall_status: str = "compliant"  # compliant, at_risk, non_compliant
    framework_scores: Dict[str, float] = field(default_factory=dict)
    open_alerts: int = 0
    evidence_count: int = 0
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "overall_status": self.overall_status,
            "framework_scores": self.framework_scores,
            "open_alerts": self.open_alerts,
            "evidence_count": self.evidence_count,
            "findings": self.findings,
        }
