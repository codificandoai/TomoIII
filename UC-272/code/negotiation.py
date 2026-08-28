"""Protocolos de negociación para UC-272.

Implementa:
- Alternating Offers (Rubinstein): propuestas alternadas con concesión temporal.
- Contract Net: licitación con evaluación multi-criterio.
- Vickrey Auction: subasta sellada de segundo precio.
- Argumentation: negociación con justificaciones y ataque/defensa.

Inspirado en: yasserfarouk/negmas, SafeRL-Lab/AgenticPay.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from config import NegotiationConfig, get_config
from models import (
    Argument,
    ArgumentationOutcome,
    AuctionResult,
    ContractAnnouncement,
    ContractBid,
    NegotiationOffer,
    NegotiationOutcome,
    NegotiationProtocol,
    NegotiationStatus,
    VickreyBid,
)


# ============================================================
# Alternating Offers (Rubinstein)
# ============================================================

class AlternatingOffersEngine:
    """Negociación bilateral con ofertas alternadas y concesión temporal."""

    def __init__(self, config: NegotiationConfig | None = None) -> None:
        self.config = config or get_config().negotiation

    def negotiate(
        self,
        negotiation_id: UUID,
        proposer: str,
        responder: str,
        proposer_utility_fn: Callable[[Dict[str, Any]], float],
        responder_utility_fn: Callable[[Dict[str, Any]], float],
        feasible_set: List[Dict[str, Any]],
        proposer_reservation: float = 0.0,
        responder_reservation: float = 0.0,
    ) -> NegotiationOutcome:
        """Ejecuta negociación por ofertas alternadas."""
        offers: List[NegotiationOffer] = []
        current_proposer = proposer
        current_responder = responder
        current_p_fn = proposer_utility_fn
        current_r_fn = responder_utility_fn
        current_p_res = proposer_reservation
        current_r_res = responder_reservation

        for round_num in range(1, self.config.max_rounds + 1):
            # Concesión temporal cuadrática
            t = round_num / self.config.max_rounds
            concession = t ** self.config.concession_exponent

            # Proposer elige la mejor opción ajustada por concesión
            scored = []
            for terms in feasible_set:
                u = current_p_fn(terms)
                adjusted = u * (1 - concession) + current_p_res * concession
                scored.append((adjusted, terms, u))

            if not scored:
                break

            best_adj, best_terms, best_raw = max(scored, key=lambda x: x[0])

            offer = NegotiationOffer(
                negotiation_id=negotiation_id,
                round_number=round_num,
                proposer=current_proposer,
                responder=current_responder,
                terms=best_terms,
                proposer_utility=best_raw,
                concessions_made=round_num - 1,
            )
            offers.append(offer)

            # Responder evalúa
            responder_u = current_r_fn(best_terms)
            if responder_u >= current_r_res:
                return NegotiationOutcome(
                    negotiation_id=negotiation_id,
                    protocol=NegotiationProtocol.alternating_offers,
                    status=NegotiationStatus.agreed,
                    final_terms=best_terms,
                    winner=current_proposer,
                    rounds_played=round_num,
                    utilities={current_proposer: best_raw, current_responder: responder_u},
                    nash_product=max(0, (best_raw - proposer_reservation) * (responder_u - responder_reservation)),
                    rationale=f"Agreement at round {round_num}",
                )

            # Swap roles
            current_proposer, current_responder = current_responder, current_proposer
            current_p_fn, current_r_fn = current_r_fn, current_p_fn
            current_p_res, current_r_res = current_r_res, current_p_res

        return NegotiationOutcome(
            negotiation_id=negotiation_id,
            protocol=NegotiationProtocol.alternating_offers,
            status=NegotiationStatus.deadlock,
            rounds_played=self.config.max_rounds,
            utilities={proposer: 0.0, responder: 0.0},
            rationale=f"Deadlock after {self.config.max_rounds} rounds",
        )


# ============================================================
# Contract Net Protocol
# ============================================================

class ContractNetEngine:
    """Protocolo Contract Net: announce → bid → adjudicate."""

    def announce_and_adjudicate(
        self,
        announcement: ContractAnnouncement,
        bids: List[ContractBid],
    ) -> NegotiationOutcome:
        """Evalúa bids y adjudica."""
        if not bids:
            return NegotiationOutcome(
                negotiation_id=announcement.contract_id,
                protocol=NegotiationProtocol.contract_net,
                status=NegotiationStatus.deadlock,
                rounds_played=0,
                rationale="No bids received",
            )

        scored = [(self._score_bid(b, announcement.evaluation_criteria), b) for b in bids]
        scored.sort(key=lambda x: x[0], reverse=True)
        winner_score, winner_bid = scored[0]

        return NegotiationOutcome(
            negotiation_id=announcement.contract_id,
            protocol=NegotiationProtocol.contract_net,
            status=NegotiationStatus.agreed,
            final_terms=winner_bid.proposed_terms,
            winner=winner_bid.bidder,
            rounds_played=1,
            utilities={b.bidder: s for s, b in scored},
            rationale=f"Contract awarded to {winner_bid.bidder} (score={winner_score:.4f})",
        )

    def _score_bid(self, bid: ContractBid, criteria: Dict[str, float]) -> float:
        score = 0.0
        if "cost" in criteria:
            score += criteria["cost"] * (1.0 / (1.0 + bid.cost / 1000))
        if "duration" in criteria:
            score += criteria["duration"] * (1.0 / (1.0 + bid.estimated_duration_min / 60))
        if "confidence" in criteria:
            score += criteria["confidence"] * bid.confidence
        return score


# ============================================================
# Vickrey Auction (second-price sealed-bid)
# ============================================================

class VickreyAuctionEngine:
    """Subasta sellada de segundo precio (Vickrey)."""

    def __init__(self, reserve_price: float = 0.0) -> None:
        self.reserve_price = reserve_price

    def run_auction(self, auction_id: UUID, resource_id: str, bids: List[VickreyBid]) -> AuctionResult:
        """Ejecuta subasta: gana el mayor postor, paga el segundo precio."""
        valid = [b for b in bids if b.bid_value >= self.reserve_price]
        if not valid:
            return AuctionResult(
                auction_id=auction_id, resource_id=resource_id,
                rationale="No bids above reserve price",
                all_bids=bids,
            )

        sorted_bids = sorted(valid, key=lambda b: b.bid_value, reverse=True)
        winner = sorted_bids[0]
        second_price = sorted_bids[1].bid_value if len(sorted_bids) > 1 else self.reserve_price

        return AuctionResult(
            auction_id=auction_id,
            resource_id=resource_id,
            winner=winner.bidder,
            winning_bid=winner.bid_value,
            price_paid=second_price,
            all_bids=bids,
            rationale=f"Winner={winner.bidder}, bid={winner.bid_value:.2f}, pays={second_price:.2f} (2nd price)",
        )


# ============================================================
# Argumentation Protocol
# ============================================================

class ArgumentationEngine:
    """Negociación por argumentación: claim + justification + attacks."""

    def debate(self, topic: str, arguments: List[Argument]) -> ArgumentationOutcome:
        """Evalúa argumentos y determina ganador por fuerza neta."""
        if not arguments:
            return ArgumentationOutcome(
                topic=topic, arguments=[], rationale="No arguments submitted"
            )

        # Calcular fuerza neta: strength - penalización por ataques recibidos
        arg_by_id = {a.arg_id: a for a in arguments}
        net_strength: Dict[UUID, float] = {}

        for arg in arguments:
            attacks_received = sum(
                1 for other in arguments
                if arg.arg_id in other.attacks
            )
            net_strength[arg.arg_id] = arg.strength - attacks_received * 0.2

        best_id = max(net_strength, key=lambda k: net_strength[k])
        best_arg = arg_by_id[best_id]

        return ArgumentationOutcome(
            topic=topic,
            arguments=arguments,
            winning_argument=best_id,
            winner_agent=best_arg.agent_name,
            rationale=f"Winner: {best_arg.agent_name} (net_strength={net_strength[best_id]:.3f})",
        )
