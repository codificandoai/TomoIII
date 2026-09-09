"""Genera recomendaciones de mejora basadas en causa raíz y cluster."""
from __future__ import annotations

from typing import List

from continuous_improvement.models_ci import (
    FeedbackCluster,
    ImprovementRecommendation,
    RootCauseHypothesis,
)


class ImprovementRecommender:
    """
    Convierte hipótesis de causa raíz en recomendaciones accionables,
    siempre como evidencia que requiere aprobación antes de implementarse.
    """

    def recommend(self, cluster: FeedbackCluster, hypotheses: List[RootCauseHypothesis]) -> List[ImprovementRecommendation]:
        top = hypotheses[0] if hypotheses else RootCauseHypothesis(
            cluster_id=cluster.cluster_id, cause_category="unknown", confidence=0.0
        )
        cause = top.cause_category
        recs: List[ImprovementRecommendation] = []
        if cause == "prompt":
            recs.append(ImprovementRecommendation(
                cluster_id=cluster.cluster_id,
                root_cause_category=cause,
                action_type="prompt_patch",
                target=cluster.pattern,
                description="Revise and clarify the prompt instructions for this category.",
                expected_impact="Reduce off-target responses and improve user satisfaction.",
                confidence=top.confidence,
            ))
        elif cause == "guardrail":
            recs.append(ImprovementRecommendation(
                cluster_id=cluster.cluster_id,
                root_cause_category=cause,
                action_type="guardrail_rule",
                target=cluster.pattern,
                description="Add or tighten guardrail/schema rule around the failing category.",
                expected_impact="Reduce policy violations without over-blocking benign requests.",
                confidence=top.confidence,
            ))
        elif cause == "data_knowledge":
            recs.append(ImprovementRecommendation(
                cluster_id=cluster.cluster_id,
                root_cause_category=cause,
                action_type="data_curation",
                target=cluster.pattern,
                description="Curate or update the knowledge base/RAG documents behind this pattern.",
                expected_impact="Reduce hallucinations grounded in stale or noisy sources.",
                confidence=top.confidence,
            ))
        elif cause == "model_drift":
            recs.append(ImprovementRecommendation(
                cluster_id=cluster.cluster_id,
                root_cause_category=cause,
                action_type="retrain",
                target=cluster.pattern,
                description="Trigger fine-tuning/retraining with recent golden-set examples.",
                expected_impact="Recover accuracy and robustness against regression.",
                confidence=top.confidence,
            ))
        elif cause == "infrastructure":
            recs.append(ImprovementRecommendation(
                cluster_id=cluster.cluster_id,
                root_cause_category=cause,
                action_type="monitor",
                target=cluster.pattern,
                description="Investigate timeout/latency/rate-limit root cause and scale resource or add circuit breaker.",
                expected_impact="Improve availability and reliability of tool execution.",
                confidence=top.confidence,
            ))
        else:
            recs.append(ImprovementRecommendation(
                cluster_id=cluster.cluster_id,
                root_cause_category=cause,
                action_type="hitl_review",
                target=cluster.pattern,
                description="Root cause unclear; escalate to human review before action.",
                expected_impact="Avoid low-confidence automated changes.",
                confidence=top.confidence,
            ))
        return recs
