"""
UC-308 — Observabilidad operacional y exportador Prometheus propio.

No requiere prometheus_client. Las métricas se almacenan en memoria con
labels serializadas de forma segura para texto Prometheus.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class ObservabilityManager:
    """
    Recolecta logs, trazas y métricas con labels. Expone en formato Prometheus.
    """

    def __init__(self, component: str = "uc308_drift", pipeline: str = "uc308"):
        self.component = component
        self.pipeline = pipeline
        self.logs: List[Dict[str, Any]] = []
        self.spans: List[Dict[str, Any]] = []
        # (name, label_frozen) -> value
        self.counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
        self.gauges: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
        # histograms: name -> {labels -> [values]}
        self.histograms: Dict[str, Dict[Tuple[Tuple[str, str], ...], List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.histogram_buckets = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def log(
        self,
        level: str,
        message: str,
        trace_id: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.logs.append({
            "timestamp": time.time(),
            "component": self.component,
            "pipeline": self.pipeline,
            "level": level,
            "message": message,
            "trace_id": trace_id,
            "extra": extra or {},
        })

    def start_span(self, name: str, trace_id: str = "") -> Dict[str, Any]:
        span = {"name": name, "trace_id": trace_id, "start": time.time(), "end": None}
        self.spans.append(span)
        return span

    def end_span(self, span: Dict[str, Any]) -> None:
        span["end"] = time.time()
        span["duration_ms"] = (span["end"] - span["start"]) * 1000

    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = (self._safe_metric_name(name), self._freeze_labels(labels or {}))
        self.counters[key] = self.counters.get(key, 0.0) + value

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = (self._safe_metric_name(name), self._freeze_labels(labels or {}))
        self.gauges[key] = value

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        name = self._safe_metric_name(name)
        self.histograms[name][self._freeze_labels(labels or {})].append(value)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "pipeline": self.pipeline,
            "log_count": len(self.logs),
            "span_count": len(self.spans),
            "counter_count": len(self.counters),
            "gauge_count": len(self.gauges),
            "histogram_count": len(self.histograms),
            "latest_logs": self.logs[-5:],
        }

    def export_prometheus(self) -> str:
        """Exporta métricas en formato Prometheus text."""
        lines: List[str] = []
        # Counters
        counter_names: Dict[str, List[str]] = defaultdict(list)
        for (name, label_tuple), value in self.counters.items():
            counter_names[name].append(self._format_sample(name, label_tuple, value))
        for name in sorted(counter_names):
            lines.append(f"# TYPE {name} counter")
            lines.extend(counter_names[name])

        # Gauges
        gauge_names: Dict[str, List[str]] = defaultdict(list)
        for (name, label_tuple), value in self.gauges.items():
            gauge_names[name].append(self._format_sample(name, label_tuple, value))
        for name in sorted(gauge_names):
            lines.append(f"# TYPE {name} gauge")
            lines.extend(gauge_names[name])

        # Histograms
        for name in sorted(self.histograms.keys()):
            lines.append(f"# TYPE {name} histogram")
            for label_tuple, values in self.histograms[name].items():
                total = sum(values)
                count = len(values)
                for bucket in self.histogram_buckets:
                    bucket_value = sum(1 for v in values if v <= bucket)
                    bucket_labels = list(label_tuple) + [("le", str(bucket))]
                    lines.append(self._format_sample(f"{name}_bucket", tuple(bucket_labels), bucket_value))
                lines.append(self._format_sample(f"{name}_sum", label_tuple, total))
                lines.append(self._format_sample(f"{name}_count", label_tuple, count))

        return "\n".join(lines) + "\n" if lines else ""

    def reset(self) -> None:
        self.logs.clear()
        self.spans.clear()
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_metric_name(name: str) -> str:
        # Prometheus metric names deben coincidir [a-zA-Z_:][a-zA-Z0-9_:]*
        safe = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
        if safe and safe[0].isdigit():
            safe = "_" + safe
        return safe or "uc308_metric"

    @staticmethod
    def _safe_label_name(name: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if safe and safe[0].isdigit():
            safe = "_" + safe
        return safe or "label"

    @staticmethod
    def _escape_label_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _freeze_labels(self, labels: Dict[str, str]) -> Tuple[Tuple[str, str], ...]:
        return tuple(
            (self._safe_label_name(k), self._escape_label_value(str(v)))
            for k, v in sorted(labels.items())
        )

    def _format_sample(self, name: str, label_tuple: Tuple[Tuple[str, str], ...], value: float) -> str:
        if not label_tuple:
            return f"{name} {self._fmt(value)}"
        labels = ",".join(f'{k}="{v}"' for k, v in label_tuple)
        return f"{name}{{{labels}}} {self._fmt(value)}"

    @staticmethod
    def _fmt(value: float) -> str:
        if value == int(value):
            return str(int(value))
        return f"{value:.6g}"
