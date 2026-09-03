"""Tipos compartidos de la capa de gestión de memoria AGI de UC-296."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MemoryIntent(str, Enum):
    WORKING_STATE = "WORKING_STATE"
    FACTUAL_LOOKUP = "FACTUAL_LOOKUP"
    SEMANTIC_RECALL = "SEMANTIC_RECALL"
    SELF_MODEL = "SELF_MODEL"


@dataclass
class MemoryResult:
    intent: MemoryIntent
    source: str
    data: Any
    latency_ms: float = 0.0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "source": self.source,
            "data": self.data,
            "latency_ms": round(self.latency_ms, 4),
            "confidence": round(self.confidence, 6),
            "metadata": self.metadata,
        }


@dataclass
class SpotlightItem:
    item_id: str
    item_type: str
    content: Dict[str, Any]
    score: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "content": self.content,
            "score": round(self.score, 6),
            "reason": self.reason,
        }


@dataclass
class PerformanceEpisode:
    episode_id: str
    timestamp: str
    task: str
    success: bool
    metrics: Dict[str, Any]
    context: Dict[str, Any]
    policy_adjustments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "timestamp": self.timestamp,
            "task": self.task,
            "success": self.success,
            "metrics": self.metrics,
            "context": self.context,
            "policy_adjustments": self.policy_adjustments,
        }
