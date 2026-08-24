"""Modelos de datos para el sistema de agentes de viajes."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REBOOKED = "rebooked"


class ServiceType(str, Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
    ACTIVITY = "activity"
    MEETING = "meeting"


@dataclass
class TripRequest:
    """Solicitud de viaje del usuario."""

    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    travelers: int = 1
    budget: Optional[float] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    meeting_ids: List[str] = field(default_factory=list)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "travelers": self.travelers,
            "budget": self.budget,
            "preferences": self.preferences,
            "meeting_ids": self.meeting_ids,
            "created_at": self.created_at,
        }


@dataclass
class Flight:
    flight_id: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: float
    airline: str
    status: str = "scheduled"  # scheduled, cancelled, delayed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flight_id": self.flight_id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "price": self.price,
            "airline": self.airline,
            "status": self.status,
        }


@dataclass
class Hotel:
    hotel_id: str
    name: str
    destination: str
    check_in: str
    check_out: Optional[str]
    price_per_night: float
    rating: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hotel_id": self.hotel_id,
            "name": self.name,
            "destination": self.destination,
            "check_in": self.check_in,
            "check_out": self.check_out,
            "price_per_night": self.price_per_night,
            "rating": self.rating,
        }


@dataclass
class Activity:
    activity_id: str
    name: str
    destination: str
    date: str
    price: float
    category: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "name": self.name,
            "destination": self.destination,
            "date": self.date,
            "price": self.price,
            "category": self.category,
        }


@dataclass
class Booking:
    booking_id: str
    service_type: ServiceType
    reference_id: str
    status: BookingStatus
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "booking_id": self.booking_id,
            "service_type": self.service_type.value,
            "reference_id": self.reference_id,
            "status": self.status.value,
            "details": self.details,
            "created_at": self.created_at,
        }


@dataclass
class Meeting:
    meeting_id: str
    title: str
    scheduled_time: str
    timezone: str = "UTC"
    status: str = "scheduled"  # scheduled, rescheduled, cancelled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "scheduled_time": self.scheduled_time,
            "timezone": self.timezone,
            "status": self.status,
        }


@dataclass
class AgentAction:
    """Acción atómica ejecutada por un agente especializado."""

    agent: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    executed_at: Optional[str] = None
    success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "action": self.action,
            "parameters": self.parameters,
            "result": self.result,
            "executed_at": self.executed_at,
            "success": self.success,
        }


@dataclass
class AgentPlan:
    """Plan generado por el orquestador para un viaje."""

    request_id: str
    goal: str
    actions: List[AgentAction] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "goal": self.goal,
            "status": self.status,
            "actions": [a.to_dict() for a in self.actions],
            "messages": self.messages,
        }


@dataclass
class TravelState:
    """Estado global del viaje: vuelos, hoteles, actividades, reuniones."""

    request: TripRequest
    bookings: Dict[str, Booking] = field(default_factory=dict)
    selected_flight: Optional[Flight] = None
    selected_hotel: Optional[Hotel] = None
    selected_activities: List[Activity] = field(default_factory=list)
    meetings: Dict[str, Meeting] = field(default_factory=dict)
    notifications: List[str] = field(default_factory=list)
    log: List[AgentAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "bookings": {k: v.to_dict() for k, v in self.bookings.items()},
            "selected_flight": self.selected_flight.to_dict() if self.selected_flight else None,
            "selected_hotel": self.selected_hotel.to_dict() if self.selected_hotel else None,
            "selected_activities": [a.to_dict() for a in self.selected_activities],
            "meetings": {k: v.to_dict() for k, v in self.meetings.items()},
            "notifications": self.notifications,
            "log_count": len(self.log),
        }


@dataclass
class AgentResult:
    """Resultado de la ejecución autónoma del agente."""

    request_id: str
    status: str
    final_state: Dict[str, Any]
    plan: Dict[str, Any]
    summary: str
    notifications: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "final_state": self.final_state,
            "plan": self.plan,
            "summary": self.summary,
            "notifications": self.notifications,
        }
