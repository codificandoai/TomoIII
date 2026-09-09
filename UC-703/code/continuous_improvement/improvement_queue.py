"""Cola de aprobación humana para recomendaciones de mejora continua."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from continuous_improvement.models_ci import ImprovementQueueItem, ImprovementRecommendation


class ImprovementQueue:
    """
    Buffer de gobernanza donde las recomendaciones generadas por agentes se
    someten a revisión humana antes de convertirse en cambios materiales.
    """

    def __init__(self) -> None:
        self._items: List[ImprovementQueueItem] = []
        self._recommendations: Dict[str, ImprovementRecommendation] = {}

    def submit(self, recommendation: ImprovementRecommendation) -> ImprovementQueueItem:
        item = ImprovementQueueItem(recommendation_id=recommendation.recommendation_id)
        self._items.append(item)
        self._recommendations[recommendation.recommendation_id] = recommendation
        return item

    def decide(
        self,
        item_id: str,
        decision: str,  # approve, reject, defer
        reviewer: str,
        notes: str = "",
    ) -> Optional[ImprovementQueueItem]:
        for item in self._items:
            if item.item_id == item_id:
                item.status = decision
                item.reviewer_notes = notes
                item.submitted_at = time.time()
                rec = self._recommendations.get(item.recommendation_id)
                if rec:
                    rec.status = decision
                    rec.approved_by = reviewer if decision == "approved" else ""
                return item
        return None

    def list_pending(self) -> List[ImprovementQueueItem]:
        return [i for i in self._items if i.status == "pending"]

    def get(self, item_id: str) -> Optional[ImprovementQueueItem]:
        for item in self._items:
            if item.item_id == item_id:
                return item
        return None

    def get_recommendation(self, recommendation_id: str) -> Optional[ImprovementRecommendation]:
        return self._recommendations.get(recommendation_id)
