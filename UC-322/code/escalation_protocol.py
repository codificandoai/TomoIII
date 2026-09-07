"""Protocolo de escalación formal — Nivel 4 de resolución.

Cuando los niveles 1-3 no resuelven el conflicto, se escala al
orquestador de nivel superior (GeneralOrchestrator / MetacognitiveMonitor).

El orquestador decide:
- PROCEED: continuar con la mejor opción disponible.
- REVIEW: requiere revisión humana antes de continuar.
- STOP: detener la operación.
- REASSIGN: reasignar la tarea a otro agente o dominio.

La decisión se basa en:
- Severidad del conflicto.
- Historial de conflictos similares.
- Estado del circuit breaker.
- Homeostasis del sistema.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from conflict_models import (
    Conflict,
    ConflictSeverity,
    EscalationResult,
    EscalationVerdict,
    NegotiationResult,
    VotingResult,
    CNPResult,
)


@dataclass
class EscalationConfig:
    """Configuración del protocolo de escalación."""
    max_escalations_per_hour: int = 10
    require_human_review_severity: ConflictSeverity = ConflictSeverity.HIGH
    circuit_breaker_threshold: int = 3  # Conflictos consecutivos antes de STOP
    homeostasis_check: bool = True


class EscalationProtocol:
    """Protocolo formal de escalación al orquestador de nivel superior.

    Implementa el Nivel 4 de resolución de conflictos. Conecta con
    la arquitectura UC-315 existente: GeneralOrchestrator y
    MetacognitiveMonitor actúan como este nivel superior.
    """

    def __init__(self, config: Optional[EscalationConfig] = None) -> None:
        self.config = config or EscalationConfig()
        self._escalation_history: List[EscalationResult] = []
        self._consecutive_conflicts: int = 0
        self._circuit_breaker_open: bool = False

    def escalate(
        self,
        conflict: Conflict,
        negotiation_result: Optional[NegotiationResult] = None,
        voting_result: Optional[VotingResult] = None,
        cnp_result: Optional[CNPResult] = None,
    ) -> EscalationResult:
        """Escala el conflicto al orquestador de nivel superior.

        Args:
            conflict: Conflicto no resuelto en niveles 1-3.
            negotiation_result: Resultado de la negociación (Nivel 1).
            voting_result: Resultado de la votación (Nivel 2).
            cnp_result: Resultado del CNP (Nivel 3).

        Returns:
            EscalationResult con el veredicto del orquestador.
        """
        self._consecutive_conflicts += 1

        # Verificar circuit breaker
        if self._consecutive_conflicts >= self.config.circuit_breaker_threshold:
            self._circuit_breaker_open = True

        # Determinar veredicto
        verdict = self._decide_verdict(
            conflict, negotiation_result, voting_result, cnp_result
        )

        # Construir razonamiento
        reasoning = self._build_reasoning(
            conflict, verdict, negotiation_result, voting_result, cnp_result
        )

        # Acciones a tomar
        actions = self._determine_actions(verdict, conflict)

        # ¿Requiere revisión humana?
        requires_human = (
            conflict.severity.value >= self.config.require_human_review_severity.value
            or verdict == EscalationVerdict.STOP
        )

        result = EscalationResult(
            conflict_id=conflict.conflict_id,
            verdict=verdict,
            decided_by="GeneralOrchestrator/MetacognitiveMonitor",
            reasoning=reasoning,
            actions=actions,
            requires_human_review=requires_human,
        )

        self._escalation_history.append(result)

        # Reset circuit breaker si se resuelve
        if verdict in (EscalationVerdict.PROCEED, EscalationVerdict.REASSIGN):
            self._consecutive_conflicts = 0
            self._circuit_breaker_open = False

        return result

    def _decide_verdict(
        self,
        conflict: Conflict,
        negotiation: Optional[NegotiationResult],
        voting: Optional[VotingResult],
        cnp: Optional[CNPResult],
    ) -> EscalationVerdict:
        """Decide el veredicto basado en la evidencia de niveles 1-3."""
        # Circuit breaker abierto → STOP
        if self._circuit_breaker_open:
            return EscalationVerdict.STOP

        # Severidad crítica → STOP
        if conflict.severity == ConflictSeverity.CRITICAL:
            return EscalationVerdict.STOP

        # Severidad alta → REVIEW
        if conflict.severity == ConflictSeverity.HIGH:
            return EscalationVerdict.REVIEW

        # Si el CNP encontró un ganador → REASSIGN al ganador
        if cnp and cnp.winner:
            return EscalationVerdict.REASSIGN

        # Si la votación tiene un ganador claro → PROCEED
        if voting and voting.winner and voting.winner_score > 0.5:
            return EscalationVerdict.PROCEED

        # Si la negociación casi llegó a acuerdo → PROCEED con el promedio
        if negotiation and negotiation.remaining_gap < 0.15:
            return EscalationVerdict.PROCEED

        # Default → REVIEW
        return EscalationVerdict.REVIEW

    def _build_reasoning(
        self,
        conflict: Conflict,
        verdict: EscalationVerdict,
        negotiation: Optional[NegotiationResult],
        voting: Optional[VotingResult],
        cnp: Optional[CNPResult],
    ) -> str:
        """Construye el razonamiento del veredicto."""
        parts = [f"Conflicto {conflict.conflict_id} tipo={conflict.conflict_type.value}"]

        if negotiation:
            parts.append(
                f"Negociación: {'acuerdo' if negotiation.agreement_reached else 'sin acuerdo'}"
                f" (gap={negotiation.remaining_gap:.3f})"
            )

        if voting:
            parts.append(
                f"Votación: ganador={voting.winner} score={voting.winner_score:.3f}"
                f" consenso={'sí' if voting.consensus_reached else 'no'}"
            )

        if cnp:
            parts.append(
                f"CNP: ganador={cnp.winner} score={cnp.winner_score:.3f}"
            )

        if self._circuit_breaker_open:
            parts.append(f"Circuit breaker abierto ({self._consecutive_conflicts} conflictos consecutivos)")

        parts.append(f"Veredicto: {verdict.value}")
        return " | ".join(parts)

    def _determine_actions(
        self,
        verdict: EscalationVerdict,
        conflict: Conflict,
    ) -> List[str]:
        """Determina las acciones a tomar según el veredicto."""
        if verdict == EscalationVerdict.PROCEED:
            return [
                "Continuar con la mejor opción disponible",
                "Registrar conflicto en audit log",
                "Notificar a agentes involucrados",
            ]
        elif verdict == EscalationVerdict.REVIEW:
            return [
                "Pausar ejecución",
                "Solicitar revisión humana",
                "Registrar en audit log para trazabilidad",
                "Notificar al equipo de gobernanza",
            ]
        elif verdict == EscalationVerdict.STOP:
            return [
                "Detener todas las operaciones del dominio",
                "Activar circuit breaker",
                "Alertar al equipo SRE on-call",
                "Registrar incidente crítico",
            ]
        elif verdict == EscalationVerdict.REASSIGN:
            return [
                "Reasignar tarea al agente ganador del CNP",
                "Actualizar reputación de agentes",
                "Registrar reasignación en audit log",
            ]
        return []

    @property
    def circuit_breaker_open(self) -> bool:
        return self._circuit_breaker_open

    @property
    def consecutive_conflicts(self) -> int:
        return self._consecutive_conflicts

    def reset_circuit_breaker(self) -> None:
        """Resetea el circuit breaker manualmente."""
        self._circuit_breaker_open = False
        self._consecutive_conflicts = 0

    def get_history(self) -> List[Dict[str, Any]]:
        """Retorna el historial de escalaciones."""
        return [e.to_dict() for e in self._escalation_history]
