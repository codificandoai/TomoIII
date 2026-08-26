"""Modelos de datos para UC-262: IA Genérica evolutiva con memoria y razonamiento."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_date(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    return value.date().isoformat()


@dataclass
class TravelRequest:
    """Solicitud de planificación de viaje."""

    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    travelers: int = 1
    budget: Optional[float] = None
    currency: str = "USD"
    preferences: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    long_term_goals: List[str] = field(default_factory=list)
    confirm_irreversible: bool = False
    predict_delays: bool = True
    enable_learning: bool = True
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "anonymous"
    thread_id: str = ""
    human_feedback: str = ""
    approved_alternative: str = ""

    def to_state(self) -> Dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "travelers": self.travelers,
            "budget": self.budget,
            "currency": self.currency,
            "preferences": self.preferences,
            "constraints": self.constraints,
            "long_term_goals": self.long_term_goals,
            "confirm_irreversible": self.confirm_irreversible,
            "predict_delays": self.predict_delays,
            "enable_learning": self.enable_learning,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "thread_id": self.thread_id,
            "human_feedback": self.human_feedback,
            "approved_alternative": self.approved_alternative,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TravelRequest":
        return cls(
            origin=str(data.get("origin", "")).strip(),
            destination=str(data.get("destination", "")).strip(),
            departure_date=str(data.get("departure_date", "")).strip(),
            return_date=str(data["return_date"]).strip() if data.get("return_date") else None,
            travelers=int(data.get("travelers", 1) or 1),
            budget=float(data["budget"]) if data.get("budget") is not None else None,
            currency=str(data.get("currency", "USD")).strip() or "USD",
            preferences=dict(data.get("preferences", {}) or {}),
            constraints=list(data.get("constraints", []) or []),
            long_term_goals=list(data.get("long_term_goals", []) or []),
            confirm_irreversible=bool(data.get("confirm_irreversible", False)),
            predict_delays=bool(data.get("predict_delays", True)),
            enable_learning=bool(data.get("enable_learning", True)),
            request_id=str(data.get("request_id", uuid.uuid4())),
            user_id=str(data.get("user_id", "anonymous")),
            thread_id=str(data.get("thread_id", "")),
            human_feedback=str(data.get("human_feedback", "")),
            approved_alternative=str(data.get("approved_alternative", "")),
        )


class Belief(BaseModel):
    fact: str = Field(description="Hecho observado o inferido")
    certainty: float = Field(ge=0.0, le=1.0, default=0.8)
    source: str = Field(default="inference", description="Origen de la creencia")
    topic: str = Field(default="general")
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Desire(BaseModel):
    goal: str = Field(description="Estado deseado")
    priority: int = Field(ge=1, le=10, default=5)
    satisfied: bool = Field(default=False)
    threatened: bool = Field(default=False)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Intention(BaseModel):
    plan_name: str = Field(default="")
    action: str = Field(default="")
    target_desire: str = Field(default="")
    params: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="FORMULATED")
    reasoning: str = Field(default="")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class PolicyGenome(BaseModel):
    """Genoma de un agente evolutivo: pesos de decisión y metaparámetros."""

    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    generation: int = Field(default=0)
    weights: Dict[str, float] = Field(default_factory=dict)
    mutation_rate: float = Field(ge=0.0, le=1.0, default=0.1)
    alive: bool = Field(default=True)
    lineage: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class PlanEvaluation(BaseModel):
    """Evaluación de un plan candidato."""

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = Field(default="")
    fitness: float = Field(default=0.0)
    cost_score: float = Field(default=0.0)
    time_score: float = Field(default=0.0)
    comfort_score: float = Field(default=0.0)
    risk_score: float = Field(default=0.0)
    goal_alignment: float = Field(default=0.0)
    violations: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AgentCandidate(BaseModel):
    """Agente candidato con su genoma y plan generado."""

    agent_id: str = Field(default="")
    genome: Dict[str, Any] = Field(default_factory=dict)
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation: Dict[str, Any] = Field(default_factory=dict)
    reasoning: List[str] = Field(default_factory=list)
    alive: bool = Field(default=True)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class UserProfile(BaseModel):
    """Perfil persistente del usuario: preferencias y reglas aprendidas."""

    user_id: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    long_term_goals: List[str] = Field(default_factory=list)
    learned_rules: List[Dict[str, Any]] = Field(default_factory=list)
    past_mistakes: List[str] = Field(default_factory=list)
    policy_archive: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    def add_rule(self, rule: str, source: str = "meta_learning", utility: float = 0.0) -> None:
        self.learned_rules.append(
            {"rule": rule, "source": source, "utility": utility, "timestamp": now_iso()}
        )
        self.updated_at = now_iso()

    def add_past_mistake(self, mistake: str) -> None:
        if mistake not in self.past_mistakes:
            self.past_mistakes.append(mistake)
        self.updated_at = now_iso()

    def archive_policy(self, genome: Dict[str, Any], fitness: float) -> None:
        self.policy_archive.append(
            {"genome": genome, "fitness": fitness, "timestamp": now_iso()}
        )
        # Mantener solo las mejores políticas
        self.policy_archive = sorted(
            self.policy_archive, key=lambda p: p.get("fitness", 0.0), reverse=True
        )[:20]
        self.updated_at = now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(**data)


class Reflection(BaseModel):
    stage: str = Field(default="", description="memory|reason|self_reflect|collaborate|evolve|learn")
    message: str = Field(default="")
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
