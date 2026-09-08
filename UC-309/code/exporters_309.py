"""Simulated/file-only exporters for Loki (JSON Lines), Tempo (OTLP-like) and Prometheus."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, List

from models_309 import CanonicalEvent, EventType
from metrics_aggregator import MetricsAggregator


def _ts_ns(dt: Any) -> int:
    if isinstance(dt, (int, float)):
        return int(dt)
    return int(time.time() * 1e9)


def to_loki_lines(events: Iterable[CanonicalEvent]) -> List[str]:
    """Export canonical events as JSON lines suitable for Loki ingestion."""
    lines: List[str] = []
    for ev in events:
        # Labels are low-cardinality; trace/session IDs live inside the JSON line
        line = {
            "ts": ev.timestamp_ns,
            "level": "error" if ev.error else "info",
            "event_type": ev.event_type.value,
            "agent_id": ev.agent_id or "unknown",
            "agent_version": ev.agent_version or "unknown",
            "tool_name": ev.tool_name or "none",
            "message": json.dumps(ev.to_dict(), default=str, ensure_ascii=True),
        }
        lines.append(json.dumps(line, default=str, ensure_ascii=True))
    return lines


def to_tempo_spans(events: Iterable[CanonicalEvent]) -> List[Dict[str, Any]]:
    """Export canonical events as OTLP-like spans for Tempo/OpenTelemetry."""
    events = list(events)
    spans: List[Dict[str, Any]] = []
    for ev in events:
        end_ns = ev.timestamp_ns
        start_ns = end_ns - int((ev.latency_ms or 0) * 1e6) if ev.latency_ms else end_ns
        status = "ERROR" if ev.error or ev.tool_result_status == "error" else "OK"
        if ev.final_outcome and ev.final_outcome.value in ("failure", "blocked", "contained", "escalated"):
            status = "ERROR"
        span = {
            "traceId": ev.trace_id,
            "spanId": ev.span_id,
            "parentSpanId": ev.parent_span_id,
            "operationName": ev.event_type.value,
            "startTimeUnixNano": start_ns,
            "durationNano": max(1, end_ns - start_ns),
            "status": {"code": status},
            "attributes": _span_attributes(ev),
        }
        spans.append(span)
    return spans


def _span_attributes(ev: CanonicalEvent) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {
        "agent.id": ev.agent_id,
        "agent.version": ev.agent_version,
        "step": ev.step,
        "tool.name": ev.tool_name,
        "tool.result.status": ev.tool_result_status,
        "error": ev.error,
        "input.tokens": ev.input_tokens,
        "output.tokens": ev.output_tokens,
        "latency_ms": ev.latency_ms,
        "estimated_cost_usd": ev.estimated_cost_usd,
        "retries": ev.retries,
        "loop_count": ev.loop_count,
    }
    if ev.uc300:
        attrs["uc300.authorized"] = ev.uc300.authorized
        attrs["uc300.policy_verdict"] = ev.uc300.policy_verdict
        attrs["uc300.toctou_check"] = ev.uc300.toctou_check
    if ev.uc290:
        attrs["uc290.escalation"] = ev.uc290.escalation
        attrs["uc290.override"] = ev.uc290.override
    if ev.uc324:
        attrs["uc324.containment_type"] = ev.uc324.containment_type
    return {k: v for k, v in attrs.items() if v is not None}


def to_prometheus_text(metrics: MetricsAggregator) -> str:
    """Render aggregated metrics in Prometheus exposition format."""
    return metrics.render_prometheus()


class Exporter:
    """Convenience wrapper to produce local artifacts without network side effects."""

    def __init__(self, metrics: MetricsAggregator):
        self.metrics = metrics

    def export_loki_file(self, events: Iterable[CanonicalEvent], path: str):
        with open(path, "w", encoding="utf-8") as f:
            for line in to_loki_lines(events):
                f.write(line + "\n")

    def export_tempo_file(self, events: Iterable[CanonicalEvent], path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_tempo_spans(events), f, default=str, ensure_ascii=True, indent=2)

    def export_prometheus_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(to_prometheus_text(self.metrics))
