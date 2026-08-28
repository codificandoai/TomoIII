"""Trust scoring bayesiano para UC-273.

Cada agente tiene confianza basada en Beta(alpha, beta):
- Trust = alpha / (alpha + beta)
- Actualización bayesiana con éxitos/fallos.
- Decay temporal: la confianza se oxida sin uso.
- Quarantine automático bajo umbral.
- Trust propagation entre agentes.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from config import TrustConfig, get_config


@dataclass
class TrustScore:
    """Puntuación de confianza bayesiana Beta(alpha, beta)."""
    alpha: float = 1.0
    beta: float = 1.0
    last_updated: float = field(default_factory=time.time)
    decay_rate: float = 0.001

    @property
    def trust(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def uncertainty(self) -> float:
        total = self.alpha + self.beta
        return (self.alpha * self.beta) / ((total ** 2) * (total + 1))

    @property
    def lower_bound(self) -> float:
        """Límite inferior Wilson con 95% de confianza."""
        n = self.alpha + self.beta
        if n == 0:
            return 0.0
        z = 1.96
        phat = self.alpha / n
        denominator = 1 + z * z / n
        if denominator == 0:
            return 0.0
        center = phat + z * z / (2 * n)
        spread = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
        return (center - spread) / denominator

    def record_success(self, weight: float = 1.0) -> None:
        self.alpha += weight
        self.last_updated = time.time()

    def record_failure(self, weight: float = 1.0) -> None:
        self.beta += weight
        self.last_updated = time.time()

    def apply_decay(self) -> None:
        elapsed = time.time() - self.last_updated
        decay = math.exp(-self.decay_rate * elapsed)
        self.alpha = 1.0 + (self.alpha - 1.0) * decay
        self.beta = 1.0 + (self.beta - 1.0) * decay


class TrustRegistry:
    """Registro de confianza de agentes con quarantine."""

    def __init__(self, config: TrustConfig | None = None) -> None:
        self.config = config or get_config().trust
        self.scores: Dict[str, TrustScore] = defaultdict(
            lambda: TrustScore(decay_rate=self.config.decay_rate)
        )
        self._quarantined: Set[str] = set()
        self._history: List[Tuple[str, float, float]] = []

    def record(self, agent_id: str, success: bool, weight: float = 1.0) -> float:
        score = self.scores[agent_id]
        score.apply_decay()

        if success:
            score.record_success(weight)
        else:
            score.record_failure(weight * self.config.failure_weight_multiplier)

        self._history.append((agent_id, score.trust, time.time()))

        if score.trust < self.config.quarantine_threshold:
            self._quarantined.add(agent_id)
        elif score.trust > self.config.trusted_threshold:
            self._quarantined.discard(agent_id)

        return score.trust

    def get_trust(self, agent_id: str) -> float:
        score = self.scores[agent_id]
        score.apply_decay()
        return score.trust

    def is_quarantined(self, agent_id: str) -> bool:
        return agent_id in self._quarantined

    def quarantine(self, agent_id: str) -> None:
        self._quarantined.add(agent_id)

    def unquarantine(self, agent_id: str) -> None:
        self._quarantined.discard(agent_id)

    def get_trusted_agents(self) -> List[str]:
        return [
            aid for aid, score in self.scores.items()
            if score.trust >= self.config.trusted_threshold
            and aid not in self._quarantined
        ]

    def get_suspicious_agents(self) -> List[Tuple[str, float]]:
        suspicious = []
        for aid, score in self.scores.items():
            if score.trust < 0.5 or score.uncertainty > 0.1:
                suspicious.append((aid, score.trust))
        return sorted(suspicious, key=lambda x: x[1])

    def get_score_model(self, agent_id: str) -> dict:
        score = self.scores[agent_id]
        return {
            "agent_id": agent_id,
            "alpha": round(score.alpha, 4),
            "beta": round(score.beta, 4),
            "trust": round(score.trust, 4),
            "uncertainty": round(score.uncertainty, 6),
            "lower_bound": round(score.lower_bound, 4),
            "is_quarantined": agent_id in self._quarantined,
        }
