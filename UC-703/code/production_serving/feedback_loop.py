"""Ciclo de retroalimentación y re-evaluación automática en producción."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from production_serving.models_serving import (
    FeedbackSignal,
    InferenceRequest,
    InferenceResponse,
    ReEvaluationResult,
)


class FeedbackLoop:
    """
    Captura señales de usuario y métricas de calidad, y dispara re-evaluaciones
    deterministas con LLM-as-judge. Alimenta candidatos para re-entrenamiento
    LoRA y recuantización.
    """

    def __init__(self) -> None:
        self._feedback: List[FeedbackSignal] = []
        self._evaluations: List[ReEvaluationResult] = []

    def collect(self, signal: FeedbackSignal) -> None:
        self._feedback.append(signal)

    def collect_from_api(
        self,
        request_id: str,
        session_id: str,
        principal_id: str,
        signal_type: str,
        value: Any,
        comment: str = "",
    ) -> FeedbackSignal:
        fb = FeedbackSignal(
            request_id=request_id,
            session_id=session_id,
            principal_id=principal_id,
            signal_type=signal_type,
            value=value,
            comment=comment,
        )
        self._feedback.append(fb)
        return fb

    def re_evaluate(
        self,
        request: InferenceRequest,
        response: InferenceResponse,
    ) -> ReEvaluationResult:
        # Deterministic LLM-as-judge proxy
        score = 0.8
        reasons: List[str] = []
        if len(response.generated_text) < 5:
            score -= 0.3
            reasons.append("response too short")
        if response.guardrails.blocked:
            score -= 0.4
            reasons.append("guardrail triggered")
        if not response.generated_text.endswith("[generated]"):
            reasons.append("unexpected format")

        # simulate regression by comparing with prompt keywords
        prompt_words = set(request.prompt.lower().split())
        response_words = set(response.generated_text.lower().split())
        overlap = len(prompt_words & response_words) / max(len(prompt_words), 1)
        if overlap < 0.1:
            score -= 0.2
            reasons.append("low lexical overlap")

        score = max(0.0, min(1.0, round(score, 4)))
        flagged = score < 0.6 or bool(reasons)
        regression = any(
            fb.signal_type in {"thumbs_down", "human_escalation"} and fb.value in (True, 1, "negative")
            for fb in self._feedback if fb.request_id == request.request_id
        )

        result = ReEvaluationResult(
            request_id=request.request_id,
            judge_score=score,
            regression=regression,
            flagged=flagged,
            reasons=reasons,
        )
        self._evaluations.append(result)
        return result

    def get_retrain_candidates(self) -> List[ReEvaluationResult]:
        return [e for e in self._evaluations if e.flagged or e.regression]

    def feedback_summary(self) -> Dict[str, Any]:
        total = len(self._feedback)
        thumbs_up = sum(1 for f in self._feedback if f.signal_type == "thumbs_up")
        thumbs_down = sum(1 for f in self._feedback if f.signal_type == "thumbs_down")
        escalations = sum(1 for f in self._feedback if f.signal_type == "human_escalation")
        return {
            "total_feedback": total,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "human_escalations": escalations,
            "re_evaluations": len(self._evaluations),
            "retrain_candidates": len(self.get_retrain_candidates()),
        }
