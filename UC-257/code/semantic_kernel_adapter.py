"""Adaptador opcional de Semantic Kernel para el asistente dependiente.

Si Semantic Kernel o una API key no están disponibles, delega en el motor
interno determinista del orquestador para que los tests y demos funcionen
sin conectividad.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agent_orchestrator import TravelAgentOrchestrator
from config import AppConfig
from models import TravelState, TripRequest

logger = logging.getLogger("uc257-semantic-kernel")


class SemanticKernelAdapter:
    """Envoltorio que usa Semantic Kernel cuando está disponible."""

    def __init__(
        self,
        config: AppConfig,
        orchestrator: TravelAgentOrchestrator,
    ) -> None:
        self.config = config
        self.orchestrator = orchestrator
        self.kernel = None
        self._init_kernel()

    def _init_kernel(self) -> None:
        if not self.config.frameworks.use_semantic_kernel:
            return
        try:
            from semantic_kernel import Kernel
            from semantic_kernel.functions.kernel_function import kernel_function

            self.kernel = Kernel()

            # Plugin interno que delega en los servicios del orquestador
            class TravelFunctionsPlugin:
                def __init__(self, orchestrator: TravelAgentOrchestrator):
                    self.orchestrator = orchestrator

                @kernel_function(description="Busca vuelos disponibles")
                def search_flights(self, origin: str, destination: str, date: str) -> str:
                    flights = self.orchestrator.inventory.search_flights(
                        origin, destination, date
                    )
                    return str([f.to_dict() for f in flights[:3]])

                @kernel_function(description="Reserva el mejor vuelo")
                def book_best_flight(self, origin: str, destination: str, date: str) -> str:
                    flights = self.orchestrator.inventory.search_flights(
                        origin, destination, date
                    )
                    if not flights:
                        return "No hay vuelos"
                    from models import AgentAction
                    state = TravelState(
                        request=TripRequest(
                            origin=origin, destination=destination, departure_date=date
                        )
                    )
                    action = AgentAction(
                        agent="flight_agent",
                        action="book_best_flight",
                        parameters={},
                    )
                    executed = self.orchestrator._execute_action(action, state)
                    return str(executed.result)

            self.kernel.add_plugin(
                TravelFunctionsPlugin(self.orchestrator), plugin_name="Travel"
            )

            # Servicio LLM opcional
            if self.config.llm.provider == "openai" and self.config.llm.api_key:
                from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

                self.kernel.add_service(
                    OpenAIChatCompletion(
                        service_id="chat",
                        ai_model_id=self.config.llm.model,
                        api_key=self.config.llm.api_key,
                    )
                )
            logger.info("Semantic Kernel inicializado")
        except Exception as exc:  # pragma: no cover
            logger.warning("No se pudo inicializar Semantic Kernel: %s", exc)
            self.kernel = None

    @staticmethod
    def _action(agent: str, action: str, parameters: Dict[str, Any]) -> Any:
        from models import AgentAction
        return AgentAction(agent=agent, action=action, parameters=parameters)

    def chat(
        self,
        user_id: str,
        message: str,
        state: Optional[TravelState] = None,
    ) -> Dict[str, Any]:
        """Procesa un mensaje del usuario."""
        if self.kernel is not None and self.config.llm.provider != "stub":
            # Invocación real por prompt. Requiere LLM.
            try:
                import asyncio
                from semantic_kernel.contents.chat_history import ChatHistory

                history = ChatHistory()
                history.add_user_message(message)
                result = asyncio.get_event_loop().run_until_complete(
                    self.kernel.invoke_prompt(
                        "{{$message}}",
                        arguments={"message": message},
                    )
                )
                return {"mode": "semantic-kernel", "response": str(result), "state": state.to_dict() if state else None}
            except Exception as exc:  # pragma: no cover
                logger.warning("Error en Semantic Kernel: %s", exc)
        # Fallback determinista
        return self.orchestrator.process_user_message(user_id, message, state)
