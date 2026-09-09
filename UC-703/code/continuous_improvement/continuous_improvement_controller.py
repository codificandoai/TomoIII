"""Controller de Continuous Improvement & Feedback Loop."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from continuous_improvement.effectiveness_tracker import EffectivenessTracker
from continuous_improvement.feedback_collector import FeedbackCollector
from continuous_improvement.improvement_queue import ImprovementQueue
from continuous_improvement.improvement_recommender import ImprovementRecommender
from continuous_improvement.models_ci import (
    ExecutionLogRef,
    FeedbackItem,
    ImprovementRecommendation,
    IncidentRef,
)
from continuous_improvement.pattern_analyzer import PatternAnalyzer
from continuous_improvement.root_cause_analyzer import RootCauseAnalyzer


class ContinuousImprovementController:
    """
    Orquesta el bucle de mejora continua:
    recolecta feedback, analiza patrones, determina causas raíz, recomienda
    acciones y las somete a aprobación humana antes de materializar cambios.
    """

    def __init__(
        self,
        collector: Optional[FeedbackCollector] = None,
        analyzer: Optional[PatternAnalyzer] = None,
        root_cause: Optional[RootCauseAnalyzer] = None,
        recommender: Optional[ImprovementRecommender] = None,
        queue: Optional[ImprovementQueue] = None,
        tracker: Optional[EffectivenessTracker] = None,
    ) -> None:
        self.collector = collector or FeedbackCollector()
        self.analyzer = analyzer or PatternAnalyzer()
        self.root_cause = root_cause or RootCauseAnalyzer()
        self.recommender = recommender or ImprovementRecommender()
        self.queue = queue or ImprovementQueue()
        self.tracker = tracker or EffectivenessTracker()

    def ingest_feedback(self, data: Dict[str, Any]) -> FeedbackItem:
        return self.collector.collect(data)

    def run_analysis(
        self,
        log_refs: Optional[List[ExecutionLogRef]] = None,
        incident_refs: Optional[List[IncidentRef]] = None,
    ) -> Dict[str, Any]:
        clusters = self.analyzer.analyze(
            self.collector.list_all(),
            log_refs=log_refs or [],
            incident_refs=incident_refs or [],
        )
        recommendations: List[ImprovementRecommendation] = []
        findings = []
        for cluster in clusters:
            if not cluster.systemic:
                continue
            hypotheses = self.root_cause.analyze(cluster)
            recs = self.recommender.recommend(cluster, hypotheses)
            for rec in recs:
                self.queue.submit(rec)
                recommendations.append(rec)
            findings.append({
                "cluster": cluster.to_dict(),
                "hypotheses": [h.to_dict() for h in hypotheses],
                "recommendations": [r.to_dict() for r in recs],
            })
        return {
            "clusters_analyzed": len(clusters),
            "systemic_clusters": len([c for c in clusters if c.systemic]),
            "recommendations_created": len(recommendations),
            "findings": findings,
        }

    def approve_recommendation(
        self,
        queue_item_id: str,
        reviewer: str,
        notes: str = "",
    ) -> Optional[Any]:
        return self.queue.decide(queue_item_id, "approved", reviewer, notes)

    def reject_recommendation(
        self,
        queue_item_id: str,
        reviewer: str,
        notes: str = "",
    ) -> Optional[Any]:
        return self.queue.decide(queue_item_id, "rejected", reviewer, notes)

    def register_baseline(self, metric_name: str, value: float) -> None:
        self.tracker.register_baseline(metric_name, value)

    def measure_effectiveness(
        self,
        recommendation_id: str,
        metric_name: str,
        after_value: float,
    ) -> Any:
        return self.tracker.measure(recommendation_id, metric_name, after_value)

    def get_pending_recommendations(self) -> List[Any]:
        return [item.to_dict() for item in self.queue.list_pending()]

    def list_recommendations(self) -> List[Dict[str, Any]]:
        return [rec.to_dict() for rec in self.queue._recommendations.values()]

    def dashboard(self) -> Dict[str, Any]:
        return {
            "feedback_count": len(self.collector.list_all()),
            "cluster_count": len(self.analyzer._clusters),
            "systemic_clusters": len([c for c in self.analyzer._clusters if c.systemic]),
            "pending_recommendations": len(self.queue.list_pending()),
            "effectiveness": self.tracker.summary(),
        }
