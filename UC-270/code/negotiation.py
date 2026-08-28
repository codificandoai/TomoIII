"""Motor de negociación bilateral/multilateral (inspirado en NegMAS) para UC-270.

Implementa negociación con rondas, concesiones progresivas y zona de acuerdo.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional
from uuid import UUID

from config import NegotiationConfig, get_config
from models import (
    AgentProfile,
    DetectedConflict,
    NegotiationOffer,
    NegotiationResult,
    NegotiationRound,
    ResolutionStrategy,
)


class NegotiationEngine:
    """Motor de negociación con concesiones progresivas."""

    def __init__(self, config: Optional[NegotiationConfig] = None) -> None:
        self.config = config or get_config().negotiation

    def negotiate(
        self,
        conflict: DetectedConflict,
        profiles: Dict[str, AgentProfile],
    ) -> NegotiationResult:
        """Ejecuta negociación bilateral/multilateral sobre un conflicto detectado."""
        agents = conflict.claimants
        claims_by_agent = {c.agent_name: c for c in conflict.claims}
        rounds: List[NegotiationRound] = []

        # Posiciones iniciales: cada agente demanda toda su necesidad
        positions: Dict[str, float] = {
            name: claims_by_agent[name].need for name in agents
        }
        # Flexibilidad disponible para conceder
        flex: Dict[str, float] = {
            name: profiles[name].flexibility for name in agents
        }

        for round_num in range(1, self.config.max_rounds + 1):
            offers: List[NegotiationOffer] = []
            total = sum(positions.values())

            for name in agents:
                # Concesión: reduce posición proporcionalmente a la flexibilidad
                concession = self.config.concession_rate * flex[name] * round_num / self.config.max_rounds
                offered = max(0.05, positions[name] - concession)
                offers.append(
                    NegotiationOffer(
                        round_number=round_num,
                        agent_name=name,
                        offered_share=offered,
                        concession=concession,
                    )
                )
                positions[name] = offered

            # Verificar si hay acuerdo: la suma de shares <= 1.0 + margen
            new_total = sum(o.offered_share for o in offers)
            agreement = new_total <= 1.05

            # O bien si la probabilidad de acuerdo se cumple
            if not agreement:
                avg_skill = sum(profiles[a].negotiation_skill for a in agents) / len(agents)
                avg_flex = sum(flex[a] for a in agents) / len(agents)
                prob = self.config.agreement_base_prob + 0.25 * avg_skill + 0.20 * avg_flex + 0.05 * round_num
                agreement = random.random() < prob

            allocation = None
            if agreement:
                # Normaliza shares
                raw = {o.agent_name: o.offered_share for o in offers}
                total_raw = sum(raw.values())
                allocation = {k: round(v / total_raw, 4) for k, v in raw.items()}
                for o in offers:
                    o.accepted = True

            rounds.append(
                NegotiationRound(
                    round_number=round_num,
                    offers=offers,
                    agreement_reached=agreement,
                    agreement_share=allocation,
                )
            )

            if agreement:
                return NegotiationResult(
                    conflict_id=conflict.conflict_id,
                    rounds=rounds,
                    total_rounds=round_num,
                    agreement_reached=True,
                    final_allocation=allocation,
                )

        # Deadlock
        return NegotiationResult(
            conflict_id=conflict.conflict_id,
            rounds=rounds,
            total_rounds=self.config.max_rounds,
            agreement_reached=False,
        )
