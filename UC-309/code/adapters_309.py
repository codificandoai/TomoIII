"""Provider-independent adapters for LangSmith, LangFuse and LangGraph payloads."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from models_309 import CanonicalEvent, EventType, ModelCompletionMeta, ModelRequestMeta, Outcome, make_span_id, make_trace_id


def _now_ns() -> int:
    return int(time.time() * 1e9)


def _safe(d: Any) -> Dict[str, Any]:
    return d if isinstance(d, dict) else {}


def _gen_trace_id(v: Optional[str] = None) -> str:
    return v or make_trace_id()


def _gen_span_id(v: Optional[str] = None) -> str:
    return v or make_span_id()


class AdapterError(ValueError):
    pass


def from_langsmith(payload: Dict[str, Any]) -> List[CanonicalEvent]:
    """Map a LangSmith Run/Trace payload to canonical UC-309 events.

    Canonical source remains UC-309; this is a best-effort normalization.
    """
    if not isinstance(payload, dict):
        raise AdapterError("LangSmith payload must be a dict")
    run = _safe(payload)
    trace_id = _gen_trace_id(run.get("trace_id") or run.get("run_id") or run.get("id"))
    session_id = run.get("session_id") or run.get("project_id")
    agent_id = run.get("name") or "langsmith_adapter"
    agent_version = run.get("run_type") or "unknown"

    events: List[CanonicalEvent] = []
    parent_map: Dict[str, str] = {}

    # Root start
    events.append(CanonicalEvent(
        trace_id=trace_id,
        span_id=trace_id,
        parent_span_id=None,
        execution_id=run.get("execution_order"),
        session_id=session_id,
        agent_id=agent_id,
        agent_version=agent_version,
        step=0,
        event_type=EventType.TRACE_START,
        timestamp_ns=_now_ns(),
    ))

    # Inputs -> model request
    inputs = _safe(run.get("inputs"))
    if inputs:
        events.append(CanonicalEvent(
            trace_id=trace_id,
            span_id=_gen_span_id(),
            parent_span_id=trace_id,
            execution_id=run.get("execution_order"),
            session_id=session_id,
            agent_id=agent_id,
            agent_version=agent_version,
            step=1,
            event_type=EventType.MODEL_REQUEST,
            timestamp_ns=_now_ns(),
            model_request_meta=ModelRequestMeta(
                model=run.get("extra", {}).get("metadata", {}).get("model"),
                model_provider=run.get("extra", {}).get("metadata", {}).get("provider"),
                max_tokens=run.get("extra", {}).get("metadata", {}).get("max_tokens"),
                temperature=run.get("extra", {}).get("metadata", {}).get("temperature"),
                tools_declared=list(inputs.get("tools", {}).keys()) if isinstance(inputs.get("tools"), dict) else None,
            ),
        ))

    # Child events / steps
    children = run.get("child_runs") or []
    for idx, child in enumerate(children, start=2):
        child = _safe(child)
        span_id = _gen_span_id(child.get("id"))
        parent_span_id = _gen_span_id(child.get("parent_run_id")) if child.get("parent_run_id") else trace_id
        parent_map[span_id] = parent_span_id
        tool = child.get("name") or "unknown"
        error = child.get("error")
        events.append(CanonicalEvent(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            execution_id=run.get("execution_order"),
            session_id=session_id,
            agent_id=agent_id,
            agent_version=agent_version,
            step=idx,
            event_type=EventType.TOOL_CALL if child.get("run_type") == "tool" else EventType.OBSERVATION,
            timestamp_ns=_now_ns(),
            tool_name=tool,
            tool_result_status="error" if error else "success",
            observation_summary=str(child.get("outputs"))[:500] if child.get("outputs") else None,
            latency_ms=child.get("runtime_ms"),
            input_tokens=child.get("extra", {}).get("usage", {}).get("prompt_tokens") or 0,
            output_tokens=child.get("extra", {}).get("usage", {}).get("completion_tokens") or 0,
            error=error,
        ))

    # Outputs -> model completion
    outputs = _safe(run.get("outputs"))
    if outputs:
        events.append(CanonicalEvent(
            trace_id=trace_id,
            span_id=_gen_span_id(),
            parent_span_id=trace_id,
            execution_id=run.get("execution_order"),
            session_id=session_id,
            agent_id=agent_id,
            agent_version=agent_version,
            step=len(children) + 2,
            event_type=EventType.MODEL_COMPLETION,
            timestamp_ns=_now_ns(),
            model_completion_meta=ModelCompletionMeta(
                model=run.get("extra", {}).get("metadata", {}).get("model"),
                finish_reason="stop" if outputs else "unknown",
                tool_calls_proposed=list(_safe(outputs.get("tool_calls")).keys()) if isinstance(outputs.get("tool_calls"), dict) else None,
            ),
        ))

    # Final outcome
    events.append(CanonicalEvent(
        trace_id=trace_id,
        span_id=trace_id,
        parent_span_id=None,
        execution_id=run.get("execution_order"),
        session_id=session_id,
        agent_id=agent_id,
        agent_version=agent_version,
        step=len(children) + 3,
        event_type=EventType.FINAL_OUTCOME,
        timestamp_ns=_now_ns(),
        final_outcome=Outcome.FAILURE if run.get("error") else Outcome.SUCCESS,
        error=run.get("error"),
    ))
    return events


def from_langfuse(payload: Dict[str, Any]) -> List[CanonicalEvent]:
    """Map a LangFuse trace/observation payload to canonical UC-309 events."""
    if not isinstance(payload, dict):
        raise AdapterError("LangFuse payload must be a dict")
    trace = _safe(payload)
    trace_id = _gen_trace_id(trace.get("traceId") or trace.get("id"))
    agent_id = trace.get("name") or trace.get("projectId") or "langfuse_adapter"
    agent_version = trace.get("release") or "unknown"
    session_id = trace.get("sessionId")

    events: List[CanonicalEvent] = []
    events.append(CanonicalEvent(
        trace_id=trace_id,
        span_id=trace_id,
        parent_span_id=None,
        session_id=session_id,
        agent_id=agent_id,
        agent_version=agent_version,
        step=0,
        event_type=EventType.TRACE_START,
        timestamp_ns=_now_ns(),
    ))

    observations = trace.get("observations") or []
    for idx, obs in enumerate(observations, start=1):
        obs = _safe(obs)
        span_id = _gen_span_id(obs.get("id"))
        parent_span_id = _gen_span_id(obs.get("parentObservationId")) if obs.get("parentObservationId") else trace_id
        otype = obs.get("type", "OBSERVATION")
        etype = EventType.TOOL_CALL if otype == "SPAN" and obs.get("name") else EventType.OBSERVATION
        events.append(CanonicalEvent(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            session_id=session_id,
            agent_id=agent_id,
            agent_version=agent_version,
            step=idx,
            event_type=etype,
            timestamp_ns=_now_ns(),
            tool_name=obs.get("name"),
            observation_summary=str(obs.get("output"))[:500] if obs.get("output") else None,
            latency_ms=obs.get("endTime") and obs.get("startTime") and _diff_ms(obs["startTime"], obs["endTime"]),
            input_tokens=obs.get("usage", {}).get("input") or 0,
            output_tokens=obs.get("usage", {}).get("output") or 0,
            tool_result_status="error" if obs.get("statusMessage") else "success",
            error=obs.get("statusMessage"),
        ))

    events.append(CanonicalEvent(
        trace_id=trace_id,
        span_id=trace_id,
        parent_span_id=None,
        session_id=session_id,
        agent_id=agent_id,
        agent_version=agent_version,
        step=len(observations) + 1,
        event_type=EventType.FINAL_OUTCOME,
        timestamp_ns=_now_ns(),
        final_outcome=Outcome.SUCCESS if trace.get("scores") and all(s.get("value", 1) >= 0 for s in trace["scores"]) else Outcome.UNKNOWN,
    ))
    return events


def from_langgraph(payload: Dict[str, Any]) -> List[CanonicalEvent]:
    """Map a LangGraph state/checkpoint payload to canonical UC-309 events."""
    if not isinstance(payload, dict):
        raise AdapterError("LangGraph payload must be a dict")
    graph = _safe(payload)
    thread_id = graph.get("thread_id") or graph.get("configurable", {}).get("thread_id")
    trace_id = _gen_trace_id(thread_id)
    agent_id = graph.get("graph_id") or "langgraph_adapter"
    agent_version = graph.get("checkpoint_id") or "unknown"

    events: List[CanonicalEvent] = []
    events.append(CanonicalEvent(
        trace_id=trace_id,
        span_id=trace_id,
        parent_span_id=None,
        execution_id=thread_id,
        agent_id=agent_id,
        agent_version=agent_version,
        step=0,
        event_type=EventType.TRACE_START,
        timestamp_ns=_now_ns(),
    ))

    messages = graph.get("channel_values", {}).get("messages") or graph.get("messages") or []
    for idx, msg in enumerate(messages, start=1):
        msg = _safe(msg)
        mtype = msg.get("type") or msg.get("role") or "message"
        if mtype == "ai":
            etype = EventType.MODEL_COMPLETION
        elif mtype == "tool":
            etype = EventType.TOOL_RESULT
        elif mtype == "human":
            etype = EventType.MODEL_REQUEST
        else:
            etype = EventType.OBSERVATION
        tool_calls = msg.get("tool_calls") or []
        events.append(CanonicalEvent(
            trace_id=trace_id,
            span_id=_gen_span_id(),
            parent_span_id=trace_id,
            execution_id=thread_id,
            agent_id=agent_id,
            agent_version=agent_version,
            step=idx,
            event_type=etype,
            timestamp_ns=_now_ns(),
            tool_name=tool_calls[0].get("name") if tool_calls else None,
            tool_call_id=tool_calls[0].get("id") if tool_calls else None,
            action_proposed=tool_calls[0].get("args") if tool_calls else None,
            observation_summary=str(msg.get("content"))[:500] if msg.get("content") else None,
            input_tokens=msg.get("usage_metadata", {}).get("input_tokens") or 0,
            output_tokens=msg.get("usage_metadata", {}).get("output_tokens") or 0,
        ))

    events.append(CanonicalEvent(
        trace_id=trace_id,
        span_id=trace_id,
        parent_span_id=None,
        execution_id=thread_id,
        agent_id=agent_id,
        agent_version=agent_version,
        step=len(messages) + 1,
        event_type=EventType.FINAL_OUTCOME,
        timestamp_ns=_now_ns(),
        final_outcome=Outcome.SUCCESS,
    ))
    return events


def _diff_ms(start: Any, end: Any) -> Optional[float]:
    try:
        return (float(end) - float(start)) / 1e6
    except Exception:
        return None
