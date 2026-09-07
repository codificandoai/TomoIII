"""
UC-325 — Observabilidad para el Motor de Razonamiento Autorreflexivo.

Gestiona métricas, logs estructurados y trazas (spans) para UC-325.
Compatible con Prometheus (counters, histograms, gauges), Loki (logs JSON)
y OpenTelemetry (spans con trace_id).

Sigue el patrón de UC-322/code/observability.py.
"""

from typing import List, Dict, Optional, Any
import time
import uuid
from dataclasses import dataclass, field


# Intentar importar prometheus_client, fallback a counters internos
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
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
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"

    @property
    def duration(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration, 2),
            "attributes": self.attributes,
            "status": self.status,
        }


class ObservabilityManager:
    """
    Gestiona métricas, logs y trazas para UC-325.

    Provee:
    - Counters: reasoning_rounds_total, hallucinations_detected_total,
      quality_gates_passed_total, convergence_achieved_total.
    - Histograms: reasoning_duration_ms, rounds_to_convergence.
    - Gauges: active_hypotheses, confidence_score.
    - Logs estructurados con nivel, mensaje, trace_id.
    - Spans OpenTelemetry-compatible.
    """

    def __init__(self):
        self._counters: Dict[str, Dict[str, int]] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}
        self._logs: List[Dict[str, Any]] = []
        self._spans: Dict[str, Span] = {}

        if PROMETHEUS_AVAILABLE:
            self._prom_counters: Dict[str, Counter] = {}
            self._prom_histograms: Dict[str, Histogram] = {}
            self._prom_gauges: Dict[str, Gauge] = {}

    def start_span(
        self,
        operation: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Inicia un span de traza."""
        span = Span(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4())[:12],
            parent_span_id=parent_span_id,
            operation=operation,
            attributes=attributes or {},
        )
        self._spans[span.span_id] = span
        return span

    def end_span(self, span_id: str, status: str = "OK") -> Optional[Span]:
        """Finaliza un span."""
        span = self._spans.get(span_id)
        if span:
            span.end_time = time.time()
            span.status = status
        return span

    def get_spans(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna spans, opcionalmente filtrados por trace_id."""
        spans = list(self._spans.values())
        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]
        return [s.to_dict() for s in spans]

    def log(
        self,
        level: str,
        message: str,
        trace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Registra un log estructurado."""
        entry = {
            "timestamp": time.time(),
            "level": level.upper(),
            "message": message,
            "trace_id": trace_id,
            **kwargs,
        }
        self._logs.append(entry)
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
            logs = [l for l in logs if l.get("level") == level.upper()]
        if trace_id:
            logs = [l for l in logs if l.get("trace_id") == trace_id]
        return logs[-limit:]

    def inc_counter(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        value: int = 1,
    ) -> None:
        """Incrementa un counter."""
        key = name
        label_key = str(sorted(labels.items())) if labels else "default"

        if key not in self._counters:
            self._counters[key] = {}
        if label_key not in self._counters[key]:
            self._counters[key][label_key] = 0

        self._counters[key][label_key] += value

        if PROMETHEUS_AVAILABLE:
            if key not in self._prom_counters:
                label_names = list(labels.keys()) if labels else []
                self._prom_counters[key] = Counter(
                    key, f"UC-325 counter: {key}", label_names
                )
            if labels:
                self._prom_counters[key].labels(**labels).inc(value)
            else:
                self._prom_counters[key].inc(value)

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Registra un valor en un histograma."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

        if PROMETHEUS_AVAILABLE:
            if name not in self._prom_histograms:
                label_names = list(labels.keys()) if labels else []
                self._prom_histograms[name] = Histogram(
                    name, f"UC-325 histogram: {name}", label_names
                )
            if labels:
                self._prom_histograms[name].labels(**labels).observe(value)
            else:
                self._prom_histograms[name].observe(value)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Establece un valor gauge."""
        self._gauges[name] = value

        if PROMETHEUS_AVAILABLE:
            if name not in self._prom_gauges:
                label_names = list(labels.keys()) if labels else []
                self._prom_gauges[name] = Gauge(
                    name, f"UC-325 gauge: {name}", label_names
                )
            if labels:
                self._prom_gauges[name].labels(**labels).set(value)
            else:
                self._prom_gauges[name].set(value)

    def get_counters(self) -> Dict[str, Dict[str, int]]:
        """Retorna todos los counters."""
        return dict(self._counters)

    def get_histograms(self) -> Dict[str, List[float]]:
        """Retorna todos los histogramas."""
        return dict(self._histograms)

    def get_gauges(self) -> Dict[str, float]:
        """Retorna todos los gauges."""
        return dict(self._gauges)

    def export_prometheus(self) -> str:
        """Exporta métricas en formato Prometheus text."""
        if PROMETHEUS_AVAILABLE:
            return generate_latest().decode("utf-8")

        lines = []
        for name, label_vals in self._counters.items():
            for label_key, value in label_vals.items():
                lines.append(f"# TYPE {name} counter")
                lines.append(f'{name}{{labels="{label_key}"}} {value}')

        for name, values in self._histograms.items():
            if values:
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_sum {sum(values):.4f}")

        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value:.4f}")

        return "\n".join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumen de observabilidad."""
        return {
            "counters": self.get_counters(),
            "histograms": {
                k: {
                    "count": len(v),
                    "sum": round(sum(v), 4) if v else 0,
                    "avg": round(sum(v) / len(v), 4) if v else 0,
                }
                for k, v in self._histograms.items()
            },
            "gauges": self.get_gauges(),
            "total_logs": len(self._logs),
            "total_spans": len(self._spans),
            "error_logs": sum(1 for l in self._logs if l.get("level") == "ERROR"),
        }

    def reset(self) -> None:
        """Resetea todo el estado de observabilidad."""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()
        self._logs.clear()
        self._spans.clear()
