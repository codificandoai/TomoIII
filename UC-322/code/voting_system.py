"""Sistema de votación ponderada por reputación — Nivel 2 de resolución.

Cuando la negociación (Nivel 1) no llega a acuerdo, los agentes votan.
El peso de cada voto se calcula según la reputación dinámica del agente,
no por un peso fijo. Esto asegura que los agentes con mejor historial
tengan mayor influencia en la decisión.

Algoritmo:
1. Cada agente emite su voto por una opción.
2. El peso del voto = reputación * confianza_en_la_opción.
3. Se suman los pesos por opción.
4. La opción con mayor peso total gana.
5. Si el ganador supera el umbral de consenso → acuerdo.
6. Si no → escalar al Nivel 3 (CNP).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from conflict_models import (
    Conflict,
    Vote,
    VotingResult,
)
from reputation_system import ReputationSystem


@dataclass
class VotingConfig:
    """Configuración del sistema de votación."""
    consensus_threshold: float = 0.60  # % del peso total para consenso
    min_voters: int = 2
    allow_abstention: bool = True


class VotingSystem:
    """Sistema de votación ponderada por reputación dinámica.

    Implementa el Nivel 2 de resolución de conflictos. Reemplaza
    el voto ponderado estático (0.35/0.25/0.15) del trading_agents.py
    original con pesos dinámicos basados en reputación.
    """

    def __init__(
        self,
        reputation_system: ReputationSystem,
        config: Optional[VotingConfig] = None,
    ) -> None:
        self.reputation = reputation_system
        self.config = config or VotingConfig()

    def vote(
        self,
        conflict: Conflict,
        options: List[str],
        agent_preferences: Dict[str, str],  # agent_id -> option
        agent_confidence: Optional[Dict[str, float]] = None,
    ) -> VotingResult:
        """Ejecuta una votación ponderada por reputación.

        Args:
            conflict: Conflicto a resolver.
            options: Lista de opciones votables.
            agent_preferences: Preferencia de cada agente (agent_id -> option).
            agent_confidence: Confianza de cada agente en su opción (opcional).

        Returns:
            VotingResult con el ganador y si se alcanzó consenso.
        """
        votes: List[Vote] = []
        agent_confidence = agent_confidence or {}

        for agent_id, option in agent_preferences.items():
            if option not in options:
                continue

            rep = self.reputation.get_reputation(agent_id, conflict.domain)
            conf = agent_confidence.get(agent_id, 0.5)
            weight = rep * conf

            vote = Vote(
                agent_id=agent_id,
                option=option,
                weight=weight,
                raw_reputation=rep,
                reason=f"rep={rep:.3f} * conf={conf:.3f} = {weight:.3f}",
            )
            votes.append(vote)

        # Contar pesos por opción
        option_weights: Dict[str, float] = {opt: 0.0 for opt in options}
        for v in votes:
            option_weights[v.option] += v.weight

        total_weight = sum(option_weights.values())
        if total_weight == 0:
            return VotingResult(
                conflict_id=conflict.conflict_id,
                votes=votes,
                consensus_threshold=self.config.consensus_threshold,
                consensus_reached=False,
            )

        # Determinar ganador
        winner = max(option_weights, key=option_weights.get)
        winner_score = option_weights[winner] / total_weight

        consensus = winner_score >= self.config.consensus_threshold

        return VotingResult(
            conflict_id=conflict.conflict_id,
            votes=votes,
            winner=winner,
            winner_score=winner_score,
            total_weight=total_weight,
            consensus_threshold=self.config.consensus_threshold,
            consensus_reached=consensus,
        )

    def vote_from_beliefs(
        self,
        conflict: Conflict,
        options: List[str],
        agent_preferences: Optional[Dict[str, str]] = None,
    ) -> VotingResult:
        """Ejecuta votación usando las creencias del conflicto.

        Si agent_preferences se proporciona, lo usa directamente.
        Si no, mapea cada agente a una opción usando un hash determinista
        (MD5) por la posición del agente en la lista de creencias.
        """
        _agent_preferences: Dict[str, str] = {}
        agent_confidence: Dict[str, float] = {}

        if agent_preferences is not None:
            _agent_preferences = agent_preferences
            for belief in conflict.beliefs:
                agent_confidence[belief.agent_id] = belief.confidence
        else:
            for idx, belief in enumerate(conflict.beliefs):
                # Mapeo determinista: opción por índice del agente
                option_idx = idx % len(options)
                _agent_preferences[belief.agent_id] = options[option_idx]
                agent_confidence[belief.agent_id] = belief.confidence

        return self.vote(conflict, options, _agent_preferences, agent_confidence)
