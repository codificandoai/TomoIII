"""Spotlight de atención: selecciona qué hipótesis/señales/recuerdos entran al
espacio de trabajo (workspace) del agente AGI para UC-296."""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

from memory_config import SpotlightConfig
from memory_types import SpotlightItem


class AttentionSpotlight:
    """Implementa un mecanismo de atención competitiva sobre candidatos.

    Cada candidato (hipótesis, señal o recuerdo) recibe una puntuación de saliencia
    combinando:
    - confianza (confidence),
    - relevancia para el objetivo actual (goal relevance),
    - novedad (novelty),
    - recencia (recency).

    Solo los ``max_items_in_workspace`` mejores entran al workspace.
    """

    def __init__(self, config: Optional[SpotlightConfig] = None) -> None:
        self.config = config or SpotlightConfig()

    def select(
        self,
        candidates: List[SpotlightItem],
        current_goal: str = "",
        current_price: float = 0.0,
    ) -> List[SpotlightItem]:
        if not candidates:
            return []

        scored: List[SpotlightItem] = []
        seen_types: Dict[str, int] = {}
        for item in candidates:
            score = self._score(item, current_goal, current_price, seen_types)
            item.score = round(score, 6)
            item.reason = self._reason(item, current_goal)
            scored.append(item)
            seen_types[item.item_type] = seen_types.get(item.item_type, 0) + 1

        scored.sort(key=lambda x: x.score, reverse=True)
        selected = scored[: self.config.max_items_in_workspace]
        return selected

    def _score(
        self,
        item: SpotlightItem,
        current_goal: str,
        current_price: float,
        seen_types: Dict[str, int],
    ) -> float:
        content = item.content
        confidence = float(content.get("confidence", 0.5))
        recency = self._recency(content)
        novelty = self._novelty(item, seen_types)
        relevance = self._relevance(content, current_goal, current_price)

        score = (
            self.config.confidence_weight * confidence +
            self.config.recency_weight * recency +
            self.config.novelty_weight * novelty +
            self.config.relevance_weight * relevance
        )
        return score

    @staticmethod
    def _recency(content: Dict[str, Any]) -> float:
        ts = content.get("timestamp")
        if not ts:
            return 0.5
        try:
            from datetime import datetime
            if isinstance(ts, str):
                t = datetime.fromisoformat(ts)
                age_seconds = max(0, (datetime.now() - t).total_seconds())
                return math.exp(-age_seconds / 3600.0)
        except Exception:
            pass
        return 0.5

    @staticmethod
    def _novelty(item: SpotlightItem, seen_types: Dict[str, int]) -> float:
        count = seen_types.get(item.item_type, 0)
        return max(0.0, 1.0 - 0.2 * count)

    @staticmethod
    def _relevance(content: Dict[str, Any], current_goal: str, current_price: float) -> float:
        goal = (current_goal or "").lower()
        text = json.dumps(content).lower()
        if not goal:
            return 0.5
        keywords = [k for k in goal.split() if len(k) > 3]
        if not keywords:
            return 0.5
        matches = sum(1 for k in keywords if k in text)
        return min(1.0, matches / len(keywords))

    @staticmethod
    def _reason(item: SpotlightItem, current_goal: str) -> str:
        return (
            f"Selected by attention spotlight: confidence={item.content.get('confidence')}, "
            f"goal='{current_goal[:30]}...', score={item.score}"
        )
