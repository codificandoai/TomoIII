"""Modelos de datos para UC-263 - Q-Learning vectorial turístico."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TravelerContext(BaseModel):
    """Contexto del turista usado como estado para el agente RL."""

    user_id: str = "anonymous"
    age_group: str = Field(default="adult", description="child, teen, adult, senior")
    group_type: str = Field(default="solo", description="solo, couple, family, friends")
    season: str = Field(default="summer")
    budget_level: str = Field(default="medium", description="low, medium, high")
    interests: List[str] = Field(default_factory=list)
    origin: str = Field(default="")
    destination: str = Field(default="")
    mood: str = Field(default="")

    def describe(self) -> str:
        parts = [
            f"{self.group_type}",
            f"{self.age_group}",
            f"in {self.season}",
            f"budget {self.budget_level}",
            f"interested in {', '.join(self.interests)}" if self.interests else "",
        ]
        base = " ".join(p.strip() for p in parts if p.strip())
        if self.destination:
            base += f" traveling to {self.destination}"
        if self.mood:
            base += f" feeling {self.mood}"
        return base.strip() or "generic traveler"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TravelerContext":
        return cls(**data)


class RLExperience(BaseModel):
    """Una experiencia (state, action, reward, q_value) almacenada en memoria vectorial."""

    experience_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = "anonymous"
    state_context: str
    state_embedding: List[float] = Field(default_factory=list)
    action: str
    reward: float = 0.0
    q_value: float = 0.0
    next_state_context: str = ""
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RLExperience":
        return cls(**data)


class Recommendation(BaseModel):
    """Recomendación emitida por el agente RL."""

    recommendation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = "anonymous"
    context: str
    action: str
    q_value: float
    confidence: float = 0.0
    exploration: bool = False
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TrainingStats(BaseModel):
    """Estadísticas de entrenamiento RL."""

    episodes: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    best_action_counts: Dict[str, int] = Field(default_factory=dict)
    final_epsilon: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
