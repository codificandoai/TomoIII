"""Modelos de datos para la capa de resolución de conflictos UC-322.

Define las estructuras base que utilizan los cuatro niveles de resolución:
negociación, votación, CNP dinámico y escalación.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ─── Enums ────────────────────────────────────────────────────────────────

class ConflictType(Enum):
    """Tipos de conflicto que pueden surgir entre agentes."""
    BELIEF_DISAGREEMENT = "belief_disagreement"      # Discrepan en creencias
    RESOURCE_CONTENTION = "resource_contention"       # Recursos compartidos
    TASK_OWNERSHIP = "task_ownership"                 # Propiedad de tarea
    PRIORITY_DISPUTE = "priority_dispute"             # Prioridad de ejecución
    DUPLICATE_WORK = "duplicate_work"                 # Trabajo duplicado
    DEADLOCK = "deadlock"                             # Bloqueo mutuo
    GOAL_CONFLICT = "goal_conflict"                   # Objetivos incompatibles
    DOMAIN_BOUNDARY = "domain_boundary"               # Conflicto entre dominios


class ConflictSeverity(Enum):
    """Severidad del conflicto."""
    LOW = 1       # Resolución automática nivel 1
    MEDIUM = 2    # Requiere nivel 2 o 3
    HIGH = 3      # Requiere escalación nivel 4
    CRITICAL = 4  # Detiene el sistema


class ResolutionLevel(Enum):
    """Niveles de resolución de conflictos."""
    NEGOTIATION = 1       # Nivel 1: negociación directa
    VOTING = 2            # Nivel 2: votación ponderada
    CNP_BIDDING = 3       # Nivel 3: CNP con pujas
    ESCALATION = 4        # Nivel 4: escalación al orquestador


class ResolutionStatus(Enum):
    """Estado de la resolución."""
    DETECTED = "detected"
    NEGOTIATING = "negotiating"
    VOTING = "voting"
    BIDDING = "bidding"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    DEADLOCKED = "deadlocked"
    ABORTED = "aborted"


class EscalationVerdict(Enum):
    """Veredicto del orquestador de nivel superior."""
    PROCEED = "proceed"
    REVIEW = "review"
    STOP = "stop"
    REASSIGN = "reassign"


# ─── Modelos de agentes ────────────────────────────────────────────────────

@dataclass
class AgentBelief:
    """Creencia que un agente sostiene sobre una proposición."""
    agent_id: str
    proposition: str
    confidence: float  # 0.0 - 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "proposition": self.proposition,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


@dataclass
class Concession:
    """Concesión que un agente hace durante la negociación."""
    agent_id: str
    original_position: float
    conceded_position: float
    reason: str
    timestamp: float = field(default_factory=time.time)

    @property
    def delta(self) -> float:
        return abs(self.original_position - self.conceded_position)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "original_position": self.original_position,
            "conceded_position": self.conceded_position,
            "reason": self.reason,
            "delta": self.delta,
            "timestamp": self.timestamp,
        }


# ─── Modelo de conflicto ───────────────────────────────────────────────────

@dataclass
class Conflict:
    """Conflicto detectado entre dos o más agentes."""
    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    conflict_type: ConflictType = ConflictType.BELIEF_DISAGREEMENT
    severity: ConflictSeverity = ConflictSeverity.LOW
    domain: str = "trading"
    agents_involved: List[str] = field(default_factory=list)
    beliefs: List[AgentBelief] = field(default_factory=list)
    description: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    detected_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolution_level: Optional[ResolutionLevel] = None
    resolution_status: ResolutionStatus = ResolutionStatus.DETECTED
    resolution_detail: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def is_resolved(self) -> bool:
        return self.resolution_status in (
            ResolutionStatus.RESOLVED,
            ResolutionStatus.ABORTED,
        )

    @property
    def duration(self) -> float:
        end = self.resolved_at or time.time()
        return end - self.detected_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.name,
            "domain": self.domain,
            "agents_involved": self.agents_involved,
            "beliefs": [b.to_dict() for b in self.beliefs],
            "description": self.description,
            "context": self.context,
            "detected_at": self.detected_at,
            "resolved_at": self.resolved_at,
            "resolution_level": self.resolution_level.name if self.resolution_level else None,
            "resolution_status": self.resolution_status.value,
            "resolution_detail": self.resolution_detail,
            "trace_id": self.trace_id,
            "duration": round(self.duration, 4),
        }


# ─── Resultados de resolución ──────────────────────────────────────────────

@dataclass
class NegotiationResult:
    """Resultado de una ronda de negociación."""
    conflict_id: str
    round_number: int
    concessions: List[Concession] = field(default_factory=list)
    agreement_reached: bool = False
    agreed_value: Optional[float] = None
    remaining_gap: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "round_number": self.round_number,
            "concessions": [c.to_dict() for c in self.concessions],
            "agreement_reached": self.agreement_reached,
            "agreed_value": self.agreed_value,
            "remaining_gap": round(self.remaining_gap, 6),
            "timestamp": self.timestamp,
        }


@dataclass
class Vote:
    """Voto de un agente en una votación ponderada."""
    agent_id: str
    option: str
    weight: float  # Ponderado por reputación
    raw_reputation: float
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "option": self.option,
            "weight": round(self.weight, 4),
            "raw_reputation": round(self.raw_reputation, 4),
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class VotingResult:
    """Resultado de una votación ponderada."""
    conflict_id: str
    votes: List[Vote] = field(default_factory=list)
    winner: Optional[str] = None
    winner_score: float = 0.0
    total_weight: float = 0.0
    consensus_threshold: float = 0.6
    consensus_reached: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "votes": [v.to_dict() for v in self.votes],
            "winner": self.winner,
            "winner_score": round(self.winner_score, 4),
            "total_weight": round(self.total_weight, 4),
            "consensus_threshold": self.consensus_threshold,
            "consensus_reached": self.consensus_reached,
            "timestamp": self.timestamp,
        }


@dataclass
class CNPBid:
    """Puja de un agente en el CNP dinámico."""
    agent_id: str
    task_id: str
    bid_score: float       # Auto-evaluación de capacidad
    confidence: float      # Confianza en completar la tarea
    reputation: float      # Reputación actual del agente
    estimated_cost: float  # Costo estimado
    estimated_latency_ms: float
    composite_score: float = 0.0  # Calculado: bid + confianza + reputación - costo
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "bid_score": round(self.bid_score, 4),
            "confidence": round(self.confidence, 4),
            "reputation": round(self.reputation, 4),
            "estimated_cost": round(self.estimated_cost, 4),
            "estimated_latency_ms": self.estimated_latency_ms,
            "composite_score": round(self.composite_score, 4),
            "timestamp": self.timestamp,
        }


@dataclass
class CNPResult:
    """Resultado de una ronda CNP con pujas dinámicas."""
    conflict_id: str
    task_id: str
    bids: List[CNPBid] = field(default_factory=list)
    winner: Optional[str] = None
    winner_score: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "task_id": self.task_id,
            "bids": [b.to_dict() for b in self.bids],
            "winner": self.winner,
            "winner_score": round(self.winner_score, 4),
            "timestamp": self.timestamp,
        }


@dataclass
class EscalationResult:
    """Resultado de la escalación al orquestador de nivel superior."""
    conflict_id: str
    verdict: EscalationVerdict
    decided_by: str  # GeneralOrchestrator o MetacognitiveMonitor
    reasoning: str
    actions: List[str] = field(default_factory=list)
    requires_human_review: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "verdict": self.verdict.value,
            "decided_by": self.decided_by,
            "reasoning": self.reasoning,
            "actions": self.actions,
            "requires_human_review": self.requires_human_review,
            "timestamp": self.timestamp,
        }


@dataclass
class ConflictResolutionResult:
    """Resultado completo de la resolución de un conflicto."""
    conflict: Conflict
    level_reached: ResolutionLevel
    negotiation_result: Optional[NegotiationResult] = None
    voting_result: Optional[VotingResult] = None
    cnp_result: Optional[CNPResult] = None
    escalation_result: Optional[EscalationResult] = None
    success: bool = False
    total_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict": self.conflict.to_dict(),
            "level_reached": self.level_reached.name,
            "negotiation_result": self.negotiation_result.to_dict() if self.negotiation_result else None,
            "voting_result": self.voting_result.to_dict() if self.voting_result else None,
            "cnp_result": self.cnp_result.to_dict() if self.cnp_result else None,
            "escalation_result": self.escalation_result.to_dict() if self.escalation_result else None,
            "success": self.success,
            "total_duration": round(self.total_duration, 4),
        }
