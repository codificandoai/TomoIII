"""Tests del bus de mensajes y agentes de Mustiamente."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from agents import (
    CriticAgent,
    ExecutorAgent,
    PlannerAgent,
    SimulatorAgent,
    UserProxyAgent,
)
from message_bus import MessageBus
from models import (
    AgentRole,
    FlightClass,
    FlightSearchRequest,
    MessageEnvelope,
    Priority,
)


def test_bus_routes_message_to_agent() -> None:
    bus = MessageBus()
    user = UserProxyAgent(bus)
    planner = PlannerAgent(bus)
    simulator = SimulatorAgent(bus)
    critic = CriticAgent(bus)
    executor = ExecutorAgent(bus)

    bus.register(user)
    bus.register(planner)
    bus.register(simulator)
    bus.register(critic)
    bus.register(executor)

    req = FlightSearchRequest(
        origin="MAD",
        destination="CUN",
        departure_date=datetime(2026, 8, 15, 10, 0),
        passengers=2,
        cabin_class=FlightClass.ECONOMY,
        max_price_usd=Decimal("1200.00"),
    )
    envelope = user.send(
        target=AgentRole.PLANNER,
        message_type="flight.search_request",
        payload=req,
        priority=Priority.HIGH,
    )
    assert envelope.source_agent == AgentRole.USER_PROXY
    assert envelope.target_agent == AgentRole.PLANNER
    assert planner.metrics["received"] >= 1


def test_full_agent_flow() -> None:
    bus = MessageBus()
    planner = PlannerAgent(bus)
    simulator = SimulatorAgent(bus)
    critic = CriticAgent(bus)
    executor = ExecutorAgent(bus)
    user = UserProxyAgent(bus)

    bus.register(planner)
    bus.register(simulator)
    bus.register(critic)
    bus.register(executor)
    bus.register(user)

    req = FlightSearchRequest(
        origin="MAD",
        destination="CUN",
        departure_date=datetime(2026, 8, 15, 10, 0),
        passengers=2,
        cabin_class=FlightClass.ECONOMY,
        max_price_usd=Decimal("1200.00"),
    )
    user.request_plan(req)

    # El flujo genera múltiples mensajes: search_response, simulate, critique, execution
    assert bus.history
    assert any(env.message_type == "plan.simulate_request" for env in bus.history)
    assert any(env.message_type == "plan.critique_response" for env in bus.history)


def test_interceptor_can_block_message() -> None:
    bus = MessageBus()
    user = UserProxyAgent(bus)
    planner = PlannerAgent(bus)
    bus.register(user)
    bus.register(planner)

    blocked: list[str] = []

    def block_simulation(env: MessageEnvelope) -> MessageEnvelope | None:
        if env.message_type == "plan.simulate_request":
            blocked.append("blocked")
            return None
        return env

    bus.add_interceptor(block_simulation)

    req = FlightSearchRequest(
        origin="MAD",
        destination="CUN",
        departure_date=datetime(2026, 8, 15, 10, 0),
        passengers=1,
        cabin_class=FlightClass.ECONOMY,
        max_price_usd=Decimal("1000.00"),
    )
    user.request_plan(req)

    assert blocked
    assert not any(env.message_type == "plan.simulate_response" for env in bus.history)
