"""Retroalimentación implícita de usuarios como señales de evaluación."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fine_tuning.evaluation_matrix.models_cem import (
    EvaluationSignal,
    UserFeedbackSignal,
)


class UserFeedbackAgent:
    """
    Convierte retroalimentación implícita de usuarios (thumbs-down,
    re-preguntas, escalaciones, reportes explícitos) en señales de evaluación
    de primer orden.
    """

    SEVERITY_MAP = {
        "thumbs_down": 0.3,
        "re_prompt": 0.2,
        "escalation": 0.8,
        "explicit_report": 1.0,
    }

    def __init__(self) -> None:
        self._feedback: List[UserFeedbackSignal] = []

    def ingest(self, data: Dict[str, Any]) -> UserFeedbackSignal:
        fb = UserFeedbackSignal(
            session_id=data.get("session_id", ""),
            trace_id=data.get("trace_id", ""),
            user_id=data.get("user_id", ""),
            feedback_type=data.get("feedback_type", ""),
            reason=data.get("reason", ""),
            metadata=data.get("metadata", {}),
        )
        self._feedback.append(fb)
        return fb

    def to_evaluation_signals(
        self,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
    ) -> List[EvaluationSignal]:
        signals: List[EvaluationSignal] = []
        counts: Dict[str, int] = {}
        for fb in self._feedback:
            if window_start is not None and fb.timestamp < window_start:
                continue
            if window_end is not None and fb.timestamp > window_end:
                continue
            counts[fb.feedback_type] = counts.get(fb.feedback_type, 0) + 1

        total = len(self._feedback) or 1
        for ftype, count in counts.items():
            severity = self.SEVERITY_MAP.get(ftype, 0.5)
            # A high negative rate lowers the score
            negative_score = 1.0 - (count / total * severity)
            signals.append(EvaluationSignal(
                source="user_feedback",
                metric_name=f"user_feedback_{ftype}_rate",
                value=round(negative_score, 3),
                threshold=0.7,
                passed=negative_score >= 0.7,
                details={"count": count},
            ))
        return signals

    def list_feedback(
        self,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
    ) -> List[UserFeedbackSignal]:
        out = []
        for fb in self._feedback:
            if window_start is not None and fb.timestamp < window_start:
                continue
            if window_end is not None and fb.timestamp > window_end:
                continue
            out.append(fb)
        return out
