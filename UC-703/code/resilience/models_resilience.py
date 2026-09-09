"""Modelos para Resilient Multi-Step Tool Recovery Layer."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    run_id: str = ""
    step_id: str = ""
    tool_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "timestamp": self.timestamp,
        }


@dataclass
class ToolResult:
    step_id: str = ""
    status: str = "pending"  # pending, succeeded, failed, recovered, escalated
    output: Any = None
    error: str = ""
    error_category: str = ""  # timeout, exception, invalid_response, context_limit, auth, unknown
    duration_ms: float = 0.0
    attempts: int = 0
    recovery_action: str = ""
    backend: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "error_category": self.error_category,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "recovery_action": self.recovery_action,
            "backend": self.backend,
        }


@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter: bool = True
    retryable_categories: List[str] = field(
        default_factory=lambda: ["timeout", "exception", "invalid_response"]
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "base_delay_seconds": self.base_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "jitter": self.jitter,
            "retryable_categories": self.retryable_categories,
        }


@dataclass
class ErrorClassification:
    category: str = ""
    retryable: bool = False
    severity: str = "medium"  # low, medium, high, critical
    root_cause_hint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "retryable": self.retryable,
            "severity": self.severity,
            "root_cause_hint": self.root_cause_hint,
        }


@dataclass
class ReplanSuggestion:
    suggestion_id: str = field(default_factory=lambda: f"repl-{uuid.uuid4().hex[:8]}")
    step_id: str = ""
    strategy: str = ""  # alternative_tool, simplify, split, escalate
    reasoning: str = ""
    suggested_tool: str = ""
    suggested_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "step_id": self.step_id,
            "strategy": self.strategy,
            "reasoning": self.reasoning,
            "suggested_tool": self.suggested_tool,
            "suggested_params": self.suggested_params,
        }


@dataclass
class EscalationRecord:
    escalation_id: str = field(default_factory=lambda: f"esc-{uuid.uuid4().hex[:8]}")
    step_id: str = ""
    level: str = ""  # repair, hitl
    status: str = "pending"  # pending, resolved, rejected
    context_summary: Dict[str, Any] = field(default_factory=dict)
    operator_decision: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "escalation_id": self.escalation_id,
            "step_id": self.step_id,
            "level": self.level,
            "status": self.status,
            "context_summary": self.context_summary,
            "operator_decision": self.operator_decision,
            "timestamp": self.timestamp,
        }


@dataclass
class RecoveryLogEntry:
    entry_id: str = field(default_factory=lambda: f"rle-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    step_id: str = ""
    tool_name: str = ""
    event: str = ""  # attempt, retry, replan, escalate, repair, hitl, success, failure
    error_category: str = ""
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "event": self.event,
            "error_category": self.error_category,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ResilientPlanState:
    run_id: str = ""
    completed_steps: List[str] = field(default_factory=list)
    failed_step: str = ""
    partial_state: Dict[str, Any] = field(default_factory=dict)
    root_cause: str = ""
    fallback_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "completed_steps": self.completed_steps,
            "failed_step": self.failed_step,
            "partial_state": self.partial_state,
            "root_cause": self.root_cause,
            "fallback_prompt": self.fallback_prompt,
        }


@dataclass
class RecoveryReport:
    report_id: str = field(default_factory=lambda: f"rr-{uuid.uuid4().hex[:8]}")
    run_id: str = ""
    step_id: str = ""
    final_status: str = ""  # succeeded, failed, recovered, escalated
    original_error: str = ""
    error_category: str = ""
    attempts: int = 0
    recovery_action: str = ""
    final_output: Any = None
    escalation: Optional[EscalationRecord] = None
    replan_suggestion: Optional[ReplanSuggestion] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "final_status": self.final_status,
            "original_error": self.original_error,
            "error_category": self.error_category,
            "attempts": self.attempts,
            "recovery_action": self.recovery_action,
            "final_output": self.final_output,
            "escalation": self.escalation.to_dict() if self.escalation else None,
            "replan_suggestion": self.replan_suggestion.to_dict() if self.replan_suggestion else None,
            "telemetry": self.telemetry,
            "created_at": self.created_at,
        }
