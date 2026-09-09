"""Recolección unificada de retroalimentación explícita e implícita."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from continuous_improvement.models_ci import FeedbackItem


class FeedbackCollector:
    """
    Recolecta feedback explícito (ratings, correcciones, quejas) e implícito
    (re-preguntas, escalaciones) y lo vincula a modelo, prompt, sesión y trace.
    """

    def __init__(self) -> None:
        self._items: List[FeedbackItem] = []

    def collect(self, data: Dict[str, Any]) -> FeedbackItem:
        item = FeedbackItem(
            source=data.get("source", ""),
            user_id=data.get("user_id", ""),
            session_id=data.get("session_id", ""),
            trace_id=data.get("trace_id", ""),
            model_version=data.get("model_version", ""),
            prompt_version_id=data.get("prompt_version_id", ""),
            category=data.get("category", ""),
            severity=data.get("severity", "medium"),
            message=data.get("message", ""),
            metadata=data.get("metadata", {}),
        )
        self._items.append(item)
        return item

    def list_all(self) -> List[FeedbackItem]:
        return list(self._items)

    def query(
        self,
        category: Optional[str] = None,
        source: Optional[str] = None,
        model_version: Optional[str] = None,
        min_severity: str = "",
    ) -> List[FeedbackItem]:
        severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        out = []
        min_rank = severity_rank.get(min_severity, 0)
        for item in self._items:
            if category and item.category != category:
                continue
            if source and item.source != source:
                continue
            if model_version and item.model_version != model_version:
                continue
            if severity_rank.get(item.severity, 0) < min_rank:
                continue
            out.append(item)
        return out
