"""Capa de observabilidad para UC-322.

Proporciona:
- Métricas Prometheus (Counter, Histogram, Gauge).
- Logs estructurados para Loki (JSON con trace_id, span_id).
- Trazas OpenTelemetry-compatible (spans jerárquicos).
- Exportación de métricas en formato Prometheus text.

En modo mock (sin prometheus_client), las métricas se registran
internamente para verificación en tests.
"""
from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from prometheus_client import (
        Counter as PromCounter,
        Histogram as PromHistogram,
        Gauge as PromGauge,
        CollectorRegistry,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@dataclass
class Span:
    """Span de traza OpenTelemetry-compatible."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    agent_id: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"  # OK, ERROR, BLOCKED

    @property
    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "agent_id": self.agent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": round(self.duration, 6),
            "attributes": self.attributes,
            "status": self.status,
        }


class ObservabilityManager:
    """Gestiona métricas, logs y trazas para UC-322.

    En producción, las métricas se exponen via /metrics para Prometheus.
    Los logs se emiten a stdout en formato JSON para Loki.
    Las trazas se estructuran como spans para Tempo.
    """

    def __init__(self) -> None:
        self._spans: List[Span] = []
        self._logs: List[Dict[str, Any]] = []
        self._active_spans: Dict[str, Span] = {}

        # Métricas mock (siempre disponibles)
        self._counters: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._gauges: Dict[str, float] = {}

        # Métricas Prometheus reales (si disponibles) — registry por instancia
        if PROMETHEUS_AVAILABLE:
            self._registry = CollectorRegistry()
            self._prom_counters: Dict[str, PromCounter] = {}
            self._prom_histograms: Dict[str, PromHistogram] = {}
            self._prom_gauges: Dict[str, PromGauge] = {}
        else:
            self._registry = None

    # ─── Spans / Trazas ─────────────────────────────────────────────────

    def start_span(
        self,
        operation: str,
        agent_id: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Inicia un nuevo span de traza."""
        span = Span(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4())[:8],
            parent_span_id=parent_span_id,
            operation=operation,
            agent_id=agent_id,
            attributes=attributes or {},
        )
        self._active_spans[span.span_id] = span
        self._spans.append(span)
        return span

    def end_span(self, span_id: str, status: str = "OK") -> Span:
        """Finaliza un span."""
        span = self._active_spans.pop(span_id, None)
        if span:
            span.end_time = time.time()
            span.status = status
        return span

    def get_spans(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna los spans, opcionalmente filtrados por trace_id."""
        spans = self._spans
        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]
        return [s.to_dict() for s in spans]

    # ─── Logs estructurados (Loki) ──────────────────────────────────────

    def log(
        self,
        level: str,
        message: str,
        trace_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Emite un log estructurado en formato JSON para Loki."""
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "trace_id": trace_id,
            "agent_id": agent_id,
            **kwargs,
        }
        self._logs.append(entry)
        # En producción: print(json.dumps(entry))  # → stdout → Loki
        return entry

    def get_logs(
        self,
        level: Optional[str] = None,
        trace_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retorna logs filtrados."""
        logs = self._logs
        if level:
            logs = [l for l in logs if l["level"] == level]
        if trace_id:
            logs = [l for l in logs if l["trace_id"] == trace_id]
        return logs[-limit:]

    # ─── Métricas (Prometheus) ──────────────────────────────────────────

    def inc_counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1) -> None:
        """Incrementa un contador."""
        labels = labels or {}
        key = f"{name}:{json.dumps(labels, sort_keys=True)}"
        self._counters[name][key] += value

        if PROMETHEUS_AVAILABLE:
            if name not in self._prom_counters:
                label_names = list(labels.keys()) if labels else []
                self._prom_counters[name] = PromCounter(
                    name, f"Counter {name}", label_names, registry=self._registry
                )
            try:
                if labels:
                    self._prom_counters[name].labels(**labels).inc(value)
                else:
                    self._prom_counters[name].inc(value)
            except Exception:
                pass

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observa un valor en un histograma."""
        self._histograms[name].append(value)

        if PROMETHEUS_AVAILABLE:
            if name not in self._prom_histograms:
                label_names = list(labels.keys()) if labels else []
                self._prom_histograms[name] = PromHistogram(
                    name, f"Histogram {name}", label_names, registry=self._registry
                )
            try:
                if labels:
                    self._prom_histograms[name].labels(**labels).observe(value)
                else:
                    self._prom_histograms[name].observe(value)
            except Exception:
                pass

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Establece un gauge."""
        self._gauges[name] = value

        if PROMETHEUS_AVAILABLE:
            if name not in self._prom_gauges:
                label_names = list(labels.keys()) if labels else []
                self._prom_gauges[name] = PromGauge(
                    name, f"Gauge {name}", label_names, registry=self._registry
                )
            try:
                if labels:
                    self._prom_gauges[name].labels(**labels).set(value)
                else:
                    self._prom_gauges[name].set(value)
            except Exception:
                pass

    def get_counters(self) -> Dict[str, Dict[str, int]]:
        """Retorna los contadores mock."""
        return {name: dict(vals) for name, vals in self._counters.items()}

    def get_histograms(self) -> Dict[str, List[float]]:
        """Retorna los histogramas mock."""
        return dict(self._histograms)

    def get_gauges(self) -> Dict[str, float]:
        """Retorna los gauges mock."""
        return dict(self._gauges)

    def export_prometheus(self) -> str:
        """Exporta métricas en formato Prometheus text."""
        if PROMETHEUS_AVAILABLE and self._registry is not None:
            return generate_latest(self._registry).decode()
        # Fallback: generar texto manualmente
        lines: List[str] = []
        for name, vals in self._counters.items():
            for key, count in vals.items():
                lines.append(f"{name}{key} {count}")
        for name, values in self._histograms.items():
            if values:
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_sum {sum(values):.4f}")
        for name, value in self._gauges.items():
            lines.append(f"{name} {value}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reinicia todas las métricas, logs y trazas."""
        self._spans.clear()
        self._logs.clear()
        self._active_spans.clear()
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()
