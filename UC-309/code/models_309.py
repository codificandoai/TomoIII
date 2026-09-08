"""Canonical, provider-independent agentic observability models for UC-309."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import secrets
import time
from enum import Enum
from typing import Any, Dict, List, Optional


def _canonical_json(value: Any) -> str:
    """Stable JSON for hashing."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)


class EventType(str, Enum):
    TRACE_START = "trace_start"
    TRACE_END = "trace_end"
    THOUGHT_SUMMARY = "thought_summary"
    MODEL_REQUEST = "model_request"
    MODEL_COMPLETION = "model_completion"
    ACTION_PROPOSED = "action_proposed"
    UC300_AUTHORIZATION = "uc300_authorization"
    UC300_BLOCK = "uc300_block"
    UC300_TOCTOU = "uc300_toctou"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    OBSERVATION = "observation"
    UC290_DECISION = "uc290_decision"
    UC290_OVERRIDE = "uc290_override"
    UC290_ESCALATION = "uc290_escalation"
    UC324_CONTAINMENT = "uc324_containment"
    ERROR = "error"
    FINAL_OUTCOME = "final_outcome"


class Outcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    CONTAINED = "contained"
    ESCALATED = "escalated"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


@dataclasses.dataclass(frozen=True)
class ModelRequestMeta:
    model: Optional[str] = None
    model_provider: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    tools_declared: Optional[List[str]] = None
    # No prompt content.

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelRequestMeta":
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})


@dataclasses.dataclass(frozen=True)
class ModelCompletionMeta:
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    tool_calls_proposed: Optional[List[str]] = None
    # No full completion text.

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelCompletionMeta":
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})


@dataclasses.dataclass(frozen=True)
class UC300Auth:
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    policy_verdict: Optional[str] = None
    authorized: Optional[bool] = None
    toctou_check: Optional[bool] = None
    block_reason: Optional[str] = None
    approved_action_hash: Optional[str] = None
    authorization_latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UC300Auth":
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})


@dataclasses.dataclass(frozen=True)
class UC290Decision:
    decision_id: Optional[str] = None
    risk_score: Optional[float] = None
    override: Optional[bool] = None
    escalation: Optional[bool] = None
    human_in_the_loop: Optional[bool] = None
    decision_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UC290Decision":
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})


@dataclasses.dataclass(frozen=True)
class UC324Containment:
    containment_type: Optional[str] = None
    contained_action: Optional[str] = None
    quarantine_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UC324Containment":
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})


@dataclasses.dataclass(frozen=False)
class CanonicalEvent:
    # Identifiers
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    # Execution context
    execution_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_version: Optional[str] = None
    # Step and event
    step: int = 0
    event_type: EventType = EventType.OBSERVATION
    timestamp_ns: int = dataclasses.field(default_factory=lambda: int(time.time() * 1e9))
    # Model metadata (no raw prompt/completion)
    model_request_meta: Optional[ModelRequestMeta] = None
    model_completion_meta: Optional[ModelCompletionMeta] = None
    # Reasoning (structured summary only)
    structured_reasoning_summary: Optional[str] = None
    action_proposed: Optional[Dict[str, Any]] = None
    action_proposed_hash: Optional[str] = None
    # UC sub-events
    uc300: Optional[UC300Auth] = None
    uc290: Optional[UC290Decision] = None
    uc324: Optional[UC324Containment] = None
    # Observation / tool
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_result_status: Optional[str] = None
    observation_summary: Optional[str] = None
    observed_action_hash: Optional[str] = None
    # Errors / outcome
    error: Optional[str] = None
    final_outcome: Optional[Outcome] = None
    # Evidence / dossier
    evidence_refs: Optional[List[str]] = None
    dossier_refs: Optional[List[str]] = None
    # Telemetry
    latency_ms: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: Optional[float] = None
    retries: int = 0
    loop_count: int = 0
    # Labels (controlled cardinality)
    labels: Optional[Dict[str, str]] = None
    # Privacy / audit
    redaction_findings: Optional[List[str]] = None
    pii_pseudonyms: Optional[Dict[str, str]] = None
    allowlist_violations: Optional[List[str]] = None
    # Hash chain
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None

    def __post_init__(self):
        if self.event_hash is None:
            self.event_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = _canonical_json({
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "step": self.step,
            "event_type": self.event_type.value,
            "timestamp_ns": self.timestamp_ns,
            "action_proposed_hash": self.action_proposed_hash,
            "observed_action_hash": self.observed_action_hash,
            "previous_event_hash": self.previous_event_hash,
            "redacted_digest": _canonical_json(self.redaction_findings or []),
        })
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["event_type"] = self.event_type.value
        if self.model_request_meta:
            d["model_request_meta"] = self.model_request_meta.to_dict()
        if self.model_completion_meta:
            d["model_completion_meta"] = self.model_completion_meta.to_dict()
        if self.uc300:
            d["uc300"] = self.uc300.to_dict()
        if self.uc290:
            d["uc290"] = self.uc290.to_dict()
        if self.uc324:
            d["uc324"] = self.uc324.to_dict()
        if self.final_outcome:
            d["final_outcome"] = self.final_outcome.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalEvent":
        d = dict(d)
        d["event_type"] = EventType(d.get("event_type", "observation"))
        if d.get("model_request_meta"):
            d["model_request_meta"] = ModelRequestMeta.from_dict(d["model_request_meta"])
        if d.get("model_completion_meta"):
            d["model_completion_meta"] = ModelCompletionMeta.from_dict(d["model_completion_meta"])
        if d.get("uc300"):
            d["uc300"] = UC300Auth.from_dict(d["uc300"])
        if d.get("uc290"):
            d["uc290"] = UC290Decision.from_dict(d["uc290"])
        if d.get("uc324"):
            d["uc324"] = UC324Containment.from_dict(d["uc324"])
        if d.get("final_outcome"):
            d["final_outcome"] = Outcome(d["final_outcome"])
        if "event_hash" in d:
            d.pop("event_hash")
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})

    def has_private_reasoning(self) -> bool:
        """Detect if any field contains a raw chain-of-thought that should not be stored."""
        forbidden_keys = ("chain_of_thought", "raw_thought", "internal_thought", "reasoning_text")
        raw = _canonical_json(self.to_dict()).lower()
        return any(k in raw for k in forbidden_keys) or bool(self.structured_reasoning_summary and "raw:" in self.structured_reasoning_summary.lower())


def make_trace_id() -> str:
    return secrets.token_hex(16)


def make_span_id() -> str:
    return secrets.token_hex(8)
