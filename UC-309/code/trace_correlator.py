"""Trace correlation, reconstruction and validation for UC-309."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from models_309 import CanonicalEvent, EventType
from trace_store import TraceStore


def _hash_action(action: Any) -> str:
    return hashlib.sha256(_canonical_json(action).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)


def reconstruct_trace(store: TraceStore, trace_id: str, role: Optional[str] = None) -> List[CanonicalEvent]:
    """Return chronologically ordered events for a trace."""
    events = store.get_trace(trace_id, role=role)
    return sorted(events, key=lambda e: (e.step, e.timestamp_ns))


class TraceValidation:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.issues: List[str] = []
        self.divergences: List[Dict[str, Any]] = []
        self.missing_start = False
        self.missing_end = False
        self.broken_parents: List[str] = []
        self.actions_without_observations: List[int] = []
        self.loop_detected = False
        self.loop_details: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "valid": not self.issues,
            "issues": self.issues,
            "divergences": self.divergences,
            "missing_start": self.missing_start,
            "missing_end": self.missing_end,
            "broken_parents": self.broken_parents,
            "actions_without_observations": self.actions_without_observations,
            "loop_detected": self.loop_detected,
            "loop_details": self.loop_details,
        }


def validate_trace(store: TraceStore, trace_id: str, role: Optional[str] = None) -> Tuple[List[CanonicalEvent], TraceValidation]:
    """Reconstruct and validate a trace."""
    events = reconstruct_trace(store, trace_id, role=role)
    report = TraceValidation(trace_id)

    if not events:
        report.issues.append("trace_empty")
        return events, report

    # Start/end
    types = {e.event_type for e in events}
    if EventType.TRACE_START not in types:
        report.missing_start = True
        report.issues.append("missing_trace_start")
    if EventType.TRACE_END not in types and EventType.FINAL_OUTCOME not in types:
        report.missing_end = True
        report.issues.append("missing_trace_end_or_final_outcome")

    # Parent spans
    span_ids = {e.span_id for e in events}
    for ev in events:
        if ev.parent_span_id and ev.parent_span_id not in span_ids and ev.parent_span_id != ev.trace_id:
            report.broken_parents.append(ev.parent_span_id)
            report.issues.append(f"broken_parent_span:{ev.parent_span_id}")

    # Action without observation and hash divergence (correlate by span_id)
    action_spans: Dict[str, Dict[str, Any]] = {}
    observation_spans: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        if ev.event_type == EventType.ACTION_PROPOSED and ev.span_id:
            action_spans[ev.span_id] = {
                "step": ev.step,
                "action_hash": ev.action_proposed_hash or _hash_action(ev.action_proposed),
                "proposed": ev.action_proposed,
            }
        if ev.event_type == EventType.OBSERVATION and ev.span_id:
            observation_spans[ev.span_id] = {
                "step": ev.step,
                "observed_hash": ev.observed_action_hash,
                "observation": ev.observation_summary,
            }

    for span_id, a in action_spans.items():
        if span_id not in observation_spans:
            report.actions_without_observations.append(a["step"])
            report.issues.append(f"action_without_observation:span_{span_id}")
            continue
        obs = observation_spans[span_id]
        # If both hashes present and differ, it is a divergence
        if a["action_hash"] and obs["observed_hash"] and a["action_hash"] != obs["observed_hash"]:
            report.divergences.append({
                "span_id": span_id,
                "step": a["step"],
                "approved_action_hash": a["action_hash"],
                "observed_action_hash": obs["observed_hash"],
                "type": "approved_vs_observed_action_divergence",
            })
            report.issues.append(f"action_divergence:span_{span_id}")

    # Loops: repeated tool calls or repeated reasoning within the same trace
    tool_seq = [e.tool_name for e in events if e.tool_name]
    counter = Counter(tool_seq)
    repeated = {k: v for k, v in counter.items() if v > 2}
    if repeated:
        report.loop_detected = True
        report.loop_details["repeated_tools"] = repeated
        report.issues.append(f"loop_repeated_tools:{repeated}")

    summaries = [e.structured_reasoning_summary for e in events if e.structured_reasoning_summary]
    if summaries:
        summary_counter = Counter(summaries)
        repeats = {k: v for k, v in summary_counter.items() if v > 1}
        if repeats:
            report.loop_detected = True
            report.loop_details["repeated_summaries"] = {k[:40]: v for k, v in repeats.items()}
            report.issues.append("loop_repeated_reasoning")

    # Hash-chain integrity
    for i in range(1, len(events)):
        prev = events[i - 1]
        cur = events[i]
        if cur.previous_event_hash and cur.previous_event_hash != prev.event_hash:
            report.issues.append(f"hash_chain_broken:step_{cur.step}")

    return events, report
