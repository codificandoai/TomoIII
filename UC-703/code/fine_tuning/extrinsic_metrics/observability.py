"""Observabilidad: Prometheus exporter y Loki logger para métricas extrínsecas/contextuales."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.extrinsic_metrics.models_em import (
    ContextualRecallMetrics,
    ExtrinsicMetrics,
)


@dataclass
class LokiEntry:
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    line: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "labels": self.labels,
            "line": self.line,
        }


class PrometheusExporter:
    """Exporta métricas extrínsecas y contextuales en formato Prometheus."""

    def __init__(self) -> None:
        self._gauges: Dict[str, float] = {}
        self._counters: Dict[str, int] = {}
        self._snapshots: List[Dict[str, Any]] = []

    def emit_extrinsic(self, metrics: ExtrinsicMetrics) -> None:
        prefix = "llm_extrinsic_"
        self._gauges[f"{prefix}task_success_rate"] = metrics.task_success_rate
        self._gauges[f"{prefix}user_abandoned_rate"] = metrics.user_abandoned_rate
        self._gauges[f"{prefix}avg_time_to_resolution_sec"] = metrics.avg_time_to_resolution_sec
        self._gauges[f"{prefix}cost_per_completed_interaction_usd"] = metrics.cost_per_completed_interaction_usd
        self._gauges[f"{prefix}revenue_per_session_usd"] = metrics.revenue_per_session_usd
        self._gauges[f"{prefix}automation_rate"] = metrics.automation_rate
        self._gauges[f"{prefix}error_rate"] = metrics.error_rate
        if metrics.retention_lift_pct is not None:
            self._gauges[f"{prefix}retention_lift_pct"] = metrics.retention_lift_pct
        self._counters[f"{prefix}total_sessions"] = metrics.total_sessions
        self._counters[f"{prefix}completed_tasks"] = metrics.completed_tasks
        self._counters[f"{prefix}failed_tasks"] = metrics.failed_tasks
        self._counters[f"{prefix}abandoned_tasks"] = metrics.abandoned_tasks
        self._snapshots.append({"type": "extrinsic", "metrics": metrics.to_dict()})

    def emit_contextual(self, metrics: ContextualRecallMetrics) -> None:
        prefix = "llm_contextual_"
        self._gauges[f"{prefix}avg_context_chunks_used"] = metrics.avg_context_chunks_used
        self._gauges[f"{prefix}avg_llm_judge_context_score"] = metrics.avg_llm_judge_context_score
        self._gauges[f"{prefix}multi_turn_consistency_score"] = metrics.multi_turn_consistency_score
        self._gauges[f"{prefix}reference_correctness_score"] = metrics.reference_correctness_score
        self._counters[f"{prefix}sessions_with_context"] = metrics.sessions_with_context
        self._counters[f"{prefix}total_inference_events"] = metrics.total_inference_events
        self._snapshots.append({"type": "contextual", "metrics": metrics.to_dict()})

    def render(self) -> str:
        lines: List[str] = []
        for name, value in self._counters.items():
            metric_root = name.split("{")[0]
            lines.append(f"# TYPE {metric_root} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            metric_root = name.split("{")[0]
            lines.append(f"# TYPE {metric_root} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {"counters": self._counters, "gauges": self._gauges, "snapshots": self._snapshots}


class LokiLogger:
    """Logger estructurado para Loki con correlación session_id/trace_id."""

    def __init__(self) -> None:
        self._entries: List[LokiEntry] = []

    def log(
        self,
        event: str,
        session_id: str,
        trace_id: str,
        step: str,
        status: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LokiEntry:
        line = json.dumps({
            "event": event,
            "session_id": session_id,
            "trace_id": trace_id,
            "step": step,
            "status": status,
            "timestamp": time.time(),
            "payload": payload or {},
        })
        entry = LokiEntry(
            labels={
                "event": event,
                "session_id": session_id,
                "trace_id": trace_id,
                "step": step,
                "status": status,
            },
            line=line,
        )
        self._entries.append(entry)
        return entry

    def get_entries(self) -> List[LokiEntry]:
        return list(self._entries)
