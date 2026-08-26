"""Modelos de datos BDI y utilidades para UC-260."""
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
        )


class Belief(BaseModel):
    """Lo que el agente cree que es cierto sobre el mundo."""

    fact: str = Field(description="Hecho observado o inferido")
    certainty: float = Field(ge=0.0, le=1.0, description="Confianza 0-1")
    source: str = Field(description="Origen de la creencia")
    topic: str = Field(default="general", description="Tema: delay, cost, availability, ...")
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Desire(BaseModel):
    """Objetivo motivacional del agente."""

    goal: str = Field(description="Estado deseado")
    priority: int = Field(ge=1, le=10, description="Prioridad 1-10")
    satisfied: bool = Field(default=False)
    threatened: bool = Field(default=False)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Intention(BaseModel):
    """Compromiso de acción para satisfacer un deseo."""

    plan_name: str = Field(description="Nombre descriptivo del plan")
    action: str = Field(default="", description="Tipo de acción: rebook_flight, adjust_meeting, wait, escalate")
    target_desire: str = Field(description="Deseo al que apunta")
    params: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="FORMULATED")  # FORMULATED, EXECUTING, COMPLETED, ABORTED
    reasoning: str = Field(default="", description="Justificación del agente")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Experience(BaseModel):
    """Experiencia aprendida del agente para evolucionar."""

    context: str = Field(description="Situación, ej. vuelo AA123 ruta MAD-BCN")
    action: str = Field(description="Acción ejecutada")
    outcome: str = Field(description="Resultado observado")
    utility: float = Field(default=0.0, description="Utilidad: positiva si ayudó, negativa si perjudicó")
    timestamp: str = Field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
