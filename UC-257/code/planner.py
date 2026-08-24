"""Planificación de viajes y motor de decisión del agente autónomo."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from models import AgentAction, AgentPlan, Flight, Hotel, ServiceType, TripRequest
from travel_services import BookingManager, TravelInventory

logger = logging.getLogger("uc257-planner")


class TravelPlanner:
    """Genera un plan de acciones para satisfacer un TripRequest."""

    def __init__(
        self,
        inventory: TravelInventory,
        booking_manager: BookingManager,
    ) -> None:
        self.inventory = inventory
        self.bookings = booking_manager

    def create_plan(self, request: TripRequest) -> AgentPlan:
        """Crea un plan inicial con acciones de búsqueda y reserva."""
        actions: List[AgentAction] = []
        # 1. Buscar y reservar vuelo
        actions.append(
            AgentAction(
                agent="flight_search_agent",
                action="search_flights",
                parameters={
                    "origin": request.origin,
                    "destination": request.destination,
                    "date": request.departure_date,
                },
            )
        )
        actions.append(
            AgentAction(
                agent="flight_agent",
                action="book_best_flight",
                parameters={"preference": "cheapest"},
            )
        )
        # 2. Monitorizar estado del vuelo (característica autónoma)
        actions.append(
            AgentAction(
                agent="monitor_agent",
                action="monitor_flight",
                parameters={},
            )
        )
        # 3. Buscar y reservar hotel
        actions.append(
            AgentAction(
                agent="hotel_search_agent",
                action="search_hotels",
                parameters={
                    "destination": request.destination,
                    "check_in": request.departure_date,
                    "check_out": request.return_date,
                },
            )
        )
        actions.append(
            AgentAction(
                agent="hotel_agent",
                action="book_best_hotel",
                parameters={},
            )
        )
        # 4. Actividades (opcional)
        actions.append(
            AgentAction(
                agent="activity_search_agent",
                action="search_activities",
                parameters={
                    "destination": request.destination,
                    "date": request.departure_date,
                },
            )
        )
        actions.append(
            AgentAction(
                agent="activity_agent",
                action="book_best_activity",
                parameters={},
            )
        )
        # 5. Alinear reuniones
        if request.meeting_ids:
            for meeting_id in request.meeting_ids:
                actions.append(
                    AgentAction(
                        agent="meeting_agent",
                        action="reschedule_meeting_if_needed",
                        parameters={"meeting_id": meeting_id},
                    )
                )
        return AgentPlan(
            request_id=request.request_id,
            goal=f"Planificar viaje {request.origin}->{request.destination} el {request.departure_date}",
            actions=actions,
        )

    def handle_disruption(
        self,
        plan: AgentPlan,
        flight: Flight,
    ) -> List[AgentAction]:
        """Genera acciones correctivas ante la cancelación de un vuelo."""
        recovery = [
            AgentAction(
                agent="monitor_agent",
                action="report_cancellation",
                parameters={"flight_id": flight.flight_id},
            ),
            AgentAction(
                agent="flight_agent",
                action="rebook_flight",
                parameters={
                    "old_flight_id": flight.flight_id,
                    "origin": flight.origin,
                    "destination": flight.destination,
                    "date": flight.departure_time[:10],
                },
            ),
            AgentAction(
                agent="hotel_agent",
                action="adjust_hotel_booking",
                parameters={},
            ),
            AgentAction(
                agent="meeting_agent",
                action="reschedule_meeting_if_needed",
                parameters={},
            ),
        ]
        plan.messages.append(
            f"Vuelo {flight.flight_id} cancelado. Iniciando recuperación autónoma."
        )
        return recovery
