"""QualityGateController: orquesta la puerta de calidad pre-producción."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fine_tuning.quality_gate.cross_team_approval import CrossTeamApprovalGate
from fine_tuning.quality_gate.dataset_loader import DatasetLoader
from fine_tuning.quality_gate.evaluators import (
    BaselineComparator,
    QualitativeEvaluator,
    QuantitativeEvaluator,
)
from fine_tuning.quality_gate.models_quality import (
    CrossTeamApproval,
    EvalDataset,
    QualityGateReport,
)
from fine_tuning.quality_gate.observability import LokiLogger, PrometheusExporter, WikiPublisher


class QualityGateController:
    """
    Orquesta la puerta de calidad innegociable pre-producción.

    Flujo:
        1. load_dataset
        2. evaluate_quantitatively
        3. evaluate_qualitatively
        4. compare_baseline
        5. si falla -> status=blocked
        6. publish_report
        7. request_cross_team_approval -> awaiting_approval
        8. submit_signature / reject
        9. approved -> status=approved (se libera despliegue)
    """

    def __init__(
        self,
        dataset_loader: Optional[DatasetLoader] = None,
        quantitative: Optional[QuantitativeEvaluator] = None,
        qualitative: Optional[QualitativeEvaluator] = None,
        comparator: Optional[BaselineComparator] = None,
        prometheus: Optional[PrometheusExporter] = None,
        loki: Optional[LokiLogger] = None,
        wiki: Optional[WikiPublisher] = None,
        approval_gate: Optional[CrossTeamApprovalGate] = None,
        temporal_adapter: Optional[Any] = None,
    ) -> None:
        self.dataset_loader = dataset_loader or DatasetLoader()
        self.quantitative = quantitative or QuantitativeEvaluator()
        self.qualitative = qualitative or QualitativeEvaluator()
        self.comparator = comparator or BaselineComparator()
        self.prometheus = prometheus or PrometheusExporter()
        self.loki = loki or LokiLogger()
        self.wiki = wiki or WikiPublisher()
        self.approval_gate = approval_gate or CrossTeamApprovalGate()
        if temporal_adapter:
            self.approval_gate.inject_temporal(temporal_adapter)
        self._reports: Dict[str, QualityGateReport] = {}
        self._reviews: Dict[str, List[Any]] = {}

    def load_dataset(
        self,
        name: str,
        records: List[Dict[str, Any]],
        baseline_version: str = "",
        previous_version: str = "",
    ) -> EvalDataset:
        ds = self.dataset_loader.load_from_records(
            name, records, baseline_version, previous_version
        )
        self.loki.log(
            event="dataset_loaded",
            run_id=ds.dataset_id,
            step="load_dataset",
            status="success",
            payload={"sample_count": len(ds.samples), "categories": list(ds.by_category().keys())},
        )
        return ds

    def evaluate_quantitatively(
        self,
        report: QualityGateReport,
        dataset: EvalDataset,
    ) -> QualityGateReport:
        metrics = self.quantitative.evaluate(dataset)
        report.quantitative = metrics
        self.prometheus.record(report.run_id, metrics.to_dict(), "passed" if metrics.passed else "blocked")
        self.loki.log(
            event="quantitative_eval_completed",
            run_id=report.run_id,
            step="quantitative",
            status="passed" if metrics.passed else "failed",
            payload=metrics.to_dict(),
        )
        if not metrics.passed:
            report.status = "blocked"
            report.findings.extend(metrics.failures)
        return report

    def add_qualitative_review(
        self,
        report: QualityGateReport,
        review: Any,
    ) -> QualityGateReport:
        self._reviews.setdefault(report.report_id, []).append(review)
        self.loki.log(
            event="qualitative_review_added",
            run_id=report.run_id,
            step="qualitative",
            status="success",
            payload=review.to_dict(),
        )
        return report

    def evaluate_qualitatively(
        self,
        report: QualityGateReport,
    ) -> QualityGateReport:
        reviews = self._reviews.get(report.report_id, [])
        summary = self.qualitative.summarize(reviews)
        report.qualitative = summary
        self.loki.log(
            event="qualitative_eval_completed",
            run_id=report.run_id,
            step="qualitative",
            status="passed" if summary.passed else "failed",
            payload=summary.to_dict(),
        )
        if not summary.passed:
            report.status = "blocked"
            report.findings.extend(summary.failures)
        return report

    def compare_baseline(
        self,
        report: QualityGateReport,
        baseline_metrics: Dict[str, float],
        previous_metrics: Dict[str, float],
    ) -> QualityGateReport:
        if report.quantitative is None:
            raise ValueError("quantitative evaluation required before baseline comparison")
        comparison = self.comparator.compare(
            report.quantitative.to_dict(),
            baseline_metrics,
            previous_metrics,
        )
        report.baseline = comparison
        self.prometheus.record_baseline_delta(report.run_id, comparison.deltas_vs_baseline)
        self.loki.log(
            event="baseline_comparison_completed",
            run_id=report.run_id,
            step="baseline_comparison",
            status="passed" if comparison.passed else "failed",
            payload=comparison.to_dict(),
        )
        if not comparison.passed:
            report.status = "blocked"
            report.findings.extend(comparison.regressions)
        return report

    def publish_report(
        self,
        report: QualityGateReport,
    ) -> QualityGateReport:
        markdown = self.wiki.generate_markdown(
            report_id=report.report_id,
            model_version=report.model_version,
            dataset_id=report.dataset_id,
            status=report.status,
            quantitative=report.quantitative.to_dict() if report.quantitative else {},
            qualitative=report.qualitative.to_dict() if report.qualitative else {},
            baseline=report.baseline.to_dict() if report.baseline else {},
            approvals=report.cross_team_approval.to_dict() if report.cross_team_approval else {},
            findings=report.findings,
        )
        result = self.wiki.publish(report.report_id, markdown)
        report.evidence_uris["wiki_report"] = result["uri"]
        report.evidence_uris["report_digest"] = result["digest"]
        self.loki.log(
            event="report_published",
            run_id=report.run_id,
            step="publish",
            status="success",
            payload=result,
        )
        return report

    def create_report(
        self,
        run_id: str,
        model_version: str,
        dataset_id: str,
    ) -> QualityGateReport:
        report = QualityGateReport(
            run_id=run_id,
            model_version=model_version,
            dataset_id=dataset_id,
            status="pending",
        )
        self._reports[report.report_id] = report
        self.loki.log(
            event="report_created",
            run_id=run_id,
            step="create_report",
            status="pending",
            payload={"report_id": report.report_id},
        )
        return report

    def request_cross_team_approval(
        self,
        report: QualityGateReport,
        workflow_id: str = "",
    ) -> QualityGateReport:
        if report.status == "blocked":
            self.loki.log(
                event="approval_skipped_blocked",
                run_id=report.run_id,
                step="approval",
                status="blocked",
            )
            return report
        approval = self.approval_gate.request_approval(
            run_id=report.run_id,
            report_id=report.report_id,
            workflow_id=workflow_id or f"qg-{report.run_id}",
        )
        report.cross_team_approval = approval
        report.status = "awaiting_approval"
        self._reports[report.report_id] = report
        self.loki.log(
            event="approval_requested",
            run_id=report.run_id,
            step="approval",
            status="awaiting_approval",
            payload=approval.to_dict(),
        )
        return report

    def submit_approval_signature(
        self,
        approval_id: str,
        team: str,
        signed_by: str,
        comment: str = "",
    ) -> CrossTeamApproval:
        approval = self.approval_gate.submit_signature(approval_id, team, signed_by, comment)
        # Update report status if fully approved
        for report in self._reports.values():
            if report.cross_team_approval and report.cross_team_approval.approval_id == approval_id:
                report.cross_team_approval = approval
                if approval.is_approved():
                    report.status = "approved"
                self._reports[report.report_id] = report
                break
        return approval

    def reject_approval(
        self,
        approval_id: str,
        team: str,
        reason: str = "",
    ) -> CrossTeamApproval:
        approval = self.approval_gate.reject(approval_id, team, reason)
        for report in self._reports.values():
            if report.cross_team_approval and report.cross_team_approval.approval_id == approval_id:
                report.cross_team_approval = approval
                report.status = "rejected"
                report.findings.append(f"approval_rejected_by_{team}: {reason}")
                self._reports[report.report_id] = report
                break
        return approval

    def run_full_gate(
        self,
        run_id: str,
        model_version: str,
        dataset: EvalDataset,
        baseline_metrics: Dict[str, float],
        previous_metrics: Dict[str, float],
        reviews: Optional[List[Any]] = None,
        request_approval: bool = True,
    ) -> QualityGateReport:
        report = self.create_report(run_id, model_version, dataset.dataset_id)
        report = self.evaluate_quantitatively(report, dataset)
        for review in reviews or []:
            self.add_qualitative_review(report, review)
        report = self.evaluate_qualitatively(report)
        report = self.compare_baseline(report, baseline_metrics, previous_metrics)
        if report.status == "blocked":
            report = self.publish_report(report)
            return report
        report = self.publish_report(report)
        if request_approval:
            report = self.request_cross_team_approval(report)
        else:
            report.status = "approved"
        return report

    def get_report(self, report_id: str) -> Optional[QualityGateReport]:
        return self._reports.get(report_id)

    def list_reports(self, status: Optional[str] = None) -> List[QualityGateReport]:
        reports = list(self._reports.values())
        if status:
            reports = [r for r in reports if r.status == status]
        return reports
