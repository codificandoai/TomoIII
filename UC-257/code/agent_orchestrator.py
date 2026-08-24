"""Orquestador multi-agente para el sistema de viajes.

Implementa tanto el modo "asistente dependiente" (un turno por instrucción
humana) como el modo "agente autónomo" (bucle de planificación-ejecución-monitoring).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import AgentConfig
from models import (
    AgentAction,
    AgentPlan,
    AgentResult,
    Booking,
    BookingStatus,
    ServiceType,
    TravelState,
    TripRequest,
)
from planner import TravelPlanner
from travel_services import BookingManager, TravelInventory

logger = logging.getLogger("uc257-orchestrator")


class TravelAgentOrchestrator:
    """Orquesta agentes especializados para planificar y recuperar viajes."""

    def __init__(
        self,
        inventory: TravelInventory,
        booking_manager: BookingManager,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.inventory = inventory
        self.bookings = booking_manager
        self.config = config or AgentConfig()
        self.planner = TravelPlanner(inventory, booking_manager)
        self._states: Dict[str, TravelState] = {}

    # ------------------------------------------------------------------
    # Modo autónomo
    # ------------------------------------------------------------------
    def plan_and_execute(self, request: TripRequest) -> AgentResult:
        """Ejecuta el plan completo de forma autónoma, incluyendo recuperación."""
        state = TravelState(request)
        self._states[request.request_id] = state
        plan = self.planner.create_plan(request)
        plan.status = "in_progress"

        iteration = 0
        i = 0
        while i < len(plan.actions) and iteration < self.config.max_iterations:
            action = plan.actions[i]
            executed = self._execute_action(action, state)
            state.log.append(executed)
            plan.messages.append(
                f"[{executed.agent}] {executed.action} -> {executed.result}"
            )

            # Si acabamos de reservar un vuelo, monitorizarlo inmediatamente
            if executed.action == "book_best_flight" and executed.success:
                flight_id = executed.result
                flight = self.inventory.get_flight(flight_id)
                if flight and flight.status == "cancelled":
                    recovery = self.planner.handle_disruption(plan, flight)
                    # Insertar acciones de recuperación a continuación
                    plan.actions = plan.actions[: i + 1] + recovery + plan.actions[i + 1 :]

            i += 1
            iteration += 1

        plan.status = "completed" if i >= len(plan.actions) else "failed"
        summary = self._build_summary(state)
        return AgentResult(
            request_id=request.request_id,
            status=plan.status,
            final_state=state.to_dict(),
            plan=plan.to_dict(),
            summary=summary,
            notifications=state.notifications,
        )

    # ------------------------------------------------------------------
    # Modo asistente dependiente: un solo turno
    # ------------------------------------------------------------------
    def process_user_message(
        self, user_id: str, message: str, state: Optional[TravelState] = None
    ) -> Dict[str, Any]:
        """Procesa un mensaje del usuario y ejecuta una única acción."""
        intent = self._parse_intent(message)
        if state is None:
            request = TripRequest(
                origin="", destination="", departure_date="", request_id=user_id
            )
            state = TravelState(request)

        action = AgentAction(
            agent=intent.get("agent", "assistant"),
            action=intent.get("action", "unknown"),
            parameters=intent.get("parameters", {}),
        )
        executed = self._execute_action(action, state)
        return {
            "mode": "assistant",
            "user_message": message,
            "intent": intent,
            "action": executed.to_dict(),
            "state": state.to_dict(),
        }

    # ------------------------------------------------------------------
    # Ejecución de acciones por agentes especializados
    # ------------------------------------------------------------------
    def _execute_action(self, action: AgentAction, state: TravelState) -> AgentAction:
        action.executed_at = datetime.now(timezone.utc).isoformat()
        try:
            handler = getattr(self, f"_handle_{action.action}", None)
            if handler is None:
                action.result = f"Acción desconocida: {action.action}"
                action.success = False
                return action
            action.result = handler(action, state)
            action.success = True
        except Exception as exc:  # pragma: no cover - log & continue
            logger.exception("Error ejecutando %s", action.action)
            action.result = f"Error: {exc}"
            action.success = False
        return action

    # Handlers
    def _handle_search_flights(self, action: AgentAction, state: TravelState) -> str:
        p = action.parameters
        flights = self.inventory.search_flights(
            p.get("origin", state.request.origin),
            p.get("destination", state.request.destination),
            p.get("date", state.request.departure_date),
        )
        state.preferred_flights = flights  # type: ignore[attr-defined]
        if not hasattr(state, "_candidate_flights"):
            state._candidate_flights = []  # type: ignore[attr-defined]
        state._candidate_flights = flights  # type: ignore[attr-defined]
        return f"Encontrados {len(flights)} vuelos"

    def _handle_book_best_flight(self, action: AgentAction, state: TravelState) -> str:
        flights = getattr(state, "_candidate_flights", [])
        if not flights:
            flights = self.inventory.search_flights(
                state.request.origin, state.request.destination, state.request.departure_date
            )
        best = flights[0] if flights else None
        if not best:
            return "No hay vuelos disponibles"
        booking = self.bookings.create_booking(
            ServiceType.FLIGHT, best.flight_id, details=best.to_dict()
        )
        state.selected_flight = best
        state.bookings[booking.booking_id] = booking
        state.notifications.append(
            f"Vuelo reservado: {best.flight_id} ({best.airline}) a las {best.departure_time}"
        )
        return best.flight_id

    def _handle_monitor_flight(self, action: AgentAction, state: TravelState) -> str:
        flight = state.selected_flight
        if not flight:
            return "No hay vuelo activo para monitorizar"
        status = flight.status
        if status == "cancelled":
            state.notifications.append(
                f"ALERTA: vuelo {flight.flight_id} cancelado. Rebook automático en curso."
            )
            return "CANCELLED"
        return status

    def _handle_rebook_flight(self, action: AgentAction, state: TravelState) -> str:
        old_id = action.parameters.get("old_flight_id")
        old = self.inventory.get_flight(old_id) if old_id else None
        origin = action.parameters.get("origin") or (old.origin if old else state.request.origin)
        destination = action.parameters.get("destination") or (
            old.destination if old else state.request.destination
        )
        date = (
            action.parameters.get("date")
            or (old.departure_time[:10] if old else state.request.departure_date)
        )
        new_flight = self.bookings.rebook_flight(old_id or "", origin, destination, date)
        if not new_flight:
            return "No hay alternativas de vuelo"
        # Actualizar booking activo
        for b in list(state.bookings.values()):
            if b.service_type == ServiceType.FLIGHT and b.reference_id == old_id:
                b.status = BookingStatus.REBOOKED
        booking = self.bookings.create_booking(
            ServiceType.FLIGHT, new_flight.flight_id, details=new_flight.to_dict()
        )
        state.selected_flight = new_flight
        state.bookings[booking.booking_id] = booking
        state.notifications.append(
            f"Rebook exitoso: {old_id} -> {new_flight.flight_id}"
        )
        return new_flight.flight_id

    def _handle_search_hotels(self, action: AgentAction, state: TravelState) -> str:
        p = action.parameters
        hotels = self.inventory.search_hotels(
            p.get("destination", state.request.destination),
            p.get("check_in", state.request.departure_date),
            p.get("check_out", state.request.return_date),
        )
        state._candidate_hotels = hotels  # type: ignore[attr-defined]
        return f"Encontrados {len(hotels)} hoteles"

    def _handle_book_best_hotel(self, action: AgentAction, state: TravelState) -> str:
        hotels = getattr(state, "_candidate_hotels", [])
        if not hotels:
            return "No hay hoteles disponibles"
        best = hotels[0]
        booking = self.bookings.create_booking(
            ServiceType.HOTEL, best.hotel_id, details=best.to_dict()
        )
        state.selected_hotel = best
        state.bookings[booking.booking_id] = booking
        state.notifications.append(f"Hotel reservado: {best.name}")
        return best.hotel_id

    def _handle_adjust_hotel_booking(self, action: AgentAction, state: TravelState) -> str:
        hotel = state.selected_hotel
        if not hotel:
            return "No hay hotel que ajustar"
        # Simular ajuste de check-in a la nueva llegada
        flight = state.selected_flight
        new_check_in = flight.departure_time[:10] if flight else hotel.check_in
        hotel.check_in = new_check_in
        state.notifications.append(
            f"Hotel {hotel.hotel_id} ajustado al check-in {new_check_in}"
        )
        return hotel.hotel_id

    def _handle_search_activities(self, action: AgentAction, state: TravelState) -> str:
        p = action.parameters
        activities = self.inventory.search_activities(
            p.get("destination", state.request.destination),
            p.get("date", state.request.departure_date),
        )
        state._candidate_activities = activities  # type: ignore[attr-defined]
        return f"Encontradas {len(activities)} actividades"

    def _handle_book_best_activity(self, action: AgentAction, state: TravelState) -> str:
        activities = getattr(state, "_candidate_activities", [])
        if not activities:
            return "No hay actividades disponibles"
        best = activities[0]
        booking = self.bookings.create_booking(
            ServiceType.ACTIVITY, best.activity_id, details=best.to_dict()
        )
        state.selected_activities.append(best)
        state.bookings[booking.booking_id] = booking
        state.notifications.append(f"Actividad reservada: {best.name}")
        return best.activity_id

    def _handle_reschedule_meeting_if_needed(
        self, action: AgentAction, state: TravelState
    ) -> str:
        meeting_id = action.parameters.get("meeting_id") or (
            state.request.meeting_ids[0] if state.request.meeting_ids else None
        )
        if not meeting_id:
            return "Sin reuniones para reprogramar"
        meeting = self.inventory.get_meeting(meeting_id)
        if not meeting:
            return f"Reunión {meeting_id} no encontrada"
        flight = state.selected_flight
        if not flight:
            return "Sin vuelo para calcular hora de llegada"
        arrival = datetime.fromisoformat(flight.arrival_time)
        # Reprogramar 2 horas después de la llegada estimada
        new_time = (arrival + timedelta(hours=2)).isoformat()
        ok = self.inventory.reschedule_meeting(
            meeting_id, new_time, reason=f"Llegada del vuelo {flight.flight_id}"
        )
        state.meetings[meeting_id] = meeting
        state.notifications.append(
            f"Reunión {meeting_id} movida a {new_time}"
        )
        return "rescheduled" if ok else "failed"

    def _handle_report_cancellation(self, action: AgentAction, state: TravelState) -> str:
        fid = action.parameters.get("flight_id")
        state.notifications.append(f"Reportada cancelación del vuelo {fid}")
        return f"reported:{fid}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_intent(message: str) -> Dict[str, Any]:
        """Parser léxico básico de intenciones para el asistente dependiente."""
        lower = message.lower()
        if any(w in lower for w in ("vuelo", "flight", "avión", "billete")):
            return {
                "agent": "flight_search_agent",
                "action": "search_flights",
                "parameters": {},
            }
        if any(w in lower for w in ("reserva", "reservar", "book")):
            return {"agent": "flight_agent", "action": "book_best_flight", "parameters": {}}
        if any(w in lower for w in ("hotel", "alojamiento")):
            return {"agent": "hotel_search_agent", "action": "search_hotels", "parameters": {}}
        if any(w in lower for w in ("reunión", "meeting")):
            return {
                "agent": "meeting_agent",
                "action": "reschedule_meeting_if_needed",
                "parameters": {},
            }
        return {"agent": "assistant", "action": "unknown", "parameters": {}}

    def _build_summary(self, state: TravelState) -> str:
        parts = [
            f"Viaje planificado: {state.request.origin} -> {state.request.destination}",
        ]
        if state.selected_flight:
            parts.append(
                f"Vuelo: {state.selected_flight.flight_id} ({state.selected_flight.status})"
            )
        if state.selected_hotel:
            parts.append(f"Hotel: {state.selected_hotel.name}")
        if state.selected_activities:
            parts.append(
                f"Actividades: {', '.join(a.name for a in state.selected_activities)}"
            )
        if state.meetings:
            parts.append(f"Reuniones ajustadas: {len(state.meetings)}")
        return "; ".join(parts)
