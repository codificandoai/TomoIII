"""Modelos de datos para UC-261: BDI + adaptación + memoria de patrones."""
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
class FlightPlanRequest:
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
    confirm_irreversible: bool = False
    predict_delays: bool = True
    enable_learning: bool = True
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "anonymous"
    approved_action_ids: List[str] = field(default_factory=list)
    rejected_action_ids: List[str] = field(default_factory=list)
    auto_approve_all: bool = False

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
            "confirm_irreversible": self.confirm_irreversible,
            "predict_delays": self.predict_delays,
            "enable_learning": self.enable_learning,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "approved_action_ids": self.approved_action_ids,
            "rejected_action_ids": self.rejected_action_ids,
            "auto_approve_all": self.auto_approve_all,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlightPlanRequest":
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
            confirm_irreversible=bool(data.get("confirm_irreversible", False)),
            predict_delays=bool(data.get("predict_delays", True)),
            enable_learning=bool(data.get("enable_learning", True)),
            request_id=str(data.get("request_id", uuid.uuid4())),
            user_id=str(data.get("user_id", "anonymous")),
            approved_action_ids=list(data.get("approved_action_ids", []) or []),
            rejected_action_ids=list(data.get("rejected_action_ids", []) or []),
            auto_approve_all=bool(data.get("auto_approve_all", False)),
        )


class Belief(BaseModel):
    fact: str = Field(description="Hecho observado o inferido")
    certainty: float = Field(ge=0.0, le=1.0, description="Confianza 0-1")
    source: str = Field(description="Origen de la creencia")
    topic: str = Field(default="general", description="Tema: delay, cost, preference, ...")
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Desire(BaseModel):
    goal: str = Field(description="Estado deseado")
    priority: int = Field(ge=1, le=10, description="Prioridad 1-10")
    satisfied: bool = Field(default=False)
    threatened: bool = Field(default=False)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Intention(BaseModel):
    plan_name: str = Field(description="Nombre descriptivo del plan")
    action: str = Field(default="", description="Tipo de acción")
    target_desire: str = Field(description="Deseo al que apunta")
    params: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="FORMULATED")
    reasoning: str = Field(default="", description="Justificación del agente")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Experience(BaseModel):
    context: str = Field(description="Contexto de la experiencia")
    action: str = Field(description="Acción ejecutada")
    outcome: str = Field(description="Resultado observado")
    utility: float = Field(default=0.0)
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class UserProfile(BaseModel):
    """Perfil persistente del usuario: preferencias y puntuación de patrones."""

    user_id: str
    preferences: Dict[str, Any] = Field(default_factory=dict)
    pattern_scores: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    def record_outcome(self, pattern_key: str, action: str, outcome: str, utility: float) -> None:
        if pattern_key not in self.pattern_scores:
            self.pattern_scores[pattern_key] = {
                "accept": 0,
                "reject": 0,
                "score": 0.5,
                "last_action": "",
            }
        score_entry = self.pattern_scores[pattern_key]
        if outcome == "accepted":
            score_entry["accept"] += 1
        elif outcome == "rejected":
            score_entry["reject"] += 1
        total = score_entry["accept"] + score_entry["reject"]
        if total > 0:
            score_entry["score"] = score_entry["accept"] / total
        score_entry["last_action"] = action
        self.history.append(
            {"pattern_key": pattern_key, "action": action, "outcome": outcome, "utility": utility, "timestamp": now_iso()}
        )
        self.updated_at = now_iso()

    def get_pattern_confidence(self, pattern_key: str) -> float:
        return self.pattern_scores.get(pattern_key, {}).get("score", 0.5)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        return cls(**data)


class Recommendation(BaseModel):
    """Sugerencia personalizada generada por el agente adaptativo."""

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_id: str = Field(default="", description="Ítem del itinerario al que aplica")
    action: str = Field(description="Acción recomendada")
    reason: str = Field(description="Justificación")
    source_type: str = Field(default="AI_INFERENCE", description="PATTERN_MATCH o AI_INFERENCE")
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    cost_impact: float = Field(default=0.0)
    category: str = Field(default="general", description="flight, hotel, transport, dining, ...")
    status: str = Field(default="PENDING", description="PENDING, AUTO_EXECUTED, APPROVED, REJECTED")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
