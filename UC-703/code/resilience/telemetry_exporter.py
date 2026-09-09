"""Telemetría estructurada y métricas Prometheus/Loki para recuperación."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from resilience.models_resilience import RecoveryLogEntry, ToolResult


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


class RecoveryTelemetryExporter:
    """
    Emite logs estructurados y métricas Prometheus sobre recuperación de fallos.
    """

    def __init__(self) -> None:
        self._logs: List[RecoveryLogEntry] = []
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}

    def log(
        self,
        run_id: str,
        step_id: str,
        tool_name: str,
        event: str,
        error_category: str = "",
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RecoveryLogEntry:
        entry = RecoveryLogEntry(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            event=event,
            error_category=error_category,
            message=message,
            metadata=metadata or {},
        )
        self._logs.append(entry)
        return entry

    def record_tool_result(self, result: ToolResult) -> None:
        counter_name = f'llm_recovery_tool_results_total{{status="{result.status}",tool="{result.backend}"}}'
        self._counters[counter_name] = self._counters.get(counter_name, 0) + 1
        if result.error_category:
            cat_counter = f'llm_recovery_errors_total{{category="{result.error_category}",tool="{result.backend}"}}'
            self._counters[cat_counter] = self._counters.get(cat_counter, 0) + 1
        if result.attempts:
            gauge_name = f'llm_recovery_attempts{{tool="{result.backend}"}}'
            self._gauges[gauge_name] = float(result.attempts)

    def record_retry_effectiveness(self, total_failures: int, recovered: int) -> None:
        rate = recovered / total_failures if total_failures else 0.0
        self._gauges["llm_recovery_retry_effectiveness_rate"] = rate

    def record_escalation(self, level: str) -> None:
        counter = f'llm_recovery_escalations_total{{level="{level}"}}'
        self._counters[counter] = self._counters.get(counter, 0) + 1

    def render_prometheus(self) -> str:
        lines: List[str] = []
        for name, value in self._counters.items():
            root = name.split("{")[0]
            lines.append(f"# TYPE {root} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            root = name.split("{")[0]
            lines.append(f"# TYPE {root} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)

    def get_logs(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._logs]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_count": len(self._logs),
            "counters": self._counters,
            "gauges": self._gauges,
        }
