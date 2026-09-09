"""Modelos para métricas extrínsecas y recuperación contextual."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ApplicationEvent:
    event_id: str = field(default_factory=lambda: f"app-{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    event_type: str = ""  # task_completed, task_failed, user_abandoned, session_started, revenue
    timestamp: float = field(default_factory=time.time)
    user_id: str = ""
    task_id: str = ""
    task_name: str = ""
    success: Optional[bool] = None
    revenue_usd: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "success": self.success,
            "revenue_usd": self.revenue_usd,
            "metadata": self.metadata,
        }


@dataclass
class InferenceEvent:
    event_id: str = field(default_factory=lambda: f"inf-{uuid.uuid4().hex[:8]}")
    trace_id: str = ""
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    prompt: str = ""
    completion: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    context_chunks_used: int = 0
    context_references: List[str] = field(default_factory=list)
    llm_judge_context_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "context_chunks_used": self.context_chunks_used,
            "context_references": self.context_references,
            "llm_judge_context_score": self.llm_judge_context_score,
            "metadata": self.metadata,
        }


@dataclass
class UnifiedSession:
    session_id: str = ""
    trace_ids: List[str] = field(default_factory=list)
    application_events: List[ApplicationEvent] = field(default_factory=list)
    inference_events: List[InferenceEvent] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trace_ids": self.trace_ids,
            "application_events": [e.to_dict() for e in self.application_events],
            "inference_events": [e.to_dict() for e in self.inference_events],
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }


@dataclass
class ExtrinsicMetrics:
    metrics_id: str = field(default_factory=lambda: f"em-{uuid.uuid4().hex[:8]}")
    window_start: float = 0.0
    window_end: float = 0.0
    total_sessions: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    abandoned_tasks: int = 0
    task_success_rate: float = 0.0
    user_abandoned_rate: float = 0.0
    avg_time_to_resolution_sec: float = 0.0
    cost_per_completed_interaction_usd: float = 0.0
    revenue_per_session_usd: float = 0.0
    automation_rate: float = 0.0
    error_rate: float = 0.0
    retention_lift_pct: Optional[float] = None
    total_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics_id": self.metrics_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "total_sessions": self.total_sessions,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "abandoned_tasks": self.abandoned_tasks,
            "task_success_rate": self.task_success_rate,
            "user_abandoned_rate": self.user_abandoned_rate,
            "avg_time_to_resolution_sec": self.avg_time_to_resolution_sec,
            "cost_per_completed_interaction_usd": self.cost_per_completed_interaction_usd,
            "revenue_per_session_usd": self.revenue_per_session_usd,
            "automation_rate": self.automation_rate,
            "error_rate": self.error_rate,
            "retention_lift_pct": self.retention_lift_pct,
            "total_cost_usd": self.total_cost_usd,
        }


@dataclass
class ContextualRecallMetrics:
    metrics_id: str = field(default_factory=lambda: f"crm-{uuid.uuid4().hex[:8]}")
    window_start: float = 0.0
    window_end: float = 0.0
    avg_context_chunks_used: float = 0.0
    avg_llm_judge_context_score: float = 0.0
    multi_turn_consistency_score: float = 0.0
    reference_correctness_score: float = 0.0
    sessions_with_context: int = 0
    total_inference_events: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics_id": self.metrics_id,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "avg_context_chunks_used": self.avg_context_chunks_used,
            "avg_llm_judge_context_score": self.avg_llm_judge_context_score,
            "multi_turn_consistency_score": self.multi_turn_consistency_score,
            "reference_correctness_score": self.reference_correctness_score,
            "sessions_with_context": self.sessions_with_context,
            "total_inference_events": self.total_inference_events,
        }


@dataclass
class MetricsSnapshot:
    snapshot_id: str = field(default_factory=lambda: f"snap-{uuid.uuid4().hex[:8]}")
    extrinsic: Optional[ExtrinsicMetrics] = None
    contextual: Optional[ContextualRecallMetrics] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "extrinsic": self.extrinsic.to_dict() if self.extrinsic else None,
            "contextual": self.contextual.to_dict() if self.contextual else None,
        }
