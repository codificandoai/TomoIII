"""Immediate anomaly detection for UC-309 events and metrics."""
from __future__ import annotations

import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from models_309 import CanonicalEvent, EventType
from metrics_aggregator import MetricsAggregator


class AnomalyDetector:
    """Detect anomalies in real-time telemetry and produce in-memory recommendations."""

    def __init__(
        self,
        error_rate_threshold: float = 0.20,
        latency_ms_baseline: float = 500.0,
        token_input_baseline: int = 1000,
        steps_baseline: int = 10,
        retries_baseline: int = 3,
        loop_tool_repeats: int = 2,
    ):
        self.error_rate_threshold = error_rate_threshold
        self.latency_ms_baseline = latency_ms_baseline
        self.token_input_baseline = token_input_baseline
        self.steps_baseline = steps_baseline
        self.retries_baseline = retries_baseline
        self.loop_tool_repeats = loop_tool_repeats
        self._baseline = {
            "latency_ms": latency_ms_baseline,
            "input_tokens": token_input_baseline,
            "steps": steps_baseline,
        }

    def detect(
        self,
        events: Iterable[CanonicalEvent],
        metrics: Optional[MetricsAggregator] = None,
    ) -> List[Dict[str, Any]]:
        events = list(events)
        anomalies: List[Dict[str, Any]] = []
        now = time.time()

        # Per-trace grouping
        traces: Dict[str, List[CanonicalEvent]] = {}
        for ev in events:
            traces.setdefault(ev.trace_id, []).append(ev)

        # 1. High error rate per tool
        tool_status: Dict[str, Counter] = {}
        for ev in events:
            if ev.tool_name:
                status = "error" if ev.error or ev.tool_result_status == "error" else "success"
                tool_status.setdefault(ev.tool_name, Counter())[status] += 1
        for tool, counts in tool_status.items():
            total = sum(counts.values())
            errors = counts.get("error", 0)
            if total > 0 and errors / total > self.error_rate_threshold:
                anomalies.append({
                    "type": "high_error_rate",
                    "tool": tool,
                    "error_rate": errors / total,
                    "recommendation": f"Investigate tool '{tool}' error rate {errors/total:.2%}; consider disabling or adding HITL.",
                    "timestamp": now,
                })

        # 2. Latency / token baseline; excessive steps/retries; loops
        for ev in events:
            if ev.latency_ms and ev.latency_ms > self.latency_ms_baseline:
                anomalies.append({
                    "type": "latency_baseline_exceeded",
                    "trace_id": ev.trace_id,
                    "span_id": ev.span_id,
                    "latency_ms": ev.latency_ms,
                    "recommendation": "Latency above baseline; investigate model or tool slowness.",
                    "timestamp": now,
                })
            if ev.input_tokens > self.token_input_baseline:
                anomalies.append({
                    "type": "token_input_baseline_exceeded",
                    "trace_id": ev.trace_id,
                    "input_tokens": ev.input_tokens,
                    "recommendation": "Input tokens exceed baseline; review context bloat or token leakage.",
                    "timestamp": now,
                })
            if ev.retries > self.retries_baseline:
                anomalies.append({
                    "type": "excessive_retries",
                    "trace_id": ev.trace_id,
                    "retries": ev.retries,
                    "recommendation": "Retry storm detected; consider circuit-breaking or HITL.",
                    "timestamp": now,
                })

        for trace_id, trace_events in traces.items():
            steps = [e for e in trace_events if e.step > 0]
            if steps and max(e.step for e in steps) > self.steps_baseline:
                anomalies.append({
                    "type": "excessive_steps",
                    "trace_id": trace_id,
                    "steps": max(e.step for e in steps),
                    "recommendation": "Trace exceeds step baseline; possible reasoning loop.",
                    "timestamp": now,
                })

            tool_seq = [e.tool_name for e in trace_events if e.tool_name]
            counter = Counter(tool_seq)
            for tool, count in counter.items():
                if count > self.loop_tool_repeats:
                    anomalies.append({
                        "type": "abnormal_tool_frequency",
                        "trace_id": trace_id,
                        "tool": tool,
                        "calls": count,
                        "recommendation": f"Tool '{tool}' called {count} times; verify loop or HITL.",
                        "timestamp": now,
                    })

            # UC signals
            for ev in trace_events:
                if ev.uc300 and ev.uc300.authorized is False:
                    anomalies.append({
                        "type": "uc300_block",
                        "trace_id": trace_id,
                        "tool": ev.uc300.tool_name,
                        "recommendation": "UC-300 blocked an action; review authorization policy.",
                        "timestamp": now,
                    })
                if ev.uc290 and (ev.uc290.escalation or ev.uc290.override):
                    anomalies.append({
                        "type": "uc290_escalation_or_override",
                        "trace_id": trace_id,
                        "escalation": ev.uc290.escalation,
                        "override": ev.uc290.override,
                        "recommendation": "UC-290 escalation/override; consider HITL and dossier capture.",
                        "timestamp": now,
                    })
                if ev.uc324:
                    anomalies.append({
                        "type": "uc324_containment",
                        "trace_id": trace_id,
                        "containment": ev.uc324.containment_type,
                        "recommendation": "UC-324 containment triggered; audit quarantine.",
                        "timestamp": now,
                    })

            # Incomplete telemetry
            types = {e.event_type for e in trace_events}
            if EventType.TRACE_START not in types or (EventType.TRACE_END not in types and EventType.FINAL_OUTCOME not in types):
                anomalies.append({
                    "type": "incomplete_telemetry",
                    "trace_id": trace_id,
                    "recommendation": "Trace missing start or end event; verify agent observer integration.",
                    "timestamp": now,
                })

            # Secret leak attempts from redaction findings
            for ev in trace_events:
                for finding in (ev.redaction_findings or []):
                    if "secret" in finding.lower() or "pii" in finding.lower():
                        anomalies.append({
                            "type": "secret_leak_attempt",
                            "trace_id": trace_id,
                            "span_id": ev.span_id,
                            "finding": finding,
                            "recommendation": "Sensitive content was redacted; review source.",
                            "timestamp": now,
                        })

            # Approved vs observed action divergence
            for ev in trace_events:
                if ev.event_type == EventType.OBSERVATION and ev.observed_action_hash and ev.parent_span_id:
                    # find approved hash in same trace
                    for a in trace_events:
                        if a.event_type == EventType.UC300_AUTHORIZATION and a.span_id == ev.parent_span_id:
                            if a.uc300 and a.uc300.approved_action_hash and a.uc300.approved_action_hash != ev.observed_action_hash:
                                anomalies.append({
                                    "type": "approved_vs_observed_divergence",
                                    "trace_id": trace_id,
                                    "span_id": ev.span_id,
                                    "recommendation": "Approved action hash differs from observed action; possible TOCTOU or tampering.",
                                    "timestamp": now,
                                })

        # 3. Metrics-derived anomalies
        if metrics:
            m = metrics.to_dict()
            if m.get("latency_p95", 0) > self.latency_ms_baseline:
                anomalies.append({
                    "type": "p95_latency_above_baseline",
                    "latency_p95_ms": m["latency_p95"],
                    "recommendation": "p95 latency above baseline; scale or investigate.",
                    "timestamp": now,
                })

        return anomalies
