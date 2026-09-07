"""Sistema de reputación dinámica para agentes multiagente.

La reputación se actualiza con cada episodio de ejecución, permitiendo
ponderar la información aportada por los agentes según su historial
de éxito, calidad y eficiencia.

Fórmula de reputación:
    reputation = clamp(
        0.50  # base
        + 0.30 * success_rate
        + 0.15 * avg_quality
        + 0.05 * avg_efficiency
        - penalty * recent_failures
    , 0.0, 1.0)

Esto reemplaza el `reliability` estático del CNP original.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from conflict_models import AgentBelief


@dataclass
class EpisodeRecord:
    """Registro de un episodio de ejecución de un agente."""
    agent_id: str
    task_id: str
    success: bool
    quality: float = 0.0   # 0-1 (confidence * coherence)
    efficiency: float = 0.0  # 0-1 (1 - tokens/max - latency/max)
    timestamp: float = field(default_factory=time.time)
    domain: str = "trading"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "success": self.success,
            "quality": round(self.quality, 4),
            "efficiency": round(self.efficiency, 4),
            "timestamp": self.timestamp,
            "domain": self.domain,
        }


@dataclass
class ReputationEntry:
    """Entrada de reputación de un agente."""
    agent_id: str
    reputation: float = 0.5       # 0.0 - 1.0
    total_episodes: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_quality: float = 0.5
    avg_efficiency: float = 0.5
    recent_failures: int = 0
    last_updated: float = field(default_factory=time.time)
    domain: str = "trading"
    history: List[EpisodeRecord] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_episodes == 0:
            return 0.5
        return self.success_count / self.total_episodes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "reputation": round(self.reputation, 4),
            "total_episodes": self.total_episodes,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "avg_quality": round(self.avg_quality, 4),
            "avg_efficiency": round(self.avg_efficiency, 4),
            "recent_failures": self.recent_failures,
            "last_updated": self.last_updated,
            "domain": self.domain,
        }


class ReputationSystem:
    """Sistema de reputación dinámica que se actualiza por episodio.

    Mantiene un registro por agente y por dominio. La reputación
    se recalcula tras cada episodio usando una fórmula ponderada
    que considera éxito, calidad y eficiencia.
    """

    # Pesos de la fórmula de reputación
    BASE_REPUTATION = 0.50
    WEIGHT_SUCCESS = 0.30
    WEIGHT_QUALITY = 0.15
    WEIGHT_EFFICIENCY = 0.05
    PENALTY_RECENT_FAILURES = 0.10
    MAX_RECENT_FAILURES_WINDOW = 5
    MAX_HISTORY = 100  # Máximo episodios a conservar por agente

    def __init__(self) -> None:
        self._reputations: Dict[str, ReputationEntry] = {}
        self._domain_reputations: Dict[str, Dict[str, ReputationEntry]] = {}

    def register_agent(self, agent_id: str, domain: str = "trading") -> None:
        """Registra un agente con reputación inicial."""
        key = self._key(agent_id, domain)
        if key not in self._reputations:
            entry = ReputationEntry(agent_id=agent_id, domain=domain)
            self._reputations[key] = entry
            if domain not in self._domain_reputations:
                self._domain_reputations[domain] = {}
            self._domain_reputations[domain][agent_id] = entry

    def _key(self, agent_id: str, domain: str) -> str:
        return f"{domain}:{agent_id}"

    def get_reputation(self, agent_id: str, domain: str = "trading") -> float:
        """Retorna la reputación actual del agente."""
        key = self._key(agent_id, domain)
        entry = self._reputations.get(key)
        if entry is None:
            return self.BASE_REPUTATION
        return entry.reputation

    def get_entry(self, agent_id: str, domain: str = "trading") -> ReputationEntry:
        """Retorna la entrada completa de reputación."""
        key = self._key(agent_id, domain)
        entry = self._reputations.get(key)
        if entry is None:
            self.register_agent(agent_id, domain)
            return self._reputations[key]
        return entry

    def record_episode(
        self,
        agent_id: str,
        task_id: str,
        success: bool,
        quality: float = 0.5,
        efficiency: float = 0.5,
        domain: str = "trading",
    ) -> float:
        """Registra un episodio y recalcula la reputación.

        Args:
            agent_id: ID del agente.
            task_id: ID de la tarea ejecutada.
            success: Si la tarea fue exitosa.
            quality: Calidad del resultado (0-1).
            efficiency: Eficiencia del resultado (0-1).
            domain: Dominio de la tarea.

        Returns:
            Nueva reputación del agente.
        """
        self.register_agent(agent_id, domain)
        key = self._key(agent_id, domain)
        entry = self._reputations[key]

        # Registrar episodio
        record = EpisodeRecord(
            agent_id=agent_id,
            task_id=task_id,
            success=success,
            quality=max(0.0, min(1.0, quality)),
            efficiency=max(0.0, min(1.0, efficiency)),
            domain=domain,
        )
        entry.history.append(record)
        if len(entry.history) > self.MAX_HISTORY:
            entry.history = entry.history[-self.MAX_HISTORY:]

        entry.total_episodes += 1
        if success:
            entry.success_count += 1
            entry.recent_failures = 0
        else:
            entry.failure_count += 1
            entry.recent_failures = min(
                entry.recent_failures + 1,
                self.MAX_RECENT_FAILURES_WINDOW,
            )

        # Recalcular promedios
        if entry.history:
            entry.avg_quality = sum(r.quality for r in entry.history) / len(entry.history)
            entry.avg_efficiency = sum(r.efficiency for r in entry.history) / len(entry.history)

        # Recalcular reputación
        entry.reputation = self._compute_reputation(entry)
        entry.last_updated = time.time()

        return entry.reputation

    def _compute_reputation(self, entry: ReputationEntry) -> float:
        """Calcula la reputación usando la fórmula ponderada."""
        rep = (
            self.BASE_REPUTATION
            + self.WEIGHT_SUCCESS * entry.success_rate
            + self.WEIGHT_QUALITY * entry.avg_quality
            + self.WEIGHT_EFFICIENCY * entry.avg_efficiency
            - self.PENALTY_RECENT_FAILURES * entry.recent_failures
        )
        return max(0.0, min(1.0, rep))

    def weight_belief(self, belief: AgentBelief, domain: str = "trading") -> float:
        """Pondera la creencia de un agente según su reputación.

        Args:
            belief: Creencia del agente.
            domain: Dominio del agente.

        Returns:
            Peso = reputación * confianza de la creencia.
        """
        rep = self.get_reputation(belief.agent_id, domain)
        return rep * belief.confidence

    def get_ranking(self, domain: str = "trading", top_n: int = 10) -> List[Dict[str, Any]]:
        """Retorna el ranking de agentes por reputación en un dominio."""
        domain_entries = self._domain_reputations.get(domain, {})
        sorted_agents = sorted(
            domain_entries.values(),
            key=lambda e: e.reputation,
            reverse=True,
        )
        return [e.to_dict() for e in sorted_agents[:top_n]]

    def list_all(self) -> List[Dict[str, Any]]:
        """Lista todas las entradas de reputación."""
        return [e.to_dict() for e in self._reputations.values()]

    def reset(self) -> None:
        """Reinicia todo el sistema de reputación."""
        self._reputations.clear()
        self._domain_reputations.clear()
