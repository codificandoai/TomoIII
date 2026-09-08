"""Metrics aggregation and Prometheus-format exporter for UC-309."""
from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from models_309 import CanonicalEvent, EventType, Outcome

LATENCY_BUCKETS = [10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0]
STEPS_BUCKETS = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]
DURATION_BUCKETS = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]


class MetricsAggregator:
    def __init__(self):
        self._lock = False
        # Counters keyed by metric name + label set
        self.counters: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.histograms: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        self.gauges: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._latencies: List[float] = []
        self._steps: List[int] = []
        self._durations: List[float] = []
        self._last_update = time.time()

    def reset(self):
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()
        self._latencies.clear()
        self._steps.clear()
        self._durations.clear()

    def update(self, events: Iterable[CanonicalEvent]):
        events = list(events)
        # Group by trace
        traces: Dict[str, List[CanonicalEvent]] = defaultdict(list)
        for ev in events:
            traces[ev.trace_id].append(ev)

        for ev in events:
            agent_lbl = self._labels(agent_id=ev.agent_id or "unknown", agent_version=ev.agent_version or "unknown")

            # Tool calls
            if ev.event_type in (EventType.TOOL_CALL, EventType.TOOL_RESULT, EventType.OBSERVATION) and ev.tool_name:
                status = "success" if not ev.error and ev.tool_result_status != "error" else "error"
                tool_lbl = self._labels(tool_name=ev.tool_name, status=status, **agent_lbl)
                self._inc("uc309_tool_calls_total", tool_lbl)
                if status == "error":
                    self._inc("uc309_tool_errors_total", tool_lbl)
                if ev.latency_ms is not None:
                    self._observe("uc309_tool_latency_ms", tool_lbl, ev.latency_ms, LATENCY_BUCKETS)
                    self._latencies.append(ev.latency_ms)

            # Tokens
            if ev.input_tokens:
                self._inc("uc309_tokens_total", {**agent_lbl, "type": "input"}, ev.input_tokens)
            if ev.output_tokens:
                self._inc("uc309_tokens_total", {**agent_lbl, "type": "output"}, ev.output_tokens)
            if ev.estimated_cost_usd:
                self._add("uc309_estimated_cost_usd_total", agent_lbl, ev.estimated_cost_usd)

            # Retries / loops
            if ev.retries:
                self._inc("uc309_retries_total", agent_lbl, ev.retries)
            if ev.loop_count:
                self._inc("uc309_loops_total", agent_lbl, ev.loop_count)

            # UC signals
            if ev.uc300:
                if ev.uc300.authorized is False:
                    self._inc("uc309_uc300_blocks_total", self._labels(tool_name=ev.uc300.tool_name or "unknown", **agent_lbl))
                if ev.uc300.toctou_check is False:
                    self._inc("uc309_uc300_toctou_total", agent_lbl)
            if ev.uc290:
                if ev.uc290.escalation:
                    self._inc("uc309_uc290_escalations_total", agent_lbl)
                if ev.uc290.override:
                    self._inc("uc309_uc290_overrides_total", agent_lbl)
            if ev.uc324:
                self._inc("uc309_uc324_containments_total", agent_lbl)

            # Redaction findings
            for finding in (ev.redaction_findings or []):
                reason = finding.split(":")[0]
                self._inc("uc309_redaction_findings_total", self._labels(reason=reason, **agent_lbl))

        for trace_id, trace_events in traces.items():
            sorted_events = sorted(trace_events, key=lambda e: (e.step, e.timestamp_ns))
            starts = [e for e in sorted_events if e.event_type == EventType.TRACE_START]
            ends = [e for e in sorted_events if e.event_type in (EventType.TRACE_END, EventType.FINAL_OUTCOME)]
            if not starts or not ends:
                self._inc("uc309_telemetry_incomplete_total", {})

            if starts and ends:
                duration_ms = (ends[-1].timestamp_ns - starts[0].timestamp_ns) / 1e6
                self._durations.append(duration_ms)
                agent_lbl = self._labels(agent_id=starts[0].agent_id or "unknown", agent_version=starts[0].agent_version or "unknown")
                self._observe("uc309_task_duration_seconds", agent_lbl, duration_ms / 1000.0, DURATION_BUCKETS)

            if ends:
                end = ends[-1]
                agent_id = end.agent_id or "unknown"
                agent_version = end.agent_version or "unknown"
                agent_lbl = self._labels(agent_id=agent_id, agent_version=agent_version)
                label_str = self._label_str(agent_lbl)

                # Tasa de éxito: outcome explícito
                outcome = end.final_outcome or Outcome.UNKNOWN
                success = 1.0 if outcome == Outcome.SUCCESS else 0.0

                # Tasa de alineación: éxito sin bloques, escalaciones, contención ni errores
                aligned = success
                if aligned:
                    for ev in sorted_events:
                        if ev.event_type in (
                            EventType.UC300_BLOCK,
                            EventType.UC300_TOCTOU,
                            EventType.UC290_ESCALATION,
                            EventType.UC324_CONTAINMENT,
                            EventType.ERROR,
                        ):
                            aligned = 0.0
                            break
                        if ev.uc300 and ev.uc300.authorized is False:
                            aligned = 0.0
                            break
                        if ev.uc290 and (ev.uc290.override or ev.uc290.escalation):
                            aligned = 0.0
                            break

                self._inc("uc309_traces_total", agent_lbl)
                if success:
                    self._inc("uc309_success_total", agent_lbl)
                if aligned:
                    self._inc("uc309_alignment_total", agent_lbl)

                # Mantener gauge por ventana actual (último valor) y acumulado
                self.gauges["uc309_success_rate"][label_str] = success
                self.gauges["uc309_alignment_rate"][label_str] = aligned
                self.gauges["uc309_success_alignment_delta"][label_str] = round(success - aligned, 6)

            # Steps per task from max step number
            if sorted_events:
                steps = max(e.step for e in sorted_events)
                self._steps.append(steps)
                agent_lbl = self._labels(agent_id=sorted_events[0].agent_id or "unknown", agent_version=sorted_events[0].agent_version or "unknown")
                self._observe("uc309_steps_total", agent_lbl, steps, STEPS_BUCKETS)

        # Active traces (traces with start but no end)
        active = sum(1 for tid, evs in traces.items() if any(e.event_type == EventType.TRACE_START for e in evs) and not any(e.event_type in (EventType.TRACE_END, EventType.FINAL_OUTCOME) for e in evs))
        self.gauges["uc309_active_traces"][""] = float(active)

        # Quantile gauges (p50/p95/p99)
        if self._latencies:
            for p in (50, 95, 99):
                self.gauges[f"uc309_latency_p{p}_ms"][""] = self._percentile(self._latencies, p / 100.0)
        if self._steps:
            for p in (50, 95, 99):
                self.gauges[f"uc309_steps_p{p}"][""] = self._percentile(self._steps, p / 100.0)
        if self._durations:
            for p in (50, 95, 99):
                self.gauges[f"uc309_task_duration_p{p}_seconds"][""] = self._percentile(self._durations, p / 100.0) / 1000.0

        # Averages
        if self._steps:
            self.gauges["uc309_avg_steps"][""] = sum(self._steps) / len(self._steps)
        if self._latencies:
            self.gauges["uc309_avg_latency_ms"][""] = sum(self._latencies) / len(self._latencies)

        # Tasas agregadas de éxito y alineación por agente
        totals = dict(self.counters.get("uc309_traces_total", {}))
        successes = dict(self.counters.get("uc309_success_total", {}))
        alignments = dict(self.counters.get("uc309_alignment_total", {}))
        for label_str, total in totals.items():
            if total > 0:
                self.gauges["uc309_success_rate_avg"][label_str] = successes.get(label_str, 0.0) / total
                self.gauges["uc309_alignment_rate_avg"][label_str] = alignments.get(label_str, 0.0) / total
                self.gauges["uc309_success_alignment_delta_avg"][label_str] = round(
                    self.gauges["uc309_success_rate_avg"][label_str]
                    - self.gauges["uc309_alignment_rate_avg"][label_str],
                    6,
                )

        self._last_update = time.time()

    def _labels(self, **kwargs) -> Dict[str, str]:
        # Strict controlled cardinality: no trace/session id
        allowed = {"agent_id", "agent_version", "tool_name", "status", "type", "outcome", "reason"}
        return {k: str(v)[:48] for k, v in kwargs.items() if k in allowed}

    def _label_str(self, labels: Dict[str, str]) -> str:
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))

    def _inc(self, name: str, labels: Dict[str, str], amount: int = 1):
        self.counters[name][self._label_str(labels)] += amount

    def _add(self, name: str, labels: Dict[str, str], amount: float):
        self.gauges[name][self._label_str(labels)] += amount

    def _observe(self, name: str, labels: Dict[str, str], value: float, buckets: List[float]):
        ls = self._label_str(labels)
        self.histograms[name][ls].append(value)

    def _percentile(self, data: List[float], q: float) -> float:
        if not data:
            return 0.0
        s = sorted(data)
        k = (len(s) - 1) * q
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return s[int(k)]
        return s[f] * (c - k) + s[c] * (k - f)

    def render_prometheus(self) -> str:
        lines: List[str] = []

        # Counters
        for name, series in sorted(self.counters.items()):
            lines.append(f"# HELP {name} Count")
            lines.append(f"# TYPE {name} counter")
            for labels, value in sorted(series.items()):
                label = "{" + labels + "}" if labels else ""
                lines.append(f"{name}{label} {value}")

        # Histograms (computed on render)
        for name, series in sorted(self.histograms.items()):
            lines.append(f"# HELP {name} Histogram")
            lines.append(f"# TYPE {name} histogram")
            buckets = LATENCY_BUCKETS
            if "steps" in name:
                buckets = STEPS_BUCKETS
            elif "duration" in name:
                buckets = DURATION_BUCKETS
            for labels, values in sorted(series.items()):
                label_prefix = "{" + labels + ("," if labels else "")
                for b in buckets:
                    le = f'{label_prefix}le="{b}"' + "}" if labels else f'{{le="{b}"}}'
                    count = sum(1 for v in values if v <= b)
                    lines.append(f"{name}_bucket{le} {count}")
                # +Inf
                le_inf = f'{label_prefix}le="+Inf"' + "}" if labels else f'{{le="+Inf"}}'
                lines.append(f"{name}_bucket{le_inf} {len(values)}")
                sum_lbl = label_prefix[:-1] if labels else ""
                sum_lbl = label_prefix + "}" if labels else "{}"
                # fix sum and count
                sum_lbl = "{" + labels + "}" if labels else "{}"
                lines.append(f"{name}_sum{sum_lbl} {sum(values):.6f}")
                lines.append(f"{name}_count{sum_lbl} {len(values)}")

        # Gauges
        for name, series in sorted(self.gauges.items()):
            lines.append(f"# HELP {name} Gauge")
            lines.append(f"# TYPE {name} gauge")
            for labels, value in sorted(series.items()):
                label = "{" + labels + "}" if labels else ""
                lines.append(f"{name}{label} {value:.6f}")

        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counters": {k: dict(v) for k, v in self.counters.items()},
            "gauges": {k: dict(v) for k, v in self.gauges.items()},
            "last_update": self._last_update,
            "latency_p50": self._percentile(self._latencies, 0.5) if self._latencies else 0.0,
            "latency_p95": self._percentile(self._latencies, 0.95) if self._latencies else 0.0,
            "latency_p99": self._percentile(self._latencies, 0.99) if self._latencies else 0.0,
        }
