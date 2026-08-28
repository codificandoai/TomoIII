"""Orquestador de negociación para UC-272.

Pipeline completo:
1. Detectar conflicto (objetivos en tensión).
2. Publicar objetivo en pizarra.
3. Difundir contexto por gossip.
4. Seleccionar protocolo según severidad.
5. Ejecutar negociación.
6. Evaluar equilibrio (Nash/Pareto/KS/Utilitarian).
7. Publicar acuerdo en pizarra.
8. Aprendizaje: actualizar utilidades.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from blackboard import SharedBlackboard
from config import AppConfig, get_config
from gossip import GossipProtocol
from models import (
    AgentUtilityProfile,
    BlackboardEntry,
    ConflictSeverity,
    ContractAnnouncement,
    ContractBid,
    EquilibriumCriterion,
    KnowledgeCategory,
    NegotiationOutcome,
    NegotiationProtocol,
    NegotiationStatus,
    OrchestrationOutcome,
    VickreyBid,
)
from nash_solver import NashBargainingSolver
from negotiation import (
    AlternatingOffersEngine,
    ArgumentationEngine,
    ContractNetEngine,
    VickreyAuctionEngine,
)


class NegotiationOrchestrator:
    """Orquesta negociaciones entre agentes: pizarra + gossip + protocolos + equilibrio."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or get_config()
        self.blackboard = SharedBlackboard(self.config.blackboard)
        self.alt_offers = AlternatingOffersEngine(self.config.negotiation)
        self.contract_net = ContractNetEngine()
        self.argumentation = ArgumentationEngine()
        self._outcomes: Dict[UUID, OrchestrationOutcome] = {}

    def resolve_with_nash(
        self,
        topic: str,
        profiles: List[AgentUtilityProfile],
        criterion: EquilibriumCriterion = EquilibriumCriterion.nash,
    ) -> OrchestrationOutcome:
        """Resuelve negociación usando equilibrio cooperativo."""
        audit: List[Dict[str, Any]] = []
        severity = self._assess_severity(profiles)
        self._audit(audit, "detect_conflict", topic, f"severity={severity.value}")

        solver = NashBargainingSolver(profiles)

        if criterion == EquilibriumCriterion.nash:
            best_opt, utils, product = solver.solve()
            rationale = f"Nash: option={best_opt}, product={product:.4f}"
        elif criterion == EquilibriumCriterion.kalai_smorodinsky:
            best_opt, utils = solver.kalai_smorodinsky()
            product = None
            rationale = f"Kalai-Smorodinsky: option={best_opt}"
        elif criterion == EquilibriumCriterion.weighted_utilitarian:
            best_opt, utils, weighted_sum = solver.weighted_utilitarian()
            product = None
            rationale = f"Weighted Utilitarian: option={best_opt}, sum={weighted_sum:.4f}"
        else:
            best_opt, utils, product = solver.solve()
            rationale = f"Nash (default): option={best_opt}"

        status = NegotiationStatus.agreed if best_opt else NegotiationStatus.deadlock

        # Publicar en pizarra
        self._publish_agreement(topic, best_opt, utils, audit)

        equilibrium = solver.solve_all()
        neg_outcome = NegotiationOutcome(
            negotiation_id=uuid4(),
            protocol=NegotiationProtocol.nash_bargaining,
            status=status,
            final_terms={"option": best_opt} if best_opt else None,
            winner=best_opt,
            utilities=utils,
            nash_product=product,
            rationale=rationale,
        )

        outcome = OrchestrationOutcome(
            topic=topic,
            participants=[p.agent_id for p in profiles],
            conflict_severity=severity,
            protocol_selected=NegotiationProtocol.nash_bargaining,
            negotiation=neg_outcome,
            equilibrium=equilibrium,
            blackboard_entries=self.blackboard.entry_count,
            audit_trail=audit,
        )
        self._outcomes[outcome.orchestration_id] = outcome
        return outcome

    def resolve_with_contract_net(
        self,
        topic: str,
        announcement: ContractAnnouncement,
        bids: List[ContractBid],
    ) -> OrchestrationOutcome:
        """Resuelve con Contract Net Protocol."""
        audit: List[Dict[str, Any]] = []
        self._audit(audit, "contract_net_start", topic, f"bids={len(bids)}")

        neg_outcome = self.contract_net.announce_and_adjudicate(announcement, bids)
        self._publish_agreement(topic, neg_outcome.winner, neg_outcome.utilities, audit)

        outcome = OrchestrationOutcome(
            topic=topic,
            participants=[b.bidder for b in bids],
            conflict_severity=ConflictSeverity.medium,
            protocol_selected=NegotiationProtocol.contract_net,
            negotiation=neg_outcome,
            blackboard_entries=self.blackboard.entry_count,
            audit_trail=audit,
        )
        self._outcomes[outcome.orchestration_id] = outcome
        return outcome

    def resolve_with_vickrey(
        self,
        topic: str,
        resource_id: str,
        bids: List[VickreyBid],
        reserve_price: float = 0.0,
    ) -> OrchestrationOutcome:
        """Resuelve con subasta Vickrey."""
        audit: List[Dict[str, Any]] = []
        self._audit(audit, "vickrey_start", topic, f"bids={len(bids)}, reserve={reserve_price}")

        engine = VickreyAuctionEngine(reserve_price)
        auction_id = bids[0].auction_id if bids else uuid4()
        result = engine.run_auction(auction_id, resource_id, bids)

        status = NegotiationStatus.agreed if result.winner else NegotiationStatus.deadlock
        neg_outcome = NegotiationOutcome(
            negotiation_id=auction_id,
            protocol=NegotiationProtocol.vickrey_auction,
            status=status,
            final_terms={"resource": resource_id, "price_paid": result.price_paid} if result.winner else None,
            winner=result.winner,
            utilities={result.winner: result.winning_bid} if result.winner else {},
            rationale=result.rationale,
        )
        self._publish_agreement(topic, result.winner, neg_outcome.utilities, audit)

        outcome = OrchestrationOutcome(
            topic=topic,
            participants=[b.bidder for b in bids],
            conflict_severity=ConflictSeverity.low,
            protocol_selected=NegotiationProtocol.vickrey_auction,
            negotiation=neg_outcome,
            blackboard_entries=self.blackboard.entry_count,
            audit_trail=audit,
        )
        self._outcomes[outcome.orchestration_id] = outcome
        return outcome

    def resolve_with_alternating_offers(
        self,
        topic: str,
        proposer: str,
        responder: str,
        proposer_utility_fn: Callable,
        responder_utility_fn: Callable,
        feasible_set: List[Dict[str, Any]],
        proposer_reservation: float = 0.0,
        responder_reservation: float = 0.0,
    ) -> OrchestrationOutcome:
        """Resuelve con Alternating Offers."""
        audit: List[Dict[str, Any]] = []
        self._audit(audit, "alt_offers_start", topic, f"proposer={proposer}, responder={responder}")

        neg_id = uuid4()
        neg_outcome = self.alt_offers.negotiate(
            neg_id, proposer, responder,
            proposer_utility_fn, responder_utility_fn,
            feasible_set, proposer_reservation, responder_reservation,
        )
        self._publish_agreement(topic, neg_outcome.winner, neg_outcome.utilities, audit)

        outcome = OrchestrationOutcome(
            topic=topic,
            participants=[proposer, responder],
            conflict_severity=ConflictSeverity.medium,
            protocol_selected=NegotiationProtocol.alternating_offers,
            negotiation=neg_outcome,
            blackboard_entries=self.blackboard.entry_count,
            audit_trail=audit,
        )
        self._outcomes[outcome.orchestration_id] = outcome
        return outcome

    def get_outcome(self, orch_id: UUID) -> Optional[OrchestrationOutcome]:
        return self._outcomes.get(orch_id)

    def _assess_severity(self, profiles: List[AgentUtilityProfile]) -> ConflictSeverity:
        """Evalúa severidad según dispersión de utilidades."""
        if len(profiles) < 2:
            return ConflictSeverity.low
        all_opts = set()
        for p in profiles:
            all_opts.update(p.option_utilities.keys())
        if not all_opts:
            return ConflictSeverity.low
        # Contar cuántas opciones tienen conflicto (best option difiere por agente)
        best_by_agent = {p.agent_id: max(p.option_utilities, key=lambda o: p.option_utilities[o]) for p in profiles if p.option_utilities}
        unique_bests = len(set(best_by_agent.values()))
        if unique_bests >= len(profiles):
            return ConflictSeverity.high
        if unique_bests > 1:
            return ConflictSeverity.medium
        return ConflictSeverity.low

    def _publish_agreement(self, topic: str, winner: Any, utilities: Dict, audit: List) -> None:
        entry = BlackboardEntry(
            key=f"agreement:{topic}",
            category=KnowledgeCategory.negotiation_state,
            value={"winner": str(winner) if winner else None, "utilities": utilities},
            author="orchestrator",
            confidence=1.0,
        )
        self.blackboard.write(entry)
        self._audit(audit, "agreement_published", topic, f"winner={winner}")

    def _audit(self, trail: List[Dict], action: str, topic: str, detail: str) -> None:
        sig = hashlib.sha256(f"{action}:{topic}:{detail}".encode()).hexdigest()[:16]
        trail.append({"action": action, "topic": topic, "detail": detail, "signature": sig})
