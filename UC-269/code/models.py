"""Modelos Pydantic para el protocolo Contract Net (UC-269)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskStatus(str, Enum):
    announced = "announced"
    bidding = "bidding"
    awarded = "awarded"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class TaskAnnouncement(BaseModel):
    """Anuncio broadcast del manager a los workers."""

    task_id: UUID = Field(default_factory=uuid4)
    title: str
    description: str = ""
    requirements: Dict[str, Any] = Field(default_factory=dict)
    deadline_seconds: Optional[int] = None
    status: TaskStatus = TaskStatus.announced
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkerProfile(BaseModel):
    """Perfil de un worker que participa en el Contract Net."""

    name: str
    skills: List[str] = Field(default_factory=list)
    skill_score: float = Field(ge=0.0, le=1.0)
    reliability: float = Field(ge=0.0, le=1.0, default=0.9)
    cost_factor: float = Field(ge=0.0)
    latency_factor: float = Field(ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Proposal(BaseModel):
    """Oferta presentada por un worker."""

    proposal_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    agent_name: str
    score: float = Field(..., description="Puntuación normalizada del worker")
    estimated_cost: Decimal = Field(..., decimal_places=2)
    estimated_latency_ms: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    message: str = ""
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ContractAward(BaseModel):
    """Notificación del ganador al manager/worker."""

    task_id: UUID
    proposal_id: UUID
    winner_name: str
    award_score: float
    awarded_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionReport(BaseModel):
    """Reporte de ejecución del worker adjudicatario."""

    task_id: UUID
    agent_name: str
    status: Literal["success", "partial", "failed"]
    result: str = ""
    execution_time_ms: int = Field(ge=0)
    cost_incurred: Decimal = Decimal("0.00")
    error: Optional[str] = None
    finished_at: datetime = Field(default_factory=datetime.utcnow)


class ConsensusLog(BaseModel):
    """Traza de auditoría del consenso."""

    task_id: UUID
    manager_name: str
    participants: List[str]
    proposals: List[Proposal]
    winner: Optional[str] = None
    award: Optional[ContractAward] = None
    report: Optional[ExecutionReport] = None
    consensus_score: float = 0.0
    status: TaskStatus
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class ContractNetOutcome(BaseModel):
    """Resultado completo de una ronda Contract Net."""

    task_id: UUID
    task_title: str
    status: TaskStatus
    proposals: List[Proposal]
    winner: Optional[str] = None
    award: Optional[ContractAward] = None
    report: Optional[ExecutionReport] = None
    consensus_log: ConsensusLog
    metrics: Dict[str, Any] = Field(default_factory=dict)
