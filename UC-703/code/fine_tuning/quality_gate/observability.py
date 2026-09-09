"""Observabilidad (Prometheus + Loki-like logs) y publisher Wiki.js/Git."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    """Emite métricas Prometheus para el quality gate."""

    def __init__(self) -> None:
        self._metrics: Dict[str, Any] = {}
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}

    def record(self, run_id: str, metrics: Dict[str, float], status: str) -> None:
        self._metrics[run_id] = {"metrics": metrics, "status": status}
        for key, value in metrics.items():
            metric_name = f"llm_eval_{key}"
            self._gauges[f'{metric_name}{{run_id="{run_id}"}}'] = value
        self._counters["llm_eval_runs_total"] = self._counters.get("llm_eval_runs_total", 0) + 1
        if status == "passed":
            self._counters["llm_eval_passed_total"] = self._counters.get("llm_eval_passed_total", 0) + 1
        elif status == "blocked":
            self._counters["llm_eval_blocked_total"] = self._counters.get("llm_eval_blocked_total", 0) + 1

    def record_baseline_delta(self, run_id: str, deltas: Dict[str, float]) -> None:
        for key, value in deltas.items():
            self._gauges[f'llm_eval_baseline_delta{{metric="{key}",run_id="{run_id}"}}'] = value

    def render(self) -> str:
        lines: List[str] = []
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name.replace('{', '').split()[0]} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {"counters": self._counters, "gauges": self._gauges, "runs": self._metrics}


class LokiLogger:
    """Logger estructurado simulado para ingestion en Loki."""

    def __init__(self) -> None:
        self._entries: List[LokiEntry] = []

    def log(
        self,
        event: str,
        run_id: str,
        step: str,
        status: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LokiEntry:
        line = json.dumps({
            "event": event,
            "run_id": run_id,
            "step": step,
            "status": status,
            "payload": payload or {},
        })
        entry = LokiEntry(
            labels={"event": event, "run_id": run_id, "step": step},
            line=line,
        )
        self._entries.append(entry)
        return entry

    def get_entries(self) -> List[LokiEntry]:
        return list(self._entries)


class WikiPublisher:
    """Publicador simulado de reportes markdown a Wiki.js / Git."""

    def __init__(self, git_mode: bool = True) -> None:
        self.git_mode = git_mode
        self._published: Dict[str, str] = {}

    def publish(self, report_id: str, markdown: str) -> Dict[str, str]:
        # Simulate content-addressed URI
        digest = hashlib.sha256(markdown.encode()).hexdigest()[:16]
        if self.git_mode:
            uri = f"git://quality-gate-reports/{report_id}-{digest}.md"
        else:
            uri = f"wiki://quality-gate-reports/{report_id}-{digest}"
        self._published[report_id] = uri
        return {"uri": uri, "digest": digest}

    def generate_markdown(
        self,
        report_id: str,
        model_version: str,
        dataset_id: str,
        status: str,
        quantitative: Dict[str, Any],
        qualitative: Dict[str, Any],
        baseline: Dict[str, Any],
        approvals: Dict[str, Any],
        findings: List[str],
    ) -> str:
        lines = [
            f"# Quality Gate Report: {report_id}",
            "",
            f"- **Model version**: {model_version}",
            f"- **Dataset**: {dataset_id}",
            f"- **Status**: {status}",
            f"- **Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Quantitative Metrics",
            "",
            "```json",
            json.dumps(quantitative, indent=2),
            "```",
            "",
            "## Qualitative Summary",
            "",
            "```json",
            json.dumps(qualitative, indent=2),
            "```",
            "",
            "## Baseline Comparison",
            "",
            "```json",
            json.dumps(baseline, indent=2),
            "```",
            "",
            "## Cross-Team Approval",
            "",
            "```json",
            json.dumps(approvals, indent=2),
            "```",
            "",
            "## Findings",
            "",
        ]
        for f in findings:
            lines.append(f"- {f}")
        return "\n".join(lines)
