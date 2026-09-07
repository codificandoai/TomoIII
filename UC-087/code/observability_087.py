"""
UC-087 — Observabilidad de MLSecOps.

Logs estructurados, métricas y trazas para auditar decisiones de seguridad ML.
"""

import time
import json
from typing import Dict, Any, List


class ObservabilityManager:
    """
    Recolecta logs, métricas y trazas del guardian de seguridad ML. Exporta
métricas Prometheus si se solicita.
    """

    def __init__(self, component: str = "uc087_mlsecops", pipeline: str = "uc087_mlsecops"):
        self.component = component
        self.pipeline = pipeline
        self.logs: List[Dict[str, Any]] = []
        self.metrics: Dict[str, float] = {}
        self.spans: List[Dict[str, Any]] = []

    def log(self, level: str, message: str, trace_id: str = "", extra: Dict[str, Any] = None):
        entry = {
            "timestamp": time.time(),
            "component": self.component,
            "level": level,
            "message": message,
            "trace_id": trace_id,
            "extra": extra or {},
        }
        self.logs.append(entry)

    def increment(self, metric_name: str, value: float = 1.0):
        self.metrics[metric_name] = self.metrics.get(metric_name, 0.0) + value

    def gauge(self, metric_name: str, value: float):
        self.metrics[metric_name] = value

    def start_span(self, name: str, trace_id: str = "") -> Dict[str, Any]:
        span = {"name": name, "trace_id": trace_id, "start": time.time(), "end": None}
        self.spans.append(span)
        return span

    def end_span(self, span: Dict[str, Any]):
        span["end"] = time.time()

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

    def reset(self):
        self.logs.clear()
        self.metrics.clear()
        self.spans.clear()

    def to_json(self) -> str:
        return json.dumps({
            "logs": self.logs,
            "metrics": self.metrics,
            "spans": self.spans,
        }, indent=2, default=str)
