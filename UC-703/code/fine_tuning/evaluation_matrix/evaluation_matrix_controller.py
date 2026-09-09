"""Controller principal de la Continuous Evaluation Matrix."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fine_tuning.evaluation_matrix.diffusion_agent import DiffusionAgent
from fine_tuning.evaluation_matrix.evolutionary_curator import EvolutionaryCuratorAgent
from fine_tuning.evaluation_matrix.hybrid_evaluator import HybridEvaluatorAgent
from fine_tuning.evaluation_matrix.monitoring_exporter import MonitoringExporterAgent
from fine_tuning.evaluation_matrix.models_cem import (
    CEMReport,
    Checkpoint,
    EvaluationSignal,
    HumanReview,
    StaticPrompt,
    UserFeedbackSignal,
)
from fine_tuning.evaluation_matrix.test_design_agent import TestDesignAgent
from fine_tuning.evaluation_matrix.user_feedback_agent import UserFeedbackAgent


class EvaluationMatrixController:
    """
    Orquesta la Continuous Evaluation Matrix: diseño de pruebas, evaluación
    híbrida, feedback de usuarios, monitoreo, evolución de checkpoints y difusión.
    """

    def __init__(
        self,
        test_design: Optional[TestDesignAgent] = None,
        evaluator: Optional[HybridEvaluatorAgent] = None,
        feedback_agent: Optional[UserFeedbackAgent] = None,
        monitor: Optional[MonitoringExporterAgent] = None,
        curator: Optional[EvolutionaryCuratorAgent] = None,
        diffusion: Optional[DiffusionAgent] = None,
    ) -> None:
        self.test_design = test_design or TestDesignAgent()
        self.evaluator = evaluator or HybridEvaluatorAgent()
        self.feedback_agent = feedback_agent or UserFeedbackAgent()
        self.monitor = monitor or MonitoringExporterAgent()
        self.curator = curator or EvolutionaryCuratorAgent()
        self.diffusion = diffusion or DiffusionAgent()
        self._reports: List[CEMReport] = []
        self._human_reviews: List[HumanReview] = []

    def create_checkpoint(
        self,
        name: str,
        prompt_ids: Optional[List[str]] = None,
        golden_set_ids: Optional[List[str]] = None,
        cell_ids: Optional[List[str]] = None,
        risk_signals: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> Checkpoint:
        return self.test_design.create_checkpoint(
            name=name,
            prompt_ids=prompt_ids,
            golden_set_ids=golden_set_ids,
            cell_ids=cell_ids,
            risk_signals=risk_signals or [],
            version=version,
        )

    def create_static_prompt(
        self,
        name: str,
        prompt: str,
        category: str = "use_case",
        risk_level: str = "medium",
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> StaticPrompt:
        return self.test_design.create_static_prompt(
            name=name,
            prompt=prompt,
            category=category,
            risk_level=risk_level,
            tags=tags,
            version=version,
        )

    def create_golden_set(
        self,
        name: str,
        records: List[Dict[str, Any]],
        version: str = "1.0.0",
    ) -> Any:
        return self.test_design.create_golden_set(name, records, version)

    def create_test_cell(
        self,
        name: str,
        model_version: str,
        traffic_pct: float,
        prompt_ids: Optional[List[str]] = None,
        golden_set_id: str = "",
    ) -> Any:
        return self.test_design.create_test_cell(
            name=name,
            model_version=model_version,
            traffic_pct=traffic_pct,
            prompt_ids=prompt_ids,
            golden_set_id=golden_set_id,
        )

    def add_human_review(self, review: HumanReview) -> None:
        self._human_reviews.append(review)

    def ingest_user_feedback(self, data: Dict[str, Any]) -> UserFeedbackSignal:
        return self.feedback_agent.ingest(data)

    def run_evaluation(
        self,
        run_id: str,
        checkpoint_id: str,
        model_version: str,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
        trigger_evolution: bool = False,
    ) -> CEMReport:
        checkpoint = self.test_design.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValueError("checkpoint not found")

        signals: List[EvaluationSignal] = []

        # Evaluate static prompts
        for prompt in checkpoint.static_prompts:
            signals.extend(self.evaluator.evaluate_prompts([prompt], model_version))

        # Evaluate golden sets
        for gs in checkpoint.golden_sets:
            signals.extend(self.evaluator.evaluate_golden_set(gs, model_version))

        # Evaluate test cells
        for cell in checkpoint.test_cells:
            signals.extend(self.evaluator.evaluate_test_cell(cell))

        # Human reviews
        human_signals = self.evaluator.aggregate_human_reviews(self._human_reviews)
        signals.extend(human_signals)

        # User feedback signals
        fb_signals = self.feedback_agent.to_evaluation_signals(window_start, window_end)
        signals.extend(fb_signals)

        # Overall pass
        overall_passed = all(s.passed for s in signals)

        # Monitoring export
        for sig in signals:
            self.monitor.emit_signal(sig)

        # Failure clustering
        failure_clusters = self.curator.cluster_failures(signals)

        # Risk signals from clusters
        risk_signals = self.curator.propose_risk_signals(failure_clusters)

        # Build report
        report = CEMReport(
            run_id=run_id,
            checkpoint_id=checkpoint_id,
            model_version=model_version,
            signals=signals,
            human_reviews=list(self._human_reviews),
            failure_clusters=failure_clusters,
            risk_signals=risk_signals,
            overall_passed=overall_passed,
        )

        # Diffusion: publish report and gate updates
        self.diffusion.publish_report(report)
        failed_signals = [s for s in signals if not s.passed]
        if failed_signals:
            self.diffusion.update_gate_thresholds("quality_gate", failed_signals)
            self.diffusion.request_retrain(report, "failures detected in CEM run")

        # Optional evolution: adversarial audit and checkpoint update
        if trigger_evolution and failed_signals:
            prompt_texts = [p.prompt for p in checkpoint.static_prompts]
            adv_signals = self.curator.adversarial_audit(prompt_texts, model_version)
            report.risk_signals.extend(adv_signals)
            for cluster in failure_clusters:
                new_prompts = self.curator.generate_new_prompts_from_cluster(cluster)
                self.test_design.evolve_checkpoint(
                    checkpoint_id,
                    new_prompts=new_prompts,
                    new_risk_signals=[rs.name for rs in adv_signals],
                )

        self._reports.append(report)
        return report

    def get_report(self, report_id: str) -> Optional[CEMReport]:
        for r in self._reports:
            if r.report_id == report_id:
                return r
        return None

    def list_reports(self) -> List[CEMReport]:
        return list(self._reports)

    def render_prometheus(self) -> str:
        return self.monitor.render_prometheus()

    def get_logs(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.monitor.get_logs()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoints": len(self.test_design.list_checkpoints()),
            "reports": len(self._reports),
            "monitor": self.monitor.to_dict(),
            "diffusion": self.diffusion.to_dict(),
        }
