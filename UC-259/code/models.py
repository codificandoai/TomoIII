"""Modelos de datos y utilidades para UC-259."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def add_minutes(value: str, minutes: int) -> str:
    dt = parse_iso(value) or datetime.fromisoformat(value)
    return (dt + timedelta(minutes=minutes)).isoformat()


def fmt_date(value: datetime) -> str:
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
            request_id=str(data.get("request_id", uuid.uuid4())),
        )


@dataclass
class SafetyCheck:
    """Resultado de una validación de seguridad."""

    allowed: bool
    flags: List[str] = field(default_factory=list)
    sanitized_input: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "flags": self.flags,
            "sanitized_input": self.sanitized_input,
        }
