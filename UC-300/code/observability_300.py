"""
UC-300 — Observabilidad del Secure Tool Gateway.

Logs estructurados, métricas counters/gauges y trazas para auditar
el pipeline authorize → execute.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List


class ObservabilityManager:
    """Recolecta logs, métricas y trazas del gateway."""

    def __init__(self, component: str = "uc300_stg", pipeline: str = "uc300_stg"):
        self.component = component
        self.pipeline = pipeline
        self.logs: List[Dict[str, Any]] = []
        self.metrics: Dict[str, float] = {}
        self.spans: List[Dict[str, Any]] = []

    def log(
        self,
        level: str,
        message: str,
        trace_id: str = "",
        extra: Dict[str, Any] = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "component": self.component,
            "pipeline": self.pipeline,
            "level": level,
            "message": message,
            "trace_id": trace_id,
            "extra": extra or {},
        }
        self.logs.append(entry)

    def increment(self, metric_name: str, value: float = 1.0) -> None:
        self.metrics[metric_name] = self.metrics.get(metric_name, 0.0) + value

    def gauge(self, metric_name: str, value: float) -> None:
        self.metrics[metric_name] = value

    def start_span(self, name: str, trace_id: str = "") -> Dict[str, Any]:
        span = {
            "name": name,
            "trace_id": trace_id,
            "start": time.time(),
            "end": None,
        }
        self.spans.append(span)
        return span

    def end_span(self, span: Dict[str, Any]) -> None:
        span["end"] = time.time()
        span["duration_ms"] = (span["end"] - span["start"]) * 1000

    def export_prometheus(self) -> str:
        lines = []
        for name, value in self.metrics.items():
            safe = name.replace("-", "_").replace(" ", "_")
            metric_type = "counter" if name.endswith("_total") else "gauge"
            lines.append(f"# TYPE {safe} {metric_type}")
            lines.append(
                f'{safe}{{component="{self.component}",pipeline="{self.pipeline}"}} {value}'
            )
        return "\n".join(lines) + "\n"

    def get_summary(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "log_count": len(self.logs),
            "metric_count": len(self.metrics),
            "span_count": len(self.spans),
            "metrics": self.metrics,
            "latest_logs": self.logs[-5:],
        }

    def reset(self) -> None:
        self.logs.clear()
        self.metrics.clear()
        self.spans.clear()

    def to_json(self) -> str:
        import json
        return json.dumps(
            {"logs": self.logs, "metrics": self.metrics, "spans": self.spans},
            indent=2,
            default=str,
        )
