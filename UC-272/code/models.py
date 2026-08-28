"""Modelos Pydantic para UC-272 — Negociación y Compartición de Conocimiento.

Cubre:
- Blackboard: pizarra versionada con confianza.
- Gossip: difusión epidémica de conocimiento.
- Negociación: Alternating Offers, Contract Net, Vickrey Auction, Argumentation.
- Equilibrio: Nash Bargaining, Pareto, Kalai-Smorodinsky, Weighted Utilitarian.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class KnowledgeCategory(str, Enum):
    flight_facts = "flight_facts"
    price_intel = "price_intel"
    risk_assessment = "risk_assessment"
    user_preferences = "user_preferences"
    supplier_constraints = "supplier_constraints"
    negotiation_state = "negotiation_state"
    model_exchange = "model_exchange"


class NegotiationProtocol(str, Enum):
    alternating_offers = "alternating_offers"
    contract_net = "contract_net"
    nash_bargaining = "nash_bargaining"
    vickrey_auction = "vickrey_auction"
    argumentation = "argumentation"


class NegotiationStatus(str, Enum):
    agreed = "agreed"
    rejected = "rejected"
    timeout = "timeout"
    deadlock = "deadlock"
    escalated = "escalated"


class ConflictSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EquilibriumCriterion(str, Enum):
    nash = "nash"
    pareto = "pareto"
    kalai_smorodinsky = "kalai_smorodinsky"
    weighted_utilitarian = "weighted_utilitarian"


# ============================================================
# Blackboard
# ============================================================

class BlackboardEntry(BaseModel):
    """Entrada atómica en la pizarra compartida."""
    entry_id: UUID = Field(default_factory=uuid4)
    key: str
    category: KnowledgeCategory
    value: Any
    author: str
    confidence: float = Field(ge=0.0, le=1.0)
    version: int = 1
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: int = 3600


# ============================================================
# Gossip
# ============================================================

class KnowledgeFragment(BaseModel):
    """Fragmento de conocimiento difundido vía gossip."""
    fragment_id: UUID = Field(default_factory=uuid4)
    source_agent: str
    topic: str
    content: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    hop_count: int = 0
    max_hops: int = 3
    seen_by: List[str] = Field(default_factory=list)


# ============================================================
# Negotiation
# ============================================================

class NegotiationOffer(BaseModel):
    """Oferta en negociación por Alternating Offers."""
    offer_id: UUID = Field(default_factory=uuid4)
    negotiation_id: UUID
    round_number: int
    proposer: str
    responder: str = ""
    terms: Dict[str, Any]
    proposer_utility: float = 0.0
    concessions_made: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NegotiationOutcome(BaseModel):
    """Resultado de una negociación."""
    negotiation_id: UUID
    protocol: NegotiationProtocol
    status: NegotiationStatus
    final_terms: Optional[Dict[str, Any]] = None
    winner: Optional[str] = None
    rounds_played: int = 0
    utilities: Dict[str, float] = Field(default_factory=dict)
    nash_product: Optional[float] = None
    rationale: str = ""


# ============================================================
# Contract Net
# ============================================================

class ContractAnnouncement(BaseModel):
    """Anuncio de contrato para licitación."""
    contract_id: UUID = Field(default_factory=uuid4)
    announcer: str
    task_description: str
    requirements: Dict[str, Any] = Field(default_factory=dict)
    evaluation_criteria: Dict[str, float] = Field(default_factory=dict)
    deadline_seconds: int = 60


class ContractBid(BaseModel):
    """Puja de un agente a un contrato."""
    bid_id: UUID = Field(default_factory=uuid4)
    contract_id: UUID
    bidder: str
    proposed_terms: Dict[str, Any] = Field(default_factory=dict)
    cost: float = 0.0
    estimated_duration_min: int = 0
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Vickrey Auction
# ============================================================

class VickreyBid(BaseModel):
    """Puja sellada para subasta Vickrey (segundo precio)."""
    bid_id: UUID = Field(default_factory=uuid4)
    auction_id: UUID
    bidder: str
    bid_value: float
    resource_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuctionResult(BaseModel):
    """Resultado de una subasta Vickrey."""
    auction_id: UUID
    resource_id: str
    winner: Optional[str] = None
    winning_bid: float = 0.0
    price_paid: float = 0.0
    all_bids: List[VickreyBid] = Field(default_factory=list)
    rationale: str = ""


# ============================================================
# Argumentation
# ============================================================

class Argument(BaseModel):
    """Argumento en negociación por argumentación."""
    arg_id: UUID = Field(default_factory=uuid4)
    agent_name: str
    claim: str
    justification: str
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    strength: float = Field(ge=0.0, le=1.0)
    attacks: List[UUID] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ArgumentationOutcome(BaseModel):
    """Resultado de debate por argumentación."""
    debate_id: UUID = Field(default_factory=uuid4)
    topic: str
    arguments: List[Argument]
    winning_argument: Optional[UUID] = None
    winner_agent: Optional[str] = None
    rationale: str = ""


# ============================================================
# Nash / Equilibrium
# ============================================================

class AgentUtilityProfile(BaseModel):
    """Perfil de utilidad de un agente sobre opciones."""
    agent_id: str
    option_utilities: Dict[str, float]
    disagreement_point: float = 0.0
    weight: float = 1.0


class EquilibriumResult(BaseModel):
    """Resultado de un cálculo de equilibrio."""
    criterion: EquilibriumCriterion
    best_option: Optional[str] = None
    utilities: Dict[str, float] = Field(default_factory=dict)
    nash_product: Optional[float] = None
    pareto_frontier: List[Dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""


# ============================================================
# Orchestrator outcome
# ============================================================

class OrchestrationOutcome(BaseModel):
    """Resultado completo de la orquestación de negociación."""
    orchestration_id: UUID = Field(default_factory=uuid4)
    topic: str
    participants: List[str]
    conflict_severity: ConflictSeverity
    protocol_selected: NegotiationProtocol
    negotiation: NegotiationOutcome
    equilibrium: Optional[EquilibriumResult] = None
    blackboard_entries: int = 0
    gossip_fragments: int = 0
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
