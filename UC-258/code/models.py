"""Modelos de datos para el meta-framework de agentes adaptativos."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EnvironmentKind(str, Enum):
    CHESS = "chess"
    TRAVEL = "travel"
    STOCK = "stock"


class StrategyKind(str, Enum):
    EXACT_SEARCH = "exact_search"
    CONSTRAINT_PLANNING = "constraint_planning"
    PROBABILISTIC_RISK = "probabilistic_risk"
    DECISION_TREE = "decision_tree"


@dataclass
class EnvironmentProperties:
    """Dimensiones ontológicas del entorno."""

    name: str
    is_dynamic: bool
    is_deterministic: bool
    is_fully_observable: bool
    is_discrete: bool
    is_episodic: bool
    is_multi_agent: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_dynamic": self.is_dynamic,
            "is_deterministic": self.is_deterministic,
            "is_fully_observable": self.is_fully_observable,
            "is_discrete": self.is_discrete,
            "is_episodic": self.is_episodic,
            "is_multi_agent": self.is_multi_agent,
        }


@dataclass
class Observation:
    """Observación parcial o total del entorno."""

    data: Dict[str, Any]
    hidden: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    source: str = "internal"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "hidden": self.hidden,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "timestamp": self.timestamp,
        }


@dataclass
class StepResult:
    """Resultado de ejecutar una acción en el entorno."""

    observation: Observation
    reward: float = 0.0
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation": self.observation.to_dict(),
            "reward": round(self.reward, 4),
            "done": self.done,
            "info": self.info,
        }


@dataclass
class ExternalData:
    """Dato externo verificable con metadatos de confianza."""

    value: Any
    source: str
    confidence: float
    verified: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "verified": self.verified,
            "timestamp": self.timestamp,
            "note": self.note,
        }


@dataclass
class ToolCall:
    """Llamada a una herramienta externa."""

    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[ExternalData] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result.to_dict() if self.result else None,
            "latency_ms": round(self.latency_ms, 4),
        }


@dataclass
class TravelRequest:
    """Solicitud de itinerario para Komerzio.com."""

    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    travelers: int = 1
    budget: Optional[float] = None
    currency: str = "USD"
    preferences: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "travelers": self.travelers,
            "budget": self.budget,
            "currency": self.currency,
            "preferences": self.preferences,
            "constraints": self.constraints,
        }


@dataclass
class ItineraryItem:
    """Elemento de un itinerario."""

    item_type: str  # flight, hotel, activity
    name: str
    start_time: str
    end_time: str
    cost: float
    currency: str
    source: str
    confidence: float
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_type": self.item_type,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "cost": round(self.cost, 2),
            "currency": self.currency,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "notes": self.notes,
        }


@dataclass
class Itinerary:
    """Itinerario explicable."""

    request_id: str
    items: List[ItineraryItem] = field(default_factory=list)
    total_cost: float = 0.0
    currency: str = "USD"
    assumptions: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 0.0
    missing_info: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "items": [i.to_dict() for i in self.items],
            "total_cost": round(self.total_cost, 2),
            "currency": self.currency,
            "assumptions": self.assumptions,
            "alternatives": self.alternatives,
            "confidence": round(self.confidence, 4),
            "missing_info": self.missing_info,
        }


@dataclass
class ClarificationRequest:
    """Solicitud de aclaración al usuario."""

    question: str
    reason: str
    missing_field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "reason": self.reason,
            "missing_field": self.missing_field,
        }


@dataclass
class AgentAction:
    """Acción atómica del agente."""

    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    result: Optional[Any] = None
    success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "parameters": self.parameters,
            "requires_confirmation": self.requires_confirmation,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class Plan:
    """Plan generado por el agente."""

    goal: str
    strategy: StrategyKind
    actions: List[AgentAction] = field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "strategy": self.strategy.value,
            "actions": [a.to_dict() for a in self.actions],
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
        }


@dataclass
class SafetyCheck:
    """Resultado de validación de seguridad."""

    allowed: bool
    flags: List[str] = field(default_factory=list)
    sanitized_input: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "flags": self.flags,
            "sanitized_input": self.sanitized_input,
        }


@dataclass
class AgentTrace:
    """Traza completa de una ejecución del agente."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    environment_kind: str = ""
    properties: Optional[Dict[str, Any]] = None
    selected_strategy: str = ""
    plan: Optional[Dict[str, Any]] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)
    final_observation: Optional[Dict[str, Any]] = None
    reward: float = 0.0
    iterations: int = 0
    errors: List[str] = field(default_factory=list)
    safety_flags: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "environment_kind": self.environment_kind,
            "properties": self.properties,
            "selected_strategy": self.selected_strategy,
            "plan": self.plan,
            "actions": self.actions,
            "final_observation": self.final_observation,
            "reward": round(self.reward, 4),
            "iterations": self.iterations,
            "errors": self.errors,
            "safety_flags": self.safety_flags,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
        }
