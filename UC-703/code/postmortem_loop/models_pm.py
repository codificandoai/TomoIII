"""Modelos para bucle de post-mortem autónomo de LLMOps."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IncidentRecord:
    record_id: str = field(default_factory=lambda: f"pmr-{uuid.uuid4().hex[:8]}")
    incident_id: str = ""
    title: str = ""
    description: str = ""
    severity: str = ""
    category: str = ""
    timestamp: float = field(default_factory=time.time)
    prompt: str = ""
    output: str = ""
    model_version: str = ""
    prompt_version: str = ""
    tool_logs: List[Dict[str, Any]] = field(default_factory=list)
    config_diffs: List[str] = field(default_factory=list)
    embeddings_state: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "incident_id": self.incident_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "timestamp": self.timestamp,
            "prompt": self.prompt,
            "output": self.output,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "tool_logs": self.tool_logs,
            "config_diffs": self.config_diffs,
            "embeddings_state": self.embeddings_state,
            "metadata": self.metadata,
        }


@dataclass
class RootCauseHypothesis:
    hypothesis_id: str = field(default_factory=lambda: f"h-{uuid.uuid4().hex[:8]}")
    record_id: str = ""
    taxonomy: str = ""  # hallucination, bad_rag, prompt_injection, model_regression, tool_bug
    summary: str = ""
    confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    approved: bool = False
    approver: str = ""
    notes: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "record_id": self.record_id,
            "taxonomy": self.taxonomy,
            "summary": self.summary,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "approved": self.approved,
            "approver": self.approver,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }


@dataclass
class CorrectiveProposal:
    proposal_id: str = field(default_factory=lambda: f"cp-{uuid.uuid4().hex[:8]}")
    record_id: str = ""
    hypothesis_id: str = ""
    action_type: str = ""  # prompt_patch, guardrail_rule, tool_fix
    target: str = ""
    patch: str = ""
    rationale: str = ""
    status: str = "pending"  # pending, approved, rejected
    approver: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "record_id": self.record_id,
            "hypothesis_id": self.hypothesis_id,
            "action_type": self.action_type,
            "target": self.target,
            "patch": self.patch,
            "rationale": self.rationale,
            "status": self.status,
            "approver": self.approver,
            "timestamp": self.timestamp,
        }


@dataclass
class AntiRegressionCase:
    case_id: str = field(default_factory=lambda: f"arc-{uuid.uuid4().hex[:8]}")
    record_id: str = ""
    input_text: str = ""
    expected_behavior: str = ""
    tags: List[str] = field(default_factory=list)
    generated_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "record_id": self.record_id,
            "input_text": self.input_text,
            "expected_behavior": self.expected_behavior,
            "tags": self.tags,
            "generated_by": self.generated_by,
        }


@dataclass
class RunbookUpdate:
    update_id: str = field(default_factory=lambda: f"ru-{uuid.uuid4().hex[:8]}")
    record_id: str = ""
    runbook_id: str = ""
    changes: str = ""
    author: str = "aiops-postmortem"
    version: str = "1.0.0"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "record_id": self.record_id,
            "runbook_id": self.runbook_id,
            "changes": self.changes,
            "author": self.author,
            "version": self.version,
            "timestamp": self.timestamp,
        }


@dataclass
class ValidationResult:
    validation_id: str = field(default_factory=lambda: f"val-{uuid.uuid4().hex[:8]}")
    proposal_id: str = ""
    benchmark_passed: bool = False
    score: float = 0.0
    regression_detected: bool = False
    shadow_passed: bool = False
    judge_score: float = 0.0
    details: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "proposal_id": self.proposal_id,
            "benchmark_passed": self.benchmark_passed,
            "score": self.score,
            "regression_detected": self.regression_detected,
            "shadow_passed": self.shadow_passed,
            "judge_score": self.judge_score,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class PostMortemReport:
    report_id: str = field(default_factory=lambda: f"rep-{uuid.uuid4().hex[:8]}")
    record_id: str = ""
    timeline: List[str] = field(default_factory=list)
    root_cause: str = ""
    impact: str = ""
    lessons: str = ""
    corrective_proposals: List[str] = field(default_factory=list)
    runbook_updates: List[str] = field(default_factory=list)
    status: str = "draft"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "record_id": self.record_id,
            "timeline": self.timeline,
            "root_cause": self.root_cause,
            "impact": self.impact,
            "lessons": self.lessons,
            "corrective_proposals": self.corrective_proposals,
            "runbook_updates": self.runbook_updates,
            "status": self.status,
            "timestamp": self.timestamp,
        }
