"""Bus de mensajes interno entre agentes para UC-268.

Soporta:
- Routing por rol de agente.
- Interceptores para logging, tracing y seguridad.
- Historial limitado de mensajes.
- TTL y métricas.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Dict, List, Optional

from config import BusConfig, get_config
from models import AgentRole, MessageEnvelope, Priority


Interceptor = Callable[[MessageEnvelope], Optional[MessageEnvelope]]


class MessageBus:
    """Bus síncrono de mensajes entre agentes."""

    def __init__(self, config: Optional[BusConfig] = None) -> None:
        self.config = config or get_config().bus
        self.agents: Dict[AgentRole, "AgentBase"] = {}
        self.history: deque[MessageEnvelope] = deque(maxlen=self.config.max_history)
        self._interceptors: List[Interceptor] = []

    def register(self, agent: "AgentBase") -> None:
        self.agents[agent.role] = agent

    def add_interceptor(self, interceptor: Interceptor) -> None:
        self._interceptors.append(interceptor)

    def publish(self, envelope: MessageEnvelope) -> None:
        """Publica un mensaje, ejecutando interceptores y ruteando al agente destino."""
        if envelope.is_expired():
            return

        current: Optional[MessageEnvelope] = envelope
        for interceptor in self._interceptors:
            if current is None:
                return
            current = interceptor(current)

        target = self.agents.get(current.target_agent)
        if target is None:
            raise ValueError(f"No agent registered for {current.target_agent}")

        self.history.append(current)
        target._consume(current)

    def metrics(self) -> Dict[str, Any]:
        return {
            "agents_registered": len(self.agents),
            "history_size": len(self.history),
            "interceptors": len(self._interceptors),
        }


class AgentBase:
    """Base para todos los agentes del sistema."""

    def __init__(self, role: AgentRole, bus: MessageBus) -> None:
        self.role = role
        self.bus = bus
        self.metrics = {"sent": 0, "received": 0, "errors": 0}
        self._handlers: Dict[str, Callable[[MessageEnvelope], None]] = {}

    def register_handler(
        self, message_type: str, handler: Callable[[MessageEnvelope], None]
    ) -> None:
        self._handlers[message_type] = handler

    def send(
        self,
        target: AgentRole,
        message_type: str,
        payload: Any,
        *,
        correlation_id: Optional[Any] = None,
        causation_id: Optional[Any] = None,
        priority: Priority = Priority.NORMAL,
        ttl_ms: Optional[int] = None,
    ) -> MessageEnvelope:
        from uuid import uuid4
        from datetime import datetime

        envelope = MessageEnvelope(
            source_agent=self.role,
            target_agent=target,
            message_type=message_type,  # type: ignore[arg-type]
            payload=payload,
            correlation_id=correlation_id or uuid4(),
            causation_id=causation_id,
            priority=priority,
            ttl_ms=ttl_ms or self.config.bus.default_ttl_ms,
            timestamp=datetime.utcnow(),
        )
        self.bus.publish(envelope)
        self.metrics["sent"] += 1
        return envelope

    def _consume(self, envelope: MessageEnvelope) -> None:
        if envelope.is_expired():
            self.metrics["errors"] += 1
            return
        handler = self._handlers.get(envelope.message_type)
        if handler is None:
            self.metrics["errors"] += 1
            return
        try:
            handler(envelope)
            self.metrics["received"] += 1
        except Exception as exc:
            self.metrics["errors"] += 1
            self._handle_error(envelope, exc)

    def _handle_error(self, envelope: MessageEnvelope, error: Exception) -> None:
        self.send(
            target=envelope.source_agent,
            message_type="system.error",
            payload={
                "original_message_id": str(envelope.message_id),
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            causation_id=envelope.message_id,
            priority=Priority.HIGH,
        )

    @property
    def config(self):
        from config import get_config
        return get_config()
