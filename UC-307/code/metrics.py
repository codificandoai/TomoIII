"""Métricas Prometheus para UC-307 con fallback en memoria.

Reutiliza el patrón de UC-269 para que el servidor funcione incluso si
`prometheus_client` no está instalado, manteniendo la interfaz compatible con
Grafana/Prometheus.
"""
from __future__ import annotations

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
    buckets: List[float] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)


class MetricsRegistry:
    """Registro de métricas de evaluación/evolución de agentes autónomos."""

    def __init__(self, prefix: str = "uc307") -> None:
        self.prefix = prefix
        self._counters: Dict[str, _CounterState] = {}
        self._histograms: Dict[str, _HistogramState] = {}

        if _PROMETHEUS_AVAILABLE:
            # Nivel 1: tareas totales con resultado
            self.tasks_total = Counter(
                f"{prefix}_tasks_total", "Total de tareas evaluadas", ["status"]
            )
            # Nivel 2: puntuación de calidad (escala 1..5)
            self.quality_score = Histogram(
                f"{prefix}_quality_score",
                "Puntuación de calidad del resultado (1..5)",
                buckets=[1, 2, 3, 4, 5],
            )
            # Nivel 3: eficiencia
            self.tokens_consumed = Counter(f"{prefix}_tokens_consumed_total", "Tokens de LLM consumidos")
            self.tool_calls_total = Counter(f"{prefix}_tool_calls_total", "Llamadas a herramientas")
            self.execution_latency = Histogram(
                f"{prefix}_execution_latency_seconds",
                "Latencia de extremo a extremo",
                buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            )
            # Decisión del orquestador
            self.decisions_total = Counter(
                f"{prefix}_decisions_total", "Decisiones del orquestador", ["action"]
            )
            # Fitness del agente
            self.fitness_score = Histogram(
                f"{prefix}_fitness_score",
                "Fitness combinado del agente",
                buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            )
        else:
            self.tasks_total = None
            self.quality_score = None
            self.tokens_consumed = None
            self.tool_calls_total = None
            self.execution_latency = None
            self.decisions_total = None
            self.fitness_score = None
            self._ensure_counter("tasks_total", ["status"])
            self._ensure_histogram("quality_score", [1, 2, 3, 4, 5, float("inf")])
            self._ensure_counter("tokens_consumed_total", [])
            self._ensure_counter("tool_calls_total", [])
            self._ensure_histogram("execution_latency_seconds", [0.5, 1.0, 2.5, 5.0, 10.0, 30.0, float("inf")])
            self._ensure_counter("decisions_total", ["action"])
            self._ensure_histogram("fitness_score", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, float("inf")])

    # ------------------------------------------------------------------
    # API pública de registro
    # ------------------------------------------------------------------
    def record_task(self, status: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.tasks_total.labels(status=status).inc()
        else:
            self._inc_counter("tasks_total", status)

    def record_quality(self, score: float) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.quality_score.observe(score)
        else:
            self._observe_histogram("quality_score", score)

    def record_efficiency(self, tokens: int, tool_calls: int, latency: float) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.tokens_consumed.inc(tokens)
            self.tool_calls_total.inc(tool_calls)
            self.execution_latency.observe(latency)
        else:
            self._inc_counter("tokens_consumed_total", "", n=tokens)
            self._inc_counter("tool_calls_total", "", n=tool_calls)
            self._observe_histogram("execution_latency_seconds", latency)

    def record_decision(self, action: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.decisions_total.labels(action=action).inc()
        else:
            self._inc_counter("decisions_total", action)

    def record_fitness(self, fitness: float) -> None:
        if _PROMETHEUS_AVAILABLE:
            self.fitness_score.observe(fitness)
        else:
            self._observe_histogram("fitness_score", fitness)

    def record_evaluation(self, status: str, quality: float, fitness: float, decision: str, tokens: int, tool_calls: int, latency: float) -> None:
        """Registra todos los pasos de una evaluación en una sola llamada."""
        self.record_task(status)
        self.record_quality(quality)
        self.record_fitness(fitness)
        self.record_decision(decision)
        self.record_efficiency(tokens, tool_calls, latency)

    # ------------------------------------------------------------------
    # Exposición
    # ------------------------------------------------------------------
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
                        {"le": bucket, "count": state.counts.get(f"le_{bucket}", 0)}
                        for bucket in state.buckets
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

    def _inc_counter(self, name: str, label: str, n: int = 1) -> None:
        self._ensure_counter(name, [label])
        state = self._counters[name]
        state.value += n
        if label:
            state.labels[label] = state.labels.get(label, 0) + n

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
            lines.append(f"# HELP {full} Counter {name}")
            lines.append(f"# TYPE {full} counter")
            for label, val in sorted(state.labels.items()):
                lines.append(f'{full}{{action="{label}"}} {val}' if "decisions" in name else f'{full}{{status="{label}"}} {val}')
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


METRICS = MetricsRegistry()
