"""Agente de análisis de causa raíz con taxonomía LLMOps."""
from __future__ import annotations

from typing import List

from postmortem_loop.models_pm import IncidentRecord, RootCauseHypothesis


class RootCauseAgent:
    """
    Clasifica incidentes en taxonomías conocidas y propone hipótesis con
    evidencia verificable. No ejecuta cambios.
    """

    TAXONOMIES = [
        "hallucination",
        "bad_rag",
        "prompt_injection",
        "model_regression",
        "tool_bug",
        "config_drift",
        "latency_spike",
        "unknown",
    ]

    def analyze(self, record: IncidentRecord) -> List[RootCauseHypothesis]:
        hypotheses: List[RootCauseHypothesis] = []
        text = f"{record.prompt} {record.output} {record.description}".lower()

        if "ignore previous" in text or "jailbreak" in text or "DAN" in text:
            hypotheses.append(self._build(record, "prompt_injection", 0.9, ["suspicious instruction override"]))
        if record.category == "hallucination" or "made up" in text or "non-existent" in text:
            hypotheses.append(self._build(record, "hallucination", 0.8, ["factual claim without source"]))
        if record.category == "quality" and ("wrong source" in text or "document" in text):
            hypotheses.append(self._build(record, "bad_rag", 0.75, ["retrieved source mismatch"]))
        if record.category == "latency":
            hypotheses.append(self._build(record, "latency_spike", 0.7, ["p95 latency exceeded"]))
        if record.config_diffs:
            hypotheses.append(self._build(record, "config_drift", 0.6, ["recent config changes"] + record.config_diffs[:3]))
        if record.tool_logs:
            for log in record.tool_logs[:2]:
                if log.get("status") == "failed":
                    hypotheses.append(self._build(record, "tool_bug", 0.75, [f"tool {log.get('tool')} failed"]))
        if record.model_version and "old" in record.model_version:
            hypotheses.append(self._build(record, "model_regression", 0.65, ["deployed model rollback candidate"]))

        if not hypotheses:
            hypotheses.append(self._build(record, "unknown", 0.5, ["no strong indicators"]))

        # Sort by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    @staticmethod
    def _build(record: IncidentRecord, taxonomy: str, confidence: float, evidence_items: List[str]) -> RootCauseHypothesis:
        return RootCauseHypothesis(
            record_id=record.record_id,
            taxonomy=taxonomy,
            summary=f"Incident likely caused by {taxonomy}",
            confidence=confidence,
            evidence=[{"type": "indicator", "value": item} for item in evidence_items],
        )
