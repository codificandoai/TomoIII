"""Métricas para auditabilidad del protocolo Contract Net (UC-269).

Intenta usar prometheus_client si está disponible; si no, implementa un
registro mínimo compatible con el formato de exposición de Prometheus para
que Grafana/Prometheus puedan scrapearlo.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


try:
    from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
    _PROMETHEUS_AVAILABLE = True
except Exception:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False


@dataclass
class _CounterState:
    value: int = 0
    labels: Dict[str, int] = field(default_factory=dict)


@dataclass
class _HistogramState:
    sum_value: float = 0.0
    count: int = 0
    buckets: List[float] = field(default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf")])
    counts: Dict[str, int] = field(default_factory=dict)


class MetricsRegistry:
    """Registro de métricas compatible con Prometheus con fallback en memoria."""

    def __init__(self, prefix: str = "contractnet") -> None:
        self.prefix = prefix
        self._counters: Dict[str, _CounterState] = {}
        self._histograms: Dict[str, _HistogramState] = {}

        if _PROMETHEUS_AVAILABLE:
            self.tasks_total = Counter(
                f"{prefix}_tasks_total", "Total tasks", ["status"]
            )
            self.proposals_total = Counter(
                f"{prefix}_proposals_total", "Total proposals received", ["agent"]
            )
            self.selection_score = Histogram(
                f"{prefix}_selection_score",
                "Score of selected proposal",
                buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
            )
            self.execution_duration_seconds = Histogram(
                f"{prefix}_execution_duration_seconds",
                "Task execution time in seconds",
            )
            self.results_total = Counter(
                f"{prefix}_results_total", "Execution results", ["status"]
            )
        else:
            # Fallback states
            self.tasks_total = None
            self.proposals_total = None
            self.selection_score = None
            self.execution_duration_seconds = None
            self.results_total = None
            self._ensure_counter("tasks_total", ["status"])
            self._ensure_counter("proposals_total", ["agent"])
            self._ensure_histogram("selection_score", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, float("inf")])
            self._ensure_histogram("execution_duration_seconds", [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, float("inf")])
            self._ensure_counter("results_total", ["status"])

    # ------------------------------------------------------------------
    # Increment / observe helpers
    # ------------------------------------------------------------------
    def inc_tasks(self, status: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.tasks_total.labels(status=status).inc()
        else:
            self._inc_counter("tasks_total", status)

    def inc_proposals(self, agent: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.proposals_total.labels(agent=agent).inc()
        else:
            self._inc_counter("proposals_total", agent)

    def observe_selection_score(self, score: float) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.selection_score.observe(score)
        else:
            self._observe_histogram("selection_score", score)

    def observe_execution_duration(self, seconds: float) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.execution_duration_seconds.observe(seconds)
        else:
            self._observe_histogram("execution_duration_seconds", seconds)

    def inc_results(self, status: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.results_total.labels(status=status).inc()
        else:
            self._inc_counter("results_total", status)

    def exposition(self) -> bytes:
        if _PROMETHEUS_AVAILABLE:
            return generate_latest(REGISTRY)
        return self._generate_fallback_exposition().encode("utf-8")

    def to_dict(self) -> Dict[str, Any]:
        if _PROMETHEUS_AVAILABLE:
            return {"mode": "prometheus_client"}
        return {
            "mode": "fallback",
            "counters": {
                name: {"total": state.value, "labels": dict(state.labels)}
                for name, state in self._counters.items()
            },
            "histograms": {
                name: {
                    "sum": state.sum_value,
                    "count": state.count,
                    "buckets": [
                        {"le": le, "count": state.counts.get(f"le_{le}", 0)}
                        for le in state.buckets
                    ],
                }
                for name, state in self._histograms.items()
            },
        }

    # ------------------------------------------------------------------
    # Fallback internals
    # ------------------------------------------------------------------
    def _ensure_counter(self, name: str, _labels: List[str]) -> None:
        if name not in self._counters:
            self._counters[name] = _CounterState()

    def _ensure_histogram(self, name: str, buckets: List[float]) -> None:
        if name not in self._histograms:
            self._histograms[name] = _HistogramState(buckets=buckets)

    def _inc_counter(self, name: str, label: str) -> None:
        self._ensure_counter(name, [label])
        state = self._counters[name]
        state.value += 1
        state.labels[label] = state.labels.get(label, 0) + 1

    def _observe_histogram(self, name: str, value: float) -> None:
        state = self._histograms[name]
        state.sum_value += value
        state.count += 1
        for bucket in state.buckets:
            if value <= bucket:
                key = f"le_{bucket}"
                state.counts[key] = state.counts.get(key, 0) + 1

    def _generate_fallback_exposition(self) -> str:
        lines: List[str] = []
        for name, state in self._counters.items():
            full = f"{self.prefix}_{name}"
            lines.append(f"# HELP {full} Total {name}")
            lines.append(f"# TYPE {full} counter")
            if state.labels:
                for label, val in sorted(state.labels.items()):
                    lines.append(f'{full}{{status="{label}"}} {val}')
            lines.append(f"{full} {state.value}")
        for name, state in self._histograms.items():
            full = f"{self.prefix}_{name}"
            lines.append(f"# HELP {full} Histogram {name}")
            lines.append(f"# TYPE {full} histogram")
            cumulative = 0
            for bucket in state.buckets:
                cumulative += state.counts.get(f"le_{bucket}", 0)
                lines.append(f'{full}_bucket{{le="{bucket}"}} {cumulative}')
            lines.append(f"{full}_sum {state.sum_value}")
            lines.append(f"{full}_count {state.count}")
        return "\n".join(lines) + "\n"


# Instancia global usada por la API y el manager
METRICS = MetricsRegistry()
