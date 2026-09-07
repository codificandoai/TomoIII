"""UC-322 — Cerebro AGI Multi-Agente Multi-Dominio para Resolución Óptima de Conflictos.

Esta capa envuelve al cerebro AGI (UC-315) con un sistema de resolución
de conflictos de 4 niveles:

    Nivel 1: Negociación directa entre agentes (concesiones)
    Nivel 2: Votación ponderada por reputación dinámica
    Nivel 3: CNP con pujas dinámicas (bid + confianza + reputación - costo)
    Nivel 4: Escalación al GeneralOrchestrator / MetacognitiveMonitor

Además:
- Detecta trabajo duplicado y deadlocks.
- Mantiene reputación dinámica que se actualiza por episodio.
- Emite métricas (Prometheus), logs (Loki) y trazas (Tempo/OpenTelemetry).

Uso:
    from UC_322 import ConflictResolutionLayer, AgentBelief
    layer = ConflictResolutionLayer()
    result = layer.resolve(beliefs=[...], domain="trading")
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from conflict_models import (
    AgentBelief,
    Conflict,
    ConflictResolutionResult,
    ConflictSeverity,
    ConflictType,
    EscalationVerdict,
    ResolutionLevel,
    ResolutionStatus,
)
from reputation_system import ReputationSystem
from negotiation_engine import NegotiationEngine, NegotiationConfig
from voting_system import VotingSystem, VotingConfig
from cnp_dynamic import DynamicCNP, CNPConfig
from escalation_protocol import EscalationProtocol, EscalationConfig
from duplicate_detection import DuplicateDetection, DeadlockDetector
from observability import ObservabilityManager


class ConflictResolutionLayer:
    """Capa de resolución de conflictos para el cerebro AGI.

    Orquesta los 4 niveles de resolución en orden ascendente.
    Si un nivel resuelve el conflicto, no se escalan los siguientes.
    Si ningún nivel resuelve, el conflicto queda como DEADLOCKED.
    """

    def __init__(
        self,
        reputation: Optional[ReputationSystem] = None,
        negotiation_config: Optional[NegotiationConfig] = None,
        voting_config: Optional[VotingConfig] = None,
        cnp_config: Optional[CNPConfig] = None,
        escalation_config: Optional[EscalationConfig] = None,
    ) -> None:
        self.reputation = reputation or ReputationSystem()
        self.negotiation = NegotiationEngine(self.reputation, negotiation_config)
        self.voting = VotingSystem(self.reputation, voting_config)
        self.cnp = DynamicCNP(self.reputation, cnp_config)
        self.escalation = EscalationProtocol(escalation_config)
        self.duplicate_detection = DuplicateDetection()
        self.deadlock_detector = DeadlockDetector()
        self.observability = ObservabilityManager()

        self._resolution_history: List[ConflictResolutionResult] = []

    def resolve(
        self,
        beliefs: List[AgentBelief],
        domain: str = "trading",
        options: Optional[List[str]] = None,
        agent_preferences: Optional[Dict[str, str]] = None,
        task_id: Optional[str] = None,
        agent_bids: Optional[List[Dict[str, Any]]] = None,
    ) -> ConflictResolutionResult:
        """Resuelve un conflicto usando los 4 niveles en orden.

        Args:
            beliefs: Creencias de los agentes en conflicto.
            domain: Dominio de los agentes.
            options: Opciones votables (para Nivel 2).
            agent_preferences: Opción de voto de cada agente (para Nivel 2).
            task_id: ID de la tarea en disputa (para Nivel 3).
            agent_bids: Pujas de agentes (para Nivel 3).

        Returns:
            ConflictResolutionResult con el resultado completo.
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())

        # Span principal
        span = self.observability.start_span(
            operation="conflict_resolution",
            agent_id="UC-322",
            trace_id=trace_id,
            attributes={"domain": domain, "num_beliefs": len(beliefs)},
        )

        # Detectar conflicto
        conflict = self.negotiation.detect_conflict(beliefs, domain)
        if conflict is None:
            # No hay conflicto
            self.observability.end_span(span.span_id, "OK")
            no_conflict = Conflict(
                agents_involved=[b.agent_id for b in beliefs],
                beliefs=beliefs,
                domain=domain,
                resolution_status=ResolutionStatus.RESOLVED,
                resolution_detail={"message": "No conflict detected"},
                trace_id=trace_id,
            )
            result = ConflictResolutionResult(
                conflict=no_conflict,
                level_reached=ResolutionLevel.NEGOTIATION,
                success=True,
                total_duration=time.time() - start_time,
            )
            self._resolution_history.append(result)
            return result

        self.observability.log(
            "INFO",
            f"Conflicto detectado: {conflict.conflict_id}",
            trace_id=trace_id,
            conflict_type=conflict.conflict_type.value,
            severity=conflict.severity.name,
        )

        # ─── Nivel 1: Negociación ─────────────────────────────────────
        conflict.resolution_status = ResolutionStatus.NEGOTIATING
        neg_span = self.observability.start_span(
            operation="negotiation",
            agent_id="UC-322",
            trace_id=trace_id,
            parent_span_id=span.span_id,
        )
        neg_result = self.negotiation.negotiate(conflict)
        self.observability.end_span(neg_span.span_id, "OK" if neg_result.agreement_reached else "BLOCKED")

        self.observability.inc_counter(
            "conflict_negotiation_total",
            labels={"result": "agreement" if neg_result.agreement_reached else "no_agreement"},
        )

        if neg_result.agreement_reached:
            conflict.resolution_status = ResolutionStatus.RESOLVED
            conflict.resolution_level = ResolutionLevel.NEGOTIATION
            conflict.resolution_detail = neg_result.to_dict()
            conflict.resolved_at = time.time()
            self._record_episode(beliefs, domain, success=True, trace_id=trace_id)
            self.observability.end_span(span.span_id, "OK")
            result = ConflictResolutionResult(
                conflict=conflict,
                level_reached=ResolutionLevel.NEGOTIATION,
                negotiation_result=neg_result,
                success=True,
                total_duration=time.time() - start_time,
            )
            self._resolution_history.append(result)
            return result

        # ─── Nivel 2: Votación ────────────────────────────────────────
        conflict.resolution_status = ResolutionStatus.VOTING
        vote_span = self.observability.start_span(
            operation="voting",
            agent_id="UC-322",
            trace_id=trace_id,
            parent_span_id=span.span_id,
        )
        if options is None:
            options = ["option_a", "option_b"]
        vote_result = self.voting.vote_from_beliefs(conflict, options, agent_preferences)
        self.observability.end_span(vote_span.span_id, "OK" if vote_result.consensus_reached else "BLOCKED")

        self.observability.inc_counter(
            "conflict_voting_total",
            labels={"result": "consensus" if vote_result.consensus_reached else "no_consensus"},
        )

        if vote_result.consensus_reached:
            conflict.resolution_status = ResolutionStatus.RESOLVED
            conflict.resolution_level = ResolutionLevel.VOTING
            conflict.resolution_detail = {
                "negotiation": neg_result.to_dict(),
                "voting": vote_result.to_dict(),
            }
            conflict.resolved_at = time.time()
            self._record_episode(beliefs, domain, success=True, trace_id=trace_id)
            self.observability.end_span(span.span_id, "OK")
            result = ConflictResolutionResult(
                conflict=conflict,
                level_reached=ResolutionLevel.VOTING,
                negotiation_result=neg_result,
                voting_result=vote_result,
                success=True,
                total_duration=time.time() - start_time,
            )
            self._resolution_history.append(result)
            return result

        # ─── Nivel 3: CNP con pujas dinámicas ─────────────────────────
        conflict.resolution_status = ResolutionStatus.BIDDING
        cnp_span = self.observability.start_span(
            operation="cnp_bidding",
            agent_id="UC-322",
            trace_id=trace_id,
            parent_span_id=span.span_id,
        )
        if agent_bids is None:
            agent_bids = self.cnp.generate_bids_from_beliefs(conflict, task_id or conflict.conflict_id)
        cnp_result = self.cnp.run_bidding(conflict, task_id or conflict.conflict_id, agent_bids)
        self.observability.end_span(cnp_span.span_id, "OK" if cnp_result.winner else "BLOCKED")

        self.observability.inc_counter(
            "conflict_cnp_total",
            labels={"result": "winner" if cnp_result.winner else "no_winner"},
        )

        if cnp_result.winner:
            conflict.resolution_status = ResolutionStatus.RESOLVED
            conflict.resolution_level = ResolutionLevel.CNP_BIDDING
            conflict.resolution_detail = {
                "negotiation": neg_result.to_dict(),
                "voting": vote_result.to_dict(),
                "cnp": cnp_result.to_dict(),
            }
            conflict.resolved_at = time.time()
            self._record_episode(beliefs, domain, success=True, trace_id=trace_id)
            self.observability.end_span(span.span_id, "OK")
            result = ConflictResolutionResult(
                conflict=conflict,
                level_reached=ResolutionLevel.CNP_BIDDING,
                negotiation_result=neg_result,
                voting_result=vote_result,
                cnp_result=cnp_result,
                success=True,
                total_duration=time.time() - start_time,
            )
            self._resolution_history.append(result)
            return result

        # ─── Nivel 4: Escalación ──────────────────────────────────────
        conflict.resolution_status = ResolutionStatus.ESCALATED
        esc_span = self.observability.start_span(
            operation="escalation",
            agent_id="UC-322",
            trace_id=trace_id,
            parent_span_id=span.span_id,
        )
        esc_result = self.escalation.escalate(
            conflict, neg_result, vote_result, cnp_result
        )
        self.observability.end_span(
            esc_span.span_id,
            "OK" if esc_result.verdict != EscalationVerdict.STOP else "ERROR",
        )

        self.observability.inc_counter(
            "conflict_escalation_total",
            labels={"verdict": esc_result.verdict.value},
        )

        if esc_result.verdict in (EscalationVerdict.PROCEED, EscalationVerdict.REASSIGN):
            conflict.resolution_status = ResolutionStatus.RESOLVED
            conflict.resolution_level = ResolutionLevel.ESCALATION
            conflict.resolution_detail = {
                "negotiation": neg_result.to_dict(),
                "voting": vote_result.to_dict(),
                "cnp": cnp_result.to_dict(),
                "escalation": esc_result.to_dict(),
            }
            conflict.resolved_at = time.time()
            self._record_episode(beliefs, domain, success=True, trace_id=trace_id)
            self.observability.end_span(span.span_id, "OK")
            success = True
        else:
            conflict.resolution_status = (
                ResolutionStatus.DEADLOCKED
                if esc_result.verdict == EscalationVerdict.STOP
                else ResolutionStatus.ABORTED
            )
            conflict.resolution_level = ResolutionLevel.ESCALATION
            conflict.resolution_detail = {
                "negotiation": neg_result.to_dict(),
                "voting": vote_result.to_dict(),
                "cnp": cnp_result.to_dict(),
                "escalation": esc_result.to_dict(),
            }
            conflict.resolved_at = time.time()
            self._record_episode(beliefs, domain, success=False, trace_id=trace_id)
            self.observability.end_span(span.span_id, "ERROR")
            success = False

        result = ConflictResolutionResult(
            conflict=conflict,
            level_reached=ResolutionLevel.ESCALATION,
            negotiation_result=neg_result,
            voting_result=vote_result,
            cnp_result=cnp_result,
            escalation_result=esc_result,
            success=success,
            total_duration=time.time() - start_time,
        )
        self._resolution_history.append(result)
        return result

    def _record_episode(
        self,
        beliefs: List[AgentBelief],
        domain: str,
        success: bool,
        trace_id: str,
    ) -> None:
        """Registra el episodio en el sistema de reputación."""
        for belief in beliefs:
            self.reputation.record_episode(
                agent_id=belief.agent_id,
                task_id=trace_id,
                success=success,
                quality=belief.confidence,
                efficiency=0.7,  # Default; en producción se mide real
                domain=domain,
            )

    def check_duplicate(
        self,
        task_id: str,
        agent_id: str,
        domain: str,
        description: str,
    ) -> Dict[str, Any]:
        """Verifica si una tarea es duplicado de una activa."""
        registered, conflict = self.duplicate_detection.register_task(
            task_id, agent_id, domain, description
        )
        return {
            "registered": registered,
            "conflict": conflict.to_dict() if conflict else None,
        }

    def check_deadlock(self) -> Dict[str, Any]:
        """Verifica si hay deadlocks en el grafo de espera."""
        deadlock = self.deadlock_detector.detect_cycle()
        return {
            "deadlock_detected": deadlock is not None,
            "deadlock": deadlock.to_dict() if deadlock else None,
            "waiting_graph": self.deadlock_detector.get_waiting_graph(),
        }

    def get_reputation_ranking(self, domain: str = "trading") -> List[Dict[str, Any]]:
        """Retorna el ranking de reputación de agentes."""
        return self.reputation.get_ranking(domain)

    def get_resolution_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna el historial de resoluciones."""
        return [r.to_dict() for r in self._resolution_history[-limit:]]

    def get_observability_summary(self) -> Dict[str, Any]:
        """Retorna un resumen de métricas, logs y trazas."""
        return {
            "counters": self.observability.get_counters(),
            "histograms": self.observability.get_histograms(),
            "gauges": self.observability.get_gauges(),
            "total_logs": len(self.observability.get_logs()),
            "total_spans": len(self.observability.get_spans()),
            "circuit_breaker_open": self.escalation.circuit_breaker_open,
            "consecutive_conflicts": self.escalation.consecutive_conflicts,
        }

    def reset(self) -> None:
        """Reinicia toda la capa de resolución."""
        self.reputation.reset()
        self.escalation = EscalationProtocol()
        self.duplicate_detection = DuplicateDetection()
        self.deadlock_detector = DeadlockDetector()
        self.observability.reset()
        self._resolution_history.clear()


# ─── CLI ─────────────────────────────────────────────────────────────────

def demo() -> None:
    """Demostración del sistema de resolución de conflictos."""
    print("=" * 70)
    print("UC-322 — Demo de Resolución de Conflictos Multiagente")
    print("=" * 70)

    layer = ConflictResolutionLayer()

    # Registrar agentes con reputación inicial
    for agent in ["technical", "sentiment", "fundamental", "risk"]:
        layer.reputation.record_episode(
            agent_id=agent, task_id="init", success=True,
            quality=0.7, efficiency=0.8, domain="trading",
        )

    # Simular conflicto: 4 agentes discrepan sobre una predicción
    beliefs = [
        AgentBelief(agent_id="technical", proposition="BUY AAPL", confidence=0.85),
        AgentBelief(agent_id="sentiment", proposition="BUY AAPL", confidence=0.40),
        AgentBelief(agent_id="fundamental", proposition="BUY AAPL", confidence=0.60),
        AgentBelief(agent_id="risk", proposition="BUY AAPL", confidence=0.30),
    ]

    print(f"\nAgentes en conflicto: {[b.agent_id for b in beliefs]}")
    print(f"Confianzas: {[b.confidence for b in beliefs]}")

    result = layer.resolve(
        beliefs=beliefs,
        domain="trading",
        options=["BUY", "SELL", "HOLD"],
    )

    print(f"\n--- Resultado ---")
    print(f"Nivel alcanzado: {result.level_reached.name}")
    print(f"Éxito: {result.success}")
    print(f"Duración: {result.total_duration:.4f}s")

    if result.negotiation_result:
        print(f"\nNegociación: acuerdo={result.negotiation_result.agreement_reached}")
        print(f"  Concesiones: {len(result.negotiation_result.concessions)}")
        print(f"  Gap final: {result.negotiation_result.remaining_gap:.4f}")

    if result.voting_result:
        print(f"\nVotación: ganador={result.voting_result.winner}")
        print(f"  Score: {result.voting_result.winner_score:.4f}")
        print(f"  Consenso: {result.voting_result.consensus_reached}")

    if result.cnp_result:
        print(f"\nCNP: ganador={result.cnp_result.winner}")
        print(f"  Score: {result.cnp_result.winner_score:.4f}")

    if result.escalation_result:
        print(f"\nEscalación: veredicto={result.escalation_result.verdict.value}")
        print(f"  Razón: {result.escalation_result.reasoning}")
        print(f"  Requiere humano: {result.escalation_result.requires_human_review}")

    # Ranking de reputación
    print(f"\n--- Ranking de Reputación ---")
    for entry in layer.get_reputation_ranking("trading"):
        print(f"  {entry['agent_id']}: rep={entry['reputation']:.4f} "
              f"success_rate={entry['success_rate']:.2f} episodes={entry['total_episodes']}")

    # Observabilidad
    print(f"\n--- Observabilidad ---")
    summary = layer.get_observability_summary()
    print(f"  Contadores: {summary['counters']}")
    print(f"  Logs: {summary['total_logs']}")
    print(f"  Spans: {summary['total_spans']}")
    print(f"  Circuit breaker: {summary['circuit_breaker_open']}")


if __name__ == "__main__":
    demo()
