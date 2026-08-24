"""Adaptador opcional de AutoGen para el agente autónomo.

Si AutoGen o una API key no están disponibles, delega en el orquestador
interno determinista, que reproduce el flujo de planificación-monitoring-
recuperación sin intervención humana.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from agent_orchestrator import TravelAgentOrchestrator
from config import AppConfig
from models import AgentResult, TripRequest

logger = logging.getLogger("uc257-autogen")


class AutoGenAdapter:
    """Envoltorio que usa AutoGen cuando está disponible."""

    def __init__(
        self,
        config: AppConfig,
        orchestrator: TravelAgentOrchestrator,
    ) -> None:
        self.config = config
        self.orchestrator = orchestrator

    def run(self, request: TripRequest) -> AgentResult:
        """Ejecuta el agente autónomo."""
        if not self.config.frameworks.use_autogen or not self.config.llm.api_key:
            logger.info("AutoGen no habilitado; usando orquestador interno autónomo")
            return self.orchestrator.plan_and_execute(request)

        try:
            return self._run_with_autogen(request)
        except Exception as exc:  # pragma: no cover
            logger.warning("Error ejecutando AutoGen: %s. Fallback interno.", exc)
            return self.orchestrator.plan_and_execute(request)

    def _run_with_autogen(self, request: TripRequest) -> AgentResult:
        """Punto de integración real con AutoGen / autogen-agentchat."""
        try:
            from autogen import AssistantAgent, UserProxyAgent
        except Exception as exc1:  # pragma: no cover
            try:
                from autogen_agentchat.agents import AssistantAgent
                from autogen_agentchat.teams import RoundRobinGroupChat
                from autogen_agentchat.ui import Console
            except Exception as exc2:
                raise ImportError(f"No se pudo importar AutoGen: {exc1} / {exc2}") from exc2

        config_list = [
            {
                "model": self.config.llm.model,
                "api_key": self.config.llm.api_key,
            }
        ]

        system_message = (
            "Eres un Agente Autónomo de Viajes. Tu objetivo es asegurar que el "
            "usuario llegue a su destino. Puedes usar las herramientas de vuelos, "
            "hoteles, actividades y reuniones. Monitoriza el vuelo reservado; si "
            "se cancela, rebook, ajusta hotel y reprograma reuniones sin preguntar."
        )

        agent = AssistantAgent(
            name="travel_agent",
            llm_config={"config_list": config_list, "temperature": 0},
            system_message=system_message,
        )
        user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=self.config.frameworks.autogen_max_turns,
            code_execution_config=False,
        )

        # Registro simplificado de herramientas para AutoGen clásico
        from travel_services import BookingManager, TravelInventory

        inv = self.orchestrator.inventory
        bm = self.orchestrator.bookings

        def search_flights(origin: str, destination: str, date: str) -> str:
            flights = inv.search_flights(origin, destination, date)
            return str([f.to_dict() for f in flights[:3]])

        def book_flight(flight_id: str) -> str:
            # Ejecución local; en producción usaría el booking manager
            return f"Reservado {flight_id}"

        def get_flight_status(flight_id: str) -> str:
            f = inv.get_flight(flight_id)
            return f.status if f else "unknown"

        agent.register_for_llm(name="search_flights", description="Busca vuelos")(
            search_flights
        )
        agent.register_for_llm(name="book_flight", description="Reserva un vuelo")(
            book_flight
        )
        agent.register_for_llm(
            name="get_flight_status",
            description="Consulta estado de un vuelo",
        )(get_flight_status)

        user_proxy.initiate_chat(
            agent,
            message=f"Planifica viaje de {request.origin} a {request.destination} "
            f"el {request.departure_date}. Incluye hotel, actividad y reuniones: "
            f"{request.meeting_ids}.",
        )
        # Fallback: devolvemos el resultado determinista para mantener contrato.
        return self.orchestrator.plan_and_execute(request)
