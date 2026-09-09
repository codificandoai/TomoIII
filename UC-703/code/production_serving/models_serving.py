"""Modelos para arquitectura de producción de serving de LLM."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class GuardrailResult:
    pii_detected: bool = False
    toxicity_detected: bool = False
    jailbreak_detected: bool = False
    blocked: bool = False
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pii_detected": self.pii_detected,
            "toxicity_detected": self.toxicity_detected,
            "jailbreak_detected": self.jailbreak_detected,
            "blocked": self.blocked,
            "reasons": self.reasons,
        }


@dataclass
class InferenceRequest:
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    principal_id: str = ""
    prompt: str = ""
    model_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "principal_id": self.principal_id,
            "prompt": self.prompt,
            "model_id": self.model_id,
            "params": self.params,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }


@dataclass
class InferenceResponse:
    response_id: str = field(default_factory=lambda: f"res-{uuid.uuid4().hex[:8]}")
    request_id: str = ""
    session_id: str = ""
    model_id: str = ""
    generated_text: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    guardrails: GuardrailResult = field(default_factory=GuardrailResult)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "model_id": self.model_id,
            "generated_text": self.generated_text,
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
            "guardrails": self.guardrails.to_dict(),
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class ServingSession:
    session_id: str = field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}")
    principal_id: str = ""
    model_id: str = ""
    channel: str = ""  # api, chat, crm, erp, websocket
    created_at: float = field(default_factory=time.time)
    requests: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "principal_id": self.principal_id,
            "model_id": self.model_id,
            "channel": self.channel,
            "created_at": self.created_at,
            "requests": self.requests,
        }


@dataclass
class TelemetryRecord:
    record_id: str = field(default_factory=lambda: f"tel-{uuid.uuid4().hex[:8]}")
    request_id: str = ""
    trace_id: str = ""
    principal_id: str = ""
    model_id: str = ""
    prompt: str = ""
    response: str = ""
    latency_ms: float = 0.0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    guardrails: GuardrailResult = field(default_factory=GuardrailResult)
    timestamp: float = field(default_factory=time.time)
    origin: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "principal_id": self.principal_id,
            "model_id": self.model_id,
            "prompt": self.prompt,
            "response": self.response,
            "latency_ms": self.latency_ms,
            "token_usage": self.token_usage.to_dict(),
            "guardrails": self.guardrails.to_dict(),
            "timestamp": self.timestamp,
            "origin": self.origin,
        }


@dataclass
class FeedbackSignal:
    feedback_id: str = field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:8]}")
    request_id: str = ""
    session_id: str = ""
    principal_id: str = ""
    signal_type: str = ""  # rating, thumbs_up, thumbs_down, human_escalation
    value: Any = None
    comment: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "principal_id": self.principal_id,
            "signal_type": self.signal_type,
            "value": self.value,
            "comment": self.comment,
            "timestamp": self.timestamp,
        }


@dataclass
class ReEvaluationResult:
    eval_id: str = field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:8]}")
    request_id: str = ""
    judge_score: float = 0.0
    regression: bool = False
    flagged: bool = False
    reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "request_id": self.request_id,
            "judge_score": self.judge_score,
            "regression": self.regression,
            "flagged": self.flagged,
            "reasons": self.reasons,
            "timestamp": self.timestamp,
        }
