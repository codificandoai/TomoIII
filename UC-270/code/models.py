"""Modelos Pydantic para resolución de conflictos entre agentes (UC-270).

Integra patrones de:
- OVADARE: detección, clasificación y resolución de conflictos.
- NegMAS: negociación bilateral/multilateral con rondas y concesiones.
- AutoGen: Propose-Validate-Commit atómico con priorización y auditoría.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enums de conflicto
# ============================================================

class ConflictType(str, Enum):
    """Tipos de conflicto (inspirado en OVADARE)."""
    resource_contention = "resource_contention"
    incompatible_actions = "incompatible_actions"
    inconsistent_state = "inconsistent_state"
    duplicate_ownership = "duplicate_ownership"
    policy_violation = "policy_violation"


class ConflictSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ResolutionStrategy(str, Enum):
    prioritization = "prioritization"
    negotiation = "negotiation"
    escalation = "escalation"
    propose_validate_commit = "propose_validate_commit"
    deadlock = "deadlock"


class ResolutionStatus(str, Enum):
    agreement = "agreement"
    yielded = "yield"
    escalated = "escalate"
    committed = "committed"
    rejected = "rejected"
    deadlock = "deadlock"


class ProposalStatus(str, Enum):
    """Estado del ciclo Propose-Validate-Commit."""
    proposed = "proposed"
    validated = "validated"
    committed = "committed"
    rejected = "rejected"


# ============================================================
# Agentes y recursos
# ============================================================

class AgentProfile(BaseModel):
    """Perfil de un agente participante."""
    name: str
    priority: int = Field(ge=0, le=10)
    flexibility: float = Field(ge=0.0, le=1.0)
    negotiation_skill: float = Field(ge=0.0, le=1.0)
    reputation: float = Field(ge=0.0, le=1.0, default=0.8)
    roles: List[str] = Field(default_factory=list)


class ResourceClaim(BaseModel):
    """Reclamación de un agente sobre un recurso."""
    claim_id: UUID = Field(default_factory=uuid4)
    agent_name: str
    resource_id: str
    need: float = Field(ge=0.0, le=1.0)
    priority: int = Field(ge=0, le=10)
    flexibility: float = Field(ge=0.0, le=1.0)
    willingness: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Detección de conflictos (OVADARE)
# ============================================================

class DetectedConflict(BaseModel):
    """Conflicto detectado y clasificado."""
    conflict_id: UUID = Field(default_factory=uuid4)
    conflict_type: ConflictType
    severity: ConflictSeverity
    resource_id: str
    claimants: List[str]
    claims: List[ResourceClaim]
    description: str = ""
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Negociación (NegMAS)
# ============================================================

class NegotiationOffer(BaseModel):
    """Oferta en una ronda de negociación."""
    round_number: int
    agent_name: str
    offered_share: float = Field(ge=0.0, le=1.0)
    concession: float = Field(ge=0.0, le=1.0, default=0.0)
    accepted: bool = False


class NegotiationRound(BaseModel):
    """Ronda de negociación bilateral."""
    round_number: int
    offers: List[NegotiationOffer]
    agreement_reached: bool = False
    agreement_share: Optional[Dict[str, float]] = None


class NegotiationResult(BaseModel):
    """Resultado de un proceso de negociación."""
    conflict_id: UUID
    rounds: List[NegotiationRound]
    total_rounds: int
    agreement_reached: bool
    final_allocation: Optional[Dict[str, float]] = None
    strategy_used: ResolutionStrategy = ResolutionStrategy.negotiation


# ============================================================
# Propose-Validate-Commit (AutoGen)
# ============================================================

class StateProposal(BaseModel):
    """Propuesta de escritura al estado compartido."""
    proposal_id: UUID = Field(default_factory=uuid4)
    agent_name: str
    resource_id: str
    proposed_value: Any
    priority_level: int = Field(ge=0, le=3, description="0=highest, 3=lowest")
    status: ProposalStatus = ProposalStatus.proposed
    signature: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CommitRecord(BaseModel):
    """Registro de un commit atómico al estado compartido."""
    commit_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    agent_name: str
    resource_id: str
    committed_value: Any
    previous_value: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Auditoría y resultado
# ============================================================

class AuditEntry(BaseModel):
    """Entrada de auditoría con firma."""
    entry_id: UUID = Field(default_factory=uuid4)
    action: str
    agent_name: str
    resource_id: str
    detail: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    signature: Optional[str] = None


class ConflictResolutionOutcome(BaseModel):
    """Resultado completo de la resolución de un conflicto."""
    conflict_id: UUID
    conflict_type: ConflictType
    severity: ConflictSeverity
    resource_id: str
    claimants: List[str]
    strategy: ResolutionStrategy
    status: ResolutionStatus
    winner: Optional[str] = None
    allocation: Optional[Dict[str, float]] = None
    negotiation: Optional[NegotiationResult] = None
    commits: List[CommitRecord] = Field(default_factory=list)
    audit_trail: List[AuditEntry] = Field(default_factory=list)
    rationale: str = ""
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    metrics: Dict[str, Any] = Field(default_factory=dict)
