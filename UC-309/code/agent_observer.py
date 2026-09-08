"""Agentic observation context manager and decorator (separation of concerns)."""
from __future__ import annotations

import functools
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

from models_309 import CanonicalEvent, EventType, Outcome, make_span_id


class AgenticObservationContext:
    """Context manager for a single trace step. Records action/observation lifecycle."""

    def __init__(self, ingest: Callable[[CanonicalEvent], None], trace_id: str, parent_span_id: Optional[str], step: int, agent_id: Optional[str] = None, agent_version: Optional[str] = None):
        self.ingest = ingest
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.step = step
        self.agent_id = agent_id
        self.agent_version = agent_version
        self.span_id = make_span_id()
        self.start = time.time()
        self.action: Optional[Dict[str, Any]] = None

    def propose_action(self, action: Dict[str, Any], summary: Optional[str] = None):
        self.action = action
        ev = CanonicalEvent(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            step=self.step,
            event_type=EventType.ACTION_PROPOSED,
            action_proposed=action,
            action_proposed_hash=self._hash_action(action),
            structured_reasoning_summary=summary,
            timestamp_ns=int(self.start * 1e9),
        )
        self.ingest(ev)

    def observe(self, result: Any, error: Optional[str] = None, summary: Optional[str] = None, tokens: int = 0):
        elapsed = (time.time() - self.start) * 1000.0
        observed = {"action": self.action, "result": result}
        ev = CanonicalEvent(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            step=self.step,
            event_type=EventType.OBSERVATION,
            observation_summary=summary or (str(result)[:500] if not error else None),
            tool_result_status="error" if error else "success",
            observed_action_hash=self._hash_action(self.action) if self.action else None,
            latency_ms=elapsed,
            output_tokens=tokens,
            error=error,
            timestamp_ns=int(time.time() * 1e9),
        )
        self.ingest(ev)
        return ev

    @staticmethod
    def _hash_action(action: Any) -> str:
        import hashlib, json
        payload = json.dumps(action, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@contextmanager
def observe_step(ingest: Callable[[CanonicalEvent], None], trace_id: str, parent_span_id: Optional[str] = None, step: int = 1, agent_id: Optional[str] = None, agent_version: Optional[str] = None):
    ctx = AgenticObservationContext(ingest, trace_id, parent_span_id, step, agent_id, agent_version)
    try:
        yield ctx
    except Exception as exc:
        ctx.observe(result=None, error=str(exc), summary="step_failed")
        raise


def observe_function(ingest: Callable[[CanonicalEvent], None], agent_id: Optional[str] = None, agent_version: Optional[str] = None):
    """Decorator to instrument a function as an observation span."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import uuid
            trace_id = str(uuid.uuid4())
            span_id = make_span_id()
            start = time.time()
            error: Optional[str] = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                ev = CanonicalEvent(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=None,
                    agent_id=agent_id or "observed",
                    agent_version=agent_version or "unknown",
                    step=1,
                    event_type=EventType.TOOL_CALL,
                    tool_name=func.__name__,
                    tool_result_status="error" if error else "success",
                    latency_ms=(time.time() - start) * 1000.0,
                    error=error,
                    timestamp_ns=int(time.time() * 1e9),
                )
                ingest(ev)
        return wrapper
    return decorator
