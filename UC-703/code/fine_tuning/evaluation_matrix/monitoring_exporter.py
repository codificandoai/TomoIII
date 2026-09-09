"""Observabilidad para Continuous Evaluation Matrix: Prometheus + Loki."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.evaluation_matrix.models_cem import EvaluationSignal


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


class MonitoringExporterAgent:
    """
    Exporta señales de evaluación a Prometheus y logs estructurados a Loki.
    """

    def __init__(self) -> None:
        self._gauges: Dict[str, float] = {}
        self._counters: Dict[str, int] = {}
        self._entries: List[LokiEntry] = []

    def emit_signal(self, signal: EvaluationSignal) -> None:
        metric_name = f'llm_cem_{{metric="{signal.metric_name}",source="{signal.source}"}}'
        self._gauges[metric_name] = signal.value
        status_counter = "llm_cem_evaluations_total"
        self._counters[status_counter] = self._counters.get(status_counter, 0) + 1
        if signal.passed:
            passed_counter = "llm_cem_passed_total"
            self._counters[passed_counter] = self._counters.get(passed_counter, 0) + 1
        else:
            failed_counter = "llm_cem_failed_total"
            self._counters[failed_counter] = self._counters.get(failed_counter, 0) + 1

        line = json.dumps(signal.to_dict())
        self._entries.append(LokiEntry(
            labels={
                "metric": signal.metric_name,
                "source": signal.source,
                "passed": str(signal.passed),
            },
            line=line,
        ))

    def render_prometheus(self) -> str:
        lines: List[str] = []
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            root = name.split("{")[0]
            lines.append(f"# TYPE {root} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)

    def get_logs(self) -> List[LokiEntry]:
        return list(self._entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counters": self._counters,
            "gauges": self._gauges,
            "log_count": len(self._entries),
        }
