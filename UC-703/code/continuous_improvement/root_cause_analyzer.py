"""Análisis de causa raíz para clusters de retroalimentación."""
from __future__ import annotations

from typing import List, Optional

from continuous_improvement.models_ci import FeedbackCluster, RootCauseHypothesis


class RootCauseAnalyzer:
    """
    Determina la causa raíz más probable de un cluster usando reglas
    semánticas simples. No es ciego: genera evidencia, no ordenes.
    """

    KEYWORDS = {
        "prompt": ["prompt", "instruction", "tone", "format", "concise", "verbose", "answer style"],
        "guardrail": ["unsafe", "jailbreak", "disallowed", "blocked", "guardrail", "policy violation"],
        "data_knowledge": ["document", "source", "retrieval", "knowledge base", "rag", "context"],
        "model_drift": ["drift", "degradation", "accuracy drop", "worse", "regression"],
        "infrastructure": ["timeout", "latency", "rate limit", "error", "exception", "failure"],
    }

    def analyze(self, cluster: FeedbackCluster) -> List[RootCauseHypothesis]:
        text = cluster.pattern.lower()
        for item_text in (cluster.feedback_ids or []):
            text += " " + item_text.lower()
        for log in cluster.log_refs:
            text += " " + (log.error_category or "").lower()
            text += " " + (log.tool_name or "").lower()
        for inc in cluster.incident_refs:
            text += " " + (inc.root_cause or "").lower()

        hypotheses: List[RootCauseHypothesis] = []
        for cause, keywords in self.KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            confidence = min(hits / 3.0, 1.0) if hits else 0.1
            if hits > 0:
                hypotheses.append(RootCauseHypothesis(
                    cluster_id=cluster.cluster_id,
                    cause_category=cause,
                    confidence=round(confidence, 2),
                    evidence=[f"matched keywords for {cause}"],
                    rationale=f"Detected {hits} keyword hits for {cause}",
                ))
        if not hypotheses:
            hypotheses.append(RootCauseHypothesis(
                cluster_id=cluster.cluster_id,
                cause_category="unknown",
                confidence=0.0,
                evidence=["no strong keyword signals"],
                rationale="No clear root cause pattern detected",
            ))
        return sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
