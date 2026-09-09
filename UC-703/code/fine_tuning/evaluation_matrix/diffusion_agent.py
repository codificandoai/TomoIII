"""Difusión de aprendizajes: publica reportes, actualiza gates y alimenta re-entrenamiento."""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from fine_tuning.evaluation_matrix.models_cem import CEMReport, EvaluationSignal


class DiffusionAgent:
    """
    Propaga hallazgos a la organización: reportes markdown versionados,
    actualización de thresholds de gates, y señales para re-entrenamiento.
    """

    def __init__(self, git_mode: bool = True) -> None:
        self.git_mode = git_mode
        self._reports: Dict[str, str] = {}
        self._gate_updates: List[Dict[str, Any]] = []
        self._retrain_signals: List[Dict[str, Any]] = []

    def publish_report(self, report: CEMReport) -> str:
        md = self._to_markdown(report)
        digest = hashlib.sha256(md.encode()).hexdigest()[:16]
        if self.git_mode:
            uri = f"git://cem-reports/{report.report_id}-{digest}.md"
        else:
            uri = f"wiki://cem-reports/{report.report_id}-{digest}"
        self._reports[report.report_id] = uri
        report.wiki_uri = uri
        return uri

    def update_gate_thresholds(
        self,
        gate_name: str,
        failed_signals: List[EvaluationSignal],
    ) -> Dict[str, Any]:
        updates: Dict[str, float] = {}
        for sig in failed_signals:
            # Lower threshold slightly to tighten gate on repeated failures
            updates[sig.metric_name] = round(sig.threshold * 0.95, 3)
        update = {"gate": gate_name, "timestamp": time.time(), "thresholds": updates}
        self._gate_updates.append(update)
        return update

    def request_retrain(
        self,
        report: CEMReport,
        reason: str,
    ) -> Dict[str, Any]:
        signal = {
            "report_id": report.report_id,
            "model_version": report.model_version,
            "checkpoint_id": report.checkpoint_id,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._retrain_signals.append(signal)
        return signal

    def _to_markdown(self, report: CEMReport) -> str:
        lines = [
            f"# Continuous Evaluation Matrix Report: {report.report_id}",
            "",
            f"- **Run ID**: {report.run_id}",
            f"- **Model Version**: {report.model_version}",
            f"- **Checkpoint ID**: {report.checkpoint_id}",
            f"- **Overall Passed**: {report.overall_passed}",
            f"- **Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## Signals ({len(report.signals)})",
            "",
        ]
        for sig in report.signals:
            icon = "✅" if sig.passed else "❌"
            lines.append(f"- {icon} `{sig.metric_name}` = {sig.value} (threshold {sig.threshold}) [{sig.source}]")
        if report.human_reviews:
            lines.append("")
            lines.append(f"## Human Reviews ({len(report.human_reviews)})")
            for r in report.human_reviews:
                lines.append(f"- {r.reviewer_role}: correctness={r.correctness}, safety={r.safety}")
        if report.failure_clusters:
            lines.append("")
            lines.append(f"## Failure Clusters ({len(report.failure_clusters)})")
            for c in report.failure_clusters:
                lines.append(f"- {c.pattern}: count={c.count}, proposed_action={c.proposed_action}")
        if report.risk_signals:
            lines.append("")
            lines.append(f"## Risk Signals ({len(report.risk_signals)})")
            for rs in report.risk_signals:
                lines.append(f"- {rs.name} ({rs.severity}) [{rs.category}]")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reports": self._reports,
            "gate_updates": self._gate_updates,
            "retrain_signals": self._retrain_signals,
        }
