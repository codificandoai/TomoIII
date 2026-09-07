"""Motor de negociación con concesiones — Nivel 1 de resolución.

Reemplaza la validación binaria de Juice (aprobar/bloquear) con un
protocolo de negociación donde los agentes intercambian creencias,
hacen concesiones graduales y llegan a acuerdos sin escalación.

Algoritmo:
1. Detectar discrepancia entre creencias de agentes.
2. Cada agente propone su posición inicial.
3. En cada ronda, cada agente hace una concesión proporcional a:
   - Su flexibilidad (inversa de su confianza)
   - La reputación del otro agente
   - El número de ronda (concesiones mayores en rondas tempranas)
4. Si la brecha (gap) cae bajo el umbral → acuerdo.
5. Si se agotan las rondas → escalar al Nivel 2.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from conflict_models import (
    AgentBelief,
    Conflict,
    Concession,
    NegotiationResult,
)
from reputation_system import ReputationSystem


@dataclass
class NegotiationConfig:
    """Configuración del motor de negociación."""
    max_rounds: int = 5
    agreement_threshold: float = 0.05  # Brecha máxima para considerar acuerdo
    min_concession_step: float = 0.02  # Concesión mínima por ronda
    max_concession_step: float = 0.15  # Concesión máxima por ronda
    flexibility_factor: float = 0.3    # Cuánto cede un agente (inverso a confianza)
    reputation_influence: float = 0.4  # Cuánto influye la reputación del otro


class NegotiationEngine:
    """Motor de negociación con concesiones entre agentes.

    Implementa el Nivel 1 de resolución de conflictos. Los agentes
    intercambian creencias y hacen concesiones graduales para llegar
    a un acuerdo sin necesidad de escalación.
    """

    def __init__(
        self,
        reputation_system: ReputationSystem,
        config: Optional[NegotiationConfig] = None,
    ) -> None:
        self.reputation = reputation_system
        self.config = config or NegotiationConfig()

    def negotiate(self, conflict: Conflict) -> NegotiationResult:
        """Ejecuta el proceso de negociación para un conflicto.

        Args:
            conflict: Conflicto con las creencias de los agentes.

        Returns:
            NegotiationResult con concesiones y acuerdo (o no).
        """
        if len(conflict.beliefs) < 2:
            return NegotiationResult(
                conflict_id=conflict.conflict_id,
                round_number=0,
                agreement_reached=True,
                agreed_value=conflict.beliefs[0].confidence if conflict.beliefs else None,
            )

        # Extraer posiciones iniciales (usamos confidence como posición)
        positions: Dict[str, float] = {
            b.agent_id: b.confidence for b in conflict.beliefs
        }
        original_positions = dict(positions)
        all_concessions: List[Concession] = []

        for round_num in range(1, self.config.max_rounds + 1):
            round_concessions = self._negotiate_round(
                conflict, positions, original_positions, round_num
            )
            all_concessions.extend(round_concessions)

            # Verificar acuerdo
            gap = self._compute_gap(positions)
            if gap <= self.config.agreement_threshold:
                agreed = sum(positions.values()) / len(positions)
                result = NegotiationResult(
                    conflict_id=conflict.conflict_id,
                    round_number=round_num,
                    concessions=all_concessions,
                    agreement_reached=True,
                    agreed_value=round(agreed, 6),
                    remaining_gap=round(gap, 6),
                )
                return result

        # No se llegó a acuerdo
        gap = self._compute_gap(positions)
        return NegotiationResult(
            conflict_id=conflict.conflict_id,
            round_number=self.config.max_rounds,
            concessions=all_concessions,
            agreement_reached=False,
            remaining_gap=round(gap, 6),
        )

    def _negotiate_round(
        self,
        conflict: Conflict,
        positions: Dict[str, float],
        original_positions: Dict[str, float],
        round_num: int,
    ) -> List[Concession]:
        """Ejecuta una ronda de negociación."""
        concessions: List[Concession] = []
        agent_ids = list(positions.keys())

        for agent_id in agent_ids:
            # La concesión depende de:
            # 1. Flexibilidad (inverso de confianza)
            # 2. Reputación de los otros agentes
            # 3. Ronda actual (mayor concesión en rondas tempranas)

            my_belief = next(
                (b for b in conflict.beliefs if b.agent_id == agent_id),
                None,
            )
            if my_belief is None:
                continue

            # Flexibilidad: menor confianza → mayor flexibilidad
            flexibility = (1.0 - my_belief.confidence) * self.config.flexibility_factor

            # Influencia de reputación de otros agentes
            other_ids = [a for a in agent_ids if a != agent_id]
            other_reps = [
                self.reputation.get_reputation(a, conflict.domain)
                for a in other_ids
            ]
            avg_other_rep = sum(other_reps) / len(other_reps) if other_reps else 0.5

            # Decay por ronda: concesiones menores en rondas tardías
            round_decay = 1.0 / (1.0 + round_num * 0.3)

            # Posición promedio de los otros
            other_positions = [positions[a] for a in other_ids]
            avg_other = sum(other_positions) / len(other_positions) if other_positions else positions[agent_id]

            # Dirección de la concesión: moverse hacia el promedio de los otros
            direction = 1.0 if avg_other > positions[agent_id] else -1.0

            # Magnitud de la concesión
            step = (
                self.config.min_concession_step
                + (self.config.max_concession_step - self.config.min_concession_step)
                * flexibility
                * avg_other_rep
                * self.config.reputation_influence
                * round_decay
            )
            step = max(self.config.min_concession_step, min(self.config.max_concession_step, step))

            old_pos = positions[agent_id]
            new_pos = old_pos + direction * step
            new_pos = max(0.0, min(1.0, new_pos))

            if abs(new_pos - old_pos) > 1e-9:
                positions[agent_id] = new_pos
                concession = Concession(
                    agent_id=agent_id,
                    original_position=original_positions[agent_id],
                    conceded_position=new_pos,
                    reason=f"Ronda {round_num}: flex={flexibility:.3f} rep_other={avg_other_rep:.3f} decay={round_decay:.3f}",
                )
                concessions.append(concession)

        return concessions

    def _compute_gap(self, positions: Dict[str, float]) -> float:
        """Computa la brecha entre la posición máxima y mínima."""
        if not positions:
            return 0.0
        vals = list(positions.values())
        return max(vals) - min(vals)

    def detect_conflict(
        self,
        beliefs: List[AgentBelief],
        domain: str = "trading",
        threshold: float = 0.15,
    ) -> Optional[Conflict]:
        """Detecta si hay un conflicto entre las creencias de los agentes.

        Args:
            beliefs: Lista de creencias de agentes.
            domain: Dominio de los agentes.
            threshold: Brecha mínima para considerar conflicto.

        Returns:
            Conflict si hay discrepancia, None en caso contrario.
        """
        if len(beliefs) < 2:
            return None

        confidences = [b.confidence for b in beliefs]
        gap = max(confidences) - min(confidences)

        if gap < threshold:
            return None

        from conflict_models import (
            ConflictType,
            ConflictSeverity,
            ResolutionStatus,
        )

        severity = ConflictSeverity.LOW if gap < 0.3 else ConflictSeverity.MEDIUM

        return Conflict(
            conflict_type=ConflictType.BELIEF_DISAGREEMENT,
            severity=severity,
            domain=domain,
            agents_involved=[b.agent_id for b in beliefs],
            beliefs=beliefs,
            description=f"Discrepancia de {gap:.3f} entre {len(beliefs)} agentes",
            resolution_status=ResolutionStatus.DETECTED,
        )
