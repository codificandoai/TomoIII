"""Memoria del agente: observaciones, creencias, trazas y estado del entorno."""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional

from models import Observation, StepResult


class AgentMemory:
    """Almacena historia de percepciones, acciones y creencias del agente."""

    def __init__(self, max_observations: int = 1000) -> None:
        self.observations: deque = deque(maxlen=max_observations)
        self.actions: List[Dict[str, Any]] = []
        self.beliefs: Dict[str, Any] = {}
        self.rewards: List[float] = []
        self.total_reward: float = 0.0

    def store_observation(self, obs: Observation) -> None:
        self.observations.append(obs.to_dict())

    def store_action(self, action: str, result: StepResult) -> None:
        self.actions.append(
            {"action": action, "result": result.to_dict(), "reward": result.reward}
        )
        self.rewards.append(result.reward)
        self.total_reward += result.reward

    def update_belief(self, key: str, value: Any) -> None:
        self.beliefs[key] = value

    def get_belief(self, key: str, default: Any = None) -> Any:
        return self.beliefs.get(key, default)

    def recent_observations(self, n: int = 5) -> List[Dict[str, Any]]:
        return list(self.observations)[-n:]

    def average_reward(self) -> float:
        if not self.rewards:
            return 0.0
        return sum(self.rewards) / len(self.rewards)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_count": len(self.observations),
            "action_count": len(self.actions),
            "total_reward": round(self.total_reward, 4),
            "average_reward": round(self.average_reward(), 4),
            "beliefs": self.beliefs,
        }
