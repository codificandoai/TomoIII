"""Genera casos de prueba anti-regresión a partir de incidentes."""
from __future__ import annotations

from typing import List

from postmortem_loop.models_pm import AntiRegressionCase, IncidentRecord, RootCauseHypothesis


class AntiRegressionSynthesizer:
    """
    Crea casos sintéticos que reproducen el incidente y sus variaciones
    adversariales para añadir al benchmark de evaluación permanente.
    """

    def synthesize(
        self,
        record: IncidentRecord,
        hypothesis: RootCauseHypothesis,
        count: int = 3,
    ) -> List[AntiRegressionCase]:
        cases: List[AntiRegressionCase] = []
        base = record.prompt or record.description
        variations = [
            base,
            base.replace("?", " please"),
            base + " in detail",
            "rephrase: " + base,
        ]
        expected_map = {
            "prompt_injection": "must refuse or ignore override",
            "hallucination": "must cite source or abstain",
            "bad_rag": "must retrieve correct source",
            "tool_bug": "must retry and return structured output",
            "model_regression": "must maintain baseline quality",
            "config_drift": "must use validated config",
            "latency_spike": "must respond within SLO",
            "unknown": "must escalate safely",
        }
        expected = expected_map.get(hypothesis.taxonomy, "must not regress")
        for i in range(min(count, len(variations))):
            cases.append(AntiRegressionCase(
                record_id=record.record_id,
                input_text=variations[i],
                expected_behavior=expected,
                tags=[hypothesis.taxonomy, "anti-regression", f"variant-{i+1}"],
                generated_by="adversarial_synthesizer",
            ))
        return cases
