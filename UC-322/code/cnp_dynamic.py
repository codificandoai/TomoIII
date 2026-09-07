"""CNP con pujas dinámicas — Nivel 3 de resolución.

Extiende el Contract Net Protocol original con:
- Reputación dinámica (no estática) en el score de adjudicación.
- Score compuesto: bid + confianza + reputación - costo.
- Pujas en tiempo real donde los agentes ajustan su bid según
  la competencia.

Fórmula de adjudicación:
    composite_score = w_bid * bid_score
                    + w_conf * confidence
                    + w_rep * reputation
                    - w_cost * estimated_cost
                    - w_lat * normalized_latency
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from conflict_models import (
    CNPBid,
    CNPResult,
    Conflict,
)
from reputation_system import ReputationSystem


@dataclass
class CNPConfig:
    """Configuración del CNP dinámico."""
    weight_bid: float = 0.35
    weight_confidence: float = 0.25
    weight_reputation: float = 0.25
    weight_cost: float = 0.10
    weight_latency: float = 0.05
    max_latency_ms: float = 5000.0
    min_composite_score: float = 0.3  # Mínimo para adjudicar


class DynamicCNP:
    """Contract Net Protocol con pujas dinámicas y reputación.

    Implementa el Nivel 3 de resolución de conflictos. Cuando la
    negociación y la votación no resuelven el conflicto, los agentes
    pujan dinámicamente por la propiedad de la tarea.
    """

    def __init__(
        self,
        reputation_system: ReputationSystem,
        config: Optional[CNPConfig] = None,
    ) -> None:
        self.reputation = reputation_system
        self.config = config or CNPConfig()

    def run_bidding(
        self,
        conflict: Conflict,
        task_id: str,
        agent_bids: List[Dict[str, Any]],
    ) -> CNPResult:
        """Ejecuta una ronda de pujas dinámicas.

        Args:
            conflict: Conflicto que originó la puja.
            task_id: ID de la tarea en disputa.
            agent_bids: Lista de pujas de agentes con:
                - agent_id
                - bid_score (0-1)
                - confidence (0-1)
                - estimated_cost (0-1, normalizado)
                - estimated_latency_ms

        Returns:
            CNPResult con el ganador y score compuesto.
        """
        bids: List[CNPBid] = []

        for raw in agent_bids:
            agent_id = raw["agent_id"]
            rep = self.reputation.get_reputation(agent_id, conflict.domain)

            bid = CNPBid(
                agent_id=agent_id,
                task_id=task_id,
                bid_score=raw.get("bid_score", 0.5),
                confidence=raw.get("confidence", 0.5),
                reputation=rep,
                estimated_cost=raw.get("estimated_cost", 0.1),
                estimated_latency_ms=raw.get("estimated_latency_ms", 1000.0),
            )
            bid.composite_score = self._compute_composite(bid)
            bids.append(bid)

        # Ordenar por score compuesto descendente
        bids.sort(key=lambda b: b.composite_score, reverse=True)

        # Adjudicar al mejor si supera el mínimo
        winner = None
        winner_score = 0.0
        if bids and bids[0].composite_score >= self.config.min_composite_score:
            winner = bids[0].agent_id
            winner_score = bids[0].composite_score

        return CNPResult(
            conflict_id=conflict.conflict_id,
            task_id=task_id,
            bids=bids,
            winner=winner,
            winner_score=winner_score,
        )

    def _compute_composite(self, bid: CNPBid) -> float:
        """Calcula el score compuesto de una puja."""
        normalized_latency = bid.estimated_latency_ms / self.config.max_latency_ms
        normalized_latency = min(1.0, normalized_latency)

        score = (
            self.config.weight_bid * bid.bid_score
            + self.config.weight_confidence * bid.confidence
            + self.config.weight_reputation * bid.reputation
            - self.config.weight_cost * bid.estimated_cost
            - self.config.weight_latency * normalized_latency
        )
        return max(0.0, min(1.0, score))

    def generate_bids_from_beliefs(
        self,
        conflict: Conflict,
        task_id: str,
    ) -> List[Dict[str, Any]]:
        """Genera pujas automáticas a partir de las creencias del conflicto."""
        bids = []
        for belief in conflict.beliefs:
            bids.append({
                "agent_id": belief.agent_id,
                "bid_score": belief.confidence,
                "confidence": belief.confidence,
                "estimated_cost": 0.1,
                "estimated_latency_ms": 500.0,
            })
        return bids
