"""Servicios simulados de viajes: vuelos, hoteles, actividades y reuniones.

En producción estas funciones envolverían APIs reales (Amadeus, Booking,
Google Calendar, etc.). Aquí mantienen un estado en memoria determinista
para poder testear el comportamiento del agente sin credenciales ni red.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from models import (
    Activity,
    Booking,
    BookingStatus,
    Flight,
    Hotel,
    Meeting,
    ServiceType,
)

logger = logging.getLogger("uc257-travel-services")


class TravelInventory:
    """Inventario simulado de vuelos, hoteles y actividades."""

    def __init__(self) -> None:
        self._flights: Dict[str, Flight] = {}
        self._hotels: Dict[str, Hotel] = {}
        self._activities: Dict[str, Activity] = {}
        self._meetings: Dict[str, Meeting] = {}
        self._seed()

    def _seed(self) -> None:
        # Vuelos deterministas para demos
        self.add_flight(
            Flight(
                flight_id="IB1001",
                origin="Madrid",
                destination="París",
                departure_time="2026-07-15T08:00:00",
                arrival_time="2026-07-15T10:30:00",
                price=120.0,
                airline="Iberia",
                status="scheduled",
            )
        )
        self.add_flight(
            Flight(
                flight_id="AF2002",
                origin="Madrid",
                destination="París",
                departure_time="2026-07-15T14:00:00",
                arrival_time="2026-07-15T16:30:00",
                price=150.0,
                airline="Air France",
                status="scheduled",
            )
        )
        self.add_flight(
            Flight(
                flight_id="RY3003",
                origin="Madrid",
                destination="París",
                departure_time="2026-07-15T18:00:00",
                arrival_time="2026-07-15T20:30:00",
                price=80.0,
                airline="Ryanair",
                status="scheduled",
            )
        )
        # Hotel
        self.add_hotel(
            Hotel(
                hotel_id="HTL-PAR-01",
                name="Le Marais Boutique",
                destination="París",
                check_in="2026-07-15",
                check_out="2026-07-18",
                price_per_night=180.0,
                rating=4.6,
            )
        )
        # Actividad
        self.add_activity(
            Activity(
                activity_id="ACT-PAR-01",
                name="Tour Louvre",
                destination="París",
                date="2026-07-15",
                price=25.0,
                category="cultural",
            )
        )
        # Reunión del usuario
        self.add_meeting(
            Meeting(
                meeting_id="meet-15",
                title="Reunión stakeholders",
                scheduled_time="2026-07-15T15:00:00",
                timezone="Europe/Paris",
            )
        )

    # ---------- Vuelos ----------
    def add_flight(self, flight: Flight) -> None:
        self._flights[flight.flight_id] = flight

    def search_flights(
        self, origin: str, destination: str, date: str
    ) -> List[Flight]:
        logger.info("search_flights: %s -> %s @ %s", origin, destination, date)
        results = [
            f
            for f in self._flights.values()
            if f.origin.lower() == origin.lower()
            and f.destination.lower() == destination.lower()
            and f.departure_time.startswith(date)
        ]
        return sorted(results, key=lambda x: x.price)

    def get_flight(self, flight_id: str) -> Optional[Flight]:
        return self._flights.get(flight_id)

    def cancel_flight(self, flight_id: str) -> bool:
        f = self._flights.get(flight_id)
        if not f:
            return False
        f.status = "cancelled"
        logger.warning("Vuelo %s CANCELADO", flight_id)
        return True

    def delay_flight(self, flight_id: str, minutes: int) -> bool:
        f = self._flights.get(flight_id)
        if not f:
            return False
        dt = datetime.fromisoformat(f.departure_time)
        f.departure_time = (dt + timedelta(minutes=minutes)).isoformat()
        f.status = "delayed"
        return True

    # ---------- Hoteles ----------
    def add_hotel(self, hotel: Hotel) -> None:
        self._hotels[hotel.hotel_id] = hotel

    def search_hotels(
        self, destination: str, check_in: str, check_out: Optional[str] = None
    ) -> List[Hotel]:
        results = [
            h
            for h in self._hotels.values()
            if h.destination.lower() == destination.lower()
            and h.check_in == check_in
        ]
        if check_out:
            results = [h for h in results if h.check_out == check_out]
        return sorted(results, key=lambda x: -x.rating)

    def get_hotel(self, hotel_id: str) -> Optional[Hotel]:
        return self._hotels.get(hotel_id)

    # ---------- Actividades ----------
    def add_activity(self, activity: Activity) -> None:
        self._activities[activity.activity_id] = activity

    def search_activities(
        self, destination: str, date: str, category: Optional[str] = None
    ) -> List[Activity]:
        results = [
            a
            for a in self._activities.values()
            if a.destination.lower() == destination.lower() and a.date == date
        ]
        if category:
            results = [a for a in results if a.category.lower() == category.lower()]
        return sorted(results, key=lambda x: x.price)

    # ---------- Reuniones ----------
    def add_meeting(self, meeting: Meeting) -> None:
        self._meetings[meeting.meeting_id] = meeting

    def get_meeting(self, meeting_id: str) -> Optional[Meeting]:
        return self._meetings.get(meeting_id)

    def reschedule_meeting(
        self, meeting_id: str, new_time_iso: str, reason: str
    ) -> bool:
        m = self._meetings.get(meeting_id)
        if not m:
            return False
        m.scheduled_time = new_time_iso
        m.status = "rescheduled"
        logger.info("Reunión %s reprogramada a %s. Motivo: %s", meeting_id, new_time_iso, reason)
        return True


class BookingManager:
    """Gestiona reservas activas y eventos de cancelación/rebooking."""

    def __init__(self, inventory: TravelInventory) -> None:
        self.inventory = inventory
        self.bookings: Dict[str, Booking] = {}

    def create_booking(
        self,
        service_type: ServiceType,
        reference_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Booking:
        booking = Booking(
            booking_id=str(uuid.uuid4())[:8],
            service_type=service_type,
            reference_id=reference_id,
            status=BookingStatus.CONFIRMED,
            details=details or {},
        )
        self.bookings[booking.booking_id] = booking
        logger.info("Reserva creada: %s -> %s", booking.booking_id, reference_id)
        return booking

    def get_booking(self, booking_id: str) -> Optional[Booking]:
        return self.bookings.get(booking_id)

    def cancel_booking(self, booking_id: str) -> bool:
        booking = self.bookings.get(booking_id)
        if not booking:
            return False
        booking.status = BookingStatus.CANCELLED
        logger.info("Reserva cancelada: %s", booking_id)
        return True

    def rebook_flight(
        self, old_flight_id: str, origin: str, destination: str, date: str
    ) -> Optional[Flight]:
        """Reemplaza un vuelo cancelado por la mejor alternativa disponible."""
        alternatives = self.inventory.search_flights(origin, destination, date)
        alternatives = [a for a in alternatives if a.flight_id != old_flight_id]
        if not alternatives:
            return None
        new_flight = alternatives[0]
        # Actualiza inventario
        old = self.inventory.get_flight(old_flight_id)
        if old:
            old.status = "cancelled"
        logger.info("Rebook %s -> %s", old_flight_id, new_flight.flight_id)
        return new_flight

    def list_bookings(self) -> List[Booking]:
        return list(self.bookings.values())
