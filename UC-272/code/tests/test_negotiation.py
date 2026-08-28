"""Tests de los protocolos de negociación."""
from __future__ import annotations

from uuid import uuid4

from config import NegotiationConfig
from models import (
    Argument,
    ContractAnnouncement,
    ContractBid,
    NegotiationStatus,
    VickreyBid,
)
from negotiation import (
    AlternatingOffersEngine,
    ArgumentationEngine,
    ContractNetEngine,
    VickreyAuctionEngine,
)


# ============================================================
# Alternating Offers
# ============================================================

def test_alternating_offers_agreement() -> None:
    config = NegotiationConfig(max_rounds=10, discount_factor=0.95, concession_exponent=2.0)
    engine = AlternatingOffersEngine(config)
    feasible = [{"price": 500}, {"price": 550}, {"price": 600}]
    neg_id = uuid4()

    result = engine.negotiate(
        neg_id, "seller", "buyer",
        proposer_utility_fn=lambda t: t["price"] / 100,
        responder_utility_fn=lambda t: (700 - t["price"]) / 100,
        feasible_set=feasible,
        proposer_reservation=3.0,
        responder_reservation=1.0,
    )
    assert result.status == NegotiationStatus.agreed
    assert result.final_terms is not None


def test_alternating_offers_deadlock() -> None:
    config = NegotiationConfig(max_rounds=3, concession_exponent=2.0)
    engine = AlternatingOffersEngine(config)
    feasible = [{"price": 100}]
    neg_id = uuid4()

    # Both agents get 0 utility from any option, but need 10 — impossible agreement
    result = engine.negotiate(
        neg_id, "a", "b",
        proposer_utility_fn=lambda t: 0.0,
        responder_utility_fn=lambda t: 0.0,
        feasible_set=feasible,
        proposer_reservation=10.0,
        responder_reservation=10.0,
    )
    assert result.status == NegotiationStatus.deadlock


# ============================================================
# Contract Net
# ============================================================

def test_contract_net_adjudicates_best_bid() -> None:
    engine = ContractNetEngine()
    cid = uuid4()
    announcement = ContractAnnouncement(
        contract_id=cid, announcer="planner", task_description="Book flight",
        evaluation_criteria={"cost": 0.5, "confidence": 0.3, "duration": 0.2},
    )
    bids = [
        ContractBid(contract_id=cid, bidder="supplier_a", cost=500.0, estimated_duration_min=30, confidence=0.9),
        ContractBid(contract_id=cid, bidder="supplier_b", cost=800.0, estimated_duration_min=60, confidence=0.7),
    ]
    result = engine.announce_and_adjudicate(announcement, bids)
    assert result.status == NegotiationStatus.agreed
    assert result.winner == "supplier_a"


def test_contract_net_no_bids() -> None:
    engine = ContractNetEngine()
    announcement = ContractAnnouncement(
        announcer="planner", task_description="Empty task",
        evaluation_criteria={"cost": 1.0},
    )
    result = engine.announce_and_adjudicate(announcement, [])
    assert result.status == NegotiationStatus.deadlock


# ============================================================
# Vickrey Auction
# ============================================================

def test_vickrey_winner_pays_second_price() -> None:
    engine = VickreyAuctionEngine(reserve_price=0.0)
    aid = uuid4()
    bids = [
        VickreyBid(auction_id=aid, bidder="a", bid_value=100.0, resource_id="GPU"),
        VickreyBid(auction_id=aid, bidder="b", bid_value=80.0, resource_id="GPU"),
        VickreyBid(auction_id=aid, bidder="c", bid_value=60.0, resource_id="GPU"),
    ]
    result = engine.run_auction(aid, "GPU", bids)
    assert result.winner == "a"
    assert result.winning_bid == 100.0
    assert result.price_paid == 80.0


def test_vickrey_single_bidder_pays_reserve() -> None:
    engine = VickreyAuctionEngine(reserve_price=10.0)
    aid = uuid4()
    bids = [VickreyBid(auction_id=aid, bidder="x", bid_value=50.0, resource_id="MEM")]
    result = engine.run_auction(aid, "MEM", bids)
    assert result.winner == "x"
    assert result.price_paid == 10.0


def test_vickrey_no_valid_bids() -> None:
    engine = VickreyAuctionEngine(reserve_price=200.0)
    aid = uuid4()
    bids = [VickreyBid(auction_id=aid, bidder="a", bid_value=50.0, resource_id="R")]
    result = engine.run_auction(aid, "R", bids)
    assert result.winner is None


# ============================================================
# Argumentation
# ============================================================

def test_argumentation_winner_by_strength() -> None:
    engine = ArgumentationEngine()
    args = [
        Argument(agent_name="budget", claim="Too expensive", justification="Market avg is $500", strength=0.8),
        Argument(agent_name="user", claim="Quality matters", justification="Premium service", strength=0.6),
    ]
    result = engine.debate("price_debate", args)
    assert result.winner_agent == "budget"


def test_argumentation_attacks_reduce_strength() -> None:
    engine = ArgumentationEngine()
    a1 = Argument(agent_name="a", claim="C1", justification="J1", strength=0.7)
    a2 = Argument(agent_name="b", claim="C2", justification="J2", strength=0.9, attacks=[a1.arg_id])
    result = engine.debate("debate", [a1, a2])
    # a1 is attacked, so net strength < 0.7, b should win
    assert result.winner_agent == "b"
