"""Agentes concretos de Mustiamente para UC-268.

Comunican mediante el bus interno con envelopes tipados. Cada agente puede
ser expuesto también como un endpoint A2A remoto a través del servidor Flask.
"""
from __future__ import annotations

import random
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from message_bus import AgentBase, MessageBus
from models import (
    AgentRole,
    CritiqueResponse,
    ExecutionReport,
    FlightClass,
    FlightOption,
    FlightSearchRequest,
    FlightSearchResponse,
    InternalFlightOption,
    MessageEnvelope,
    Priority,
    SimulationOutcome,
    SimulationRequest,
    SimulationResponse,
)


class PlannerAgent(AgentBase):
    """Genera planes de viaje y orquesta simulator/critic/executor."""

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AgentRole.PLANNER, bus)
        self.register_handler("flight.search_request", self._on_search_request)
        self.register_handler("plan.simulate_response", self._on_simulation)
        self.register_handler("plan.critique_response", self._on_critique)
        self.pending_plans: Dict[UUID, Dict[str, Any]] = {}

    def _on_search_request(self, envelope: MessageEnvelope) -> None:
        request: FlightSearchRequest = envelope.payload
        options = self._search_flights(request)
        response = FlightSearchResponse(
            options=options,
            total_found=len(options),
            search_duration_ms=42,
        )
        self.send(
            target=envelope.source_agent,
            message_type="flight.search_response",
            payload=response,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.message_id,
        )

        # Inicia el flujo de simulación
        correlation_id = envelope.correlation_id
        sim_request = SimulationRequest(
            plan_id=UUID(int=random.getrandbits(128)),
            flight_options=options,
            user_preferences={"priority": "price", "max_stops": 1},
            num_scenarios=min(500, 100),
        )
        self.pending_plans[sim_request.plan_id] = {
            "request": request,
            "options": options,
            "status": "simulating",
            "correlation_id": correlation_id,
        }
        self.send(
            target=AgentRole.SIMULATOR,
            message_type="plan.simulate_request",
            payload=sim_request,
            correlation_id=correlation_id,
            priority=Priority.HIGH,
        )

    def _on_simulation(self, envelope: MessageEnvelope) -> None:
        sim_response: SimulationResponse = envelope.payload
        self.send(
            target=AgentRole.CRITIC,
            message_type="plan.simulate_response",
            payload=sim_response,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.message_id,
        )

    def _on_critique(self, envelope: MessageEnvelope) -> None:
        critique: CritiqueResponse = envelope.payload
        if critique.verdict == "approved":
            self.send(
                target=AgentRole.EXECUTOR,
                message_type="plan.execution_report",
                payload=critique,
                correlation_id=envelope.correlation_id,
                priority=Priority.HIGH,
            )
        elif critique.verdict == "needs_revision":
            self._revise_plan(envelope.correlation_id, critique)

    def _search_flights(self, request: FlightSearchRequest) -> List[FlightOption]:
        """Búsqueda simulada de vuelos."""
        base_price = float(request.max_price_usd) * 0.75
        return [
            FlightOption(
                flight_number=f"{request.origin}101",
                airline="MockAir",
                origin=request.origin,
                destination=request.destination,
                departure_time=request.departure_date,
                arrival_time=request.departure_date.replace(
                    hour=(request.departure_date.hour + 5) % 24
                ),
                duration_minutes=300,
                price_usd=Decimal(f"{base_price:.2f}"),
                cabin_class=request.cabin_class,
                seats_available=23,
                co2_kg=180.5,
                reliability_score=0.92,
            ),
            FlightOption(
                flight_number=f"{request.origin}202",
                airline="SkyLines",
                origin=request.origin,
                destination=request.destination,
                departure_time=request.departure_date,
                arrival_time=request.departure_date.replace(
                    hour=(request.departure_date.hour + 6) % 24
                ),
                duration_minutes=360,
                price_usd=Decimal(f"{base_price * 0.9:.2f}"),
                cabin_class=request.cabin_class,
                seats_available=8,
                co2_kg=210.0,
                reliability_score=0.85,
            ),
        ]

    def _revise_plan(self, correlation_id: UUID, critique: CritiqueResponse) -> None:
        plan = self.pending_plans.get(correlation_id)
        if plan is None:
            return
        plan["status"] = "revising"
        plan["critique"] = critique


class SimulatorAgent(AgentBase):
    """Simula escenarios usando opciones de vuelo."""

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AgentRole.SIMULATOR, bus)
        self.register_handler("plan.simulate_request", self._on_simulate)

    def _on_simulate(self, envelope: MessageEnvelope) -> None:
        request: SimulationRequest = envelope.payload
        internal_options = tuple(
            InternalFlightOption.from_pydantic(opt) for opt in request.flight_options
        )
        scenarios = self._run_monte_carlo(
            internal_options, request.num_scenarios, request.simulation_horizon_hours
        )
        costs = [float(s.total_cost_usd) for s in scenarios]
        expected_cost = sum(costs) / len(costs) if costs else 0.0
        p95_cost = sorted(costs)[int(len(costs) * 0.95)] if costs else 0.0
        miss_rate = (
            sum(1 for s in scenarios if s.connection_missed) / len(scenarios)
            if scenarios
            else 0.0
        )

        if miss_rate < 0.1 and expected_cost < 600:
            recommendation = "approve"
        elif miss_rate < 0.3:
            recommendation = "revise"
        else:
            recommendation = "reject"

        response = SimulationResponse(
            plan_id=request.plan_id,
            scenarios=scenarios,
            expected_cost_usd=Decimal(f"{expected_cost:.2f}"),
            p95_cost_usd=Decimal(f"{p95_cost:.2f}"),
            risk_score=miss_rate,
            recommendation=recommendation,
        )
        self.send(
            target=AgentRole.PLANNER,
            message_type="plan.simulate_response",
            payload=response,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.message_id,
        )

    def _run_monte_carlo(
        self, options: tuple, n_scenarios: int, _horizon: int
    ) -> List[SimulationOutcome]:
        scenarios: List[SimulationOutcome] = []
        for i in range(n_scenarios):
            base_cost = sum(opt.price_cents for opt in options) / 100
            noise = random.gauss(0, 50)
            scenarios.append(
                SimulationOutcome(
                    scenario_id=i,
                    total_cost_usd=Decimal(f"{max(0, base_cost + noise):.2f}"),
                    total_travel_time_min=sum(o.duration_min for o in options),
                    connection_missed=random.random() < 0.08,
                    disruption_probability=random.uniform(0.05, 0.25),
                    user_satisfaction_score=random.uniform(6.5, 9.5),
                )
            )
        return scenarios


class CriticAgent(AgentBase):
    """Evalúa críticamente los planes simulados."""

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AgentRole.CRITIC, bus)
        self.register_handler("plan.simulate_response", self._on_sim_response)

    def _on_sim_response(self, envelope: MessageEnvelope) -> None:
        sim: SimulationResponse = envelope.payload
        strengths: List[str] = []
        weaknesses: List[str] = []

        if sim.risk_score < 0.15:
            strengths.append(f"Riesgo bajo: {sim.risk_score:.1%}")
        else:
            weaknesses.append(f"Riesgo alto: {sim.risk_score:.1%}")

        if float(sim.expected_cost_usd) < 500:
            strengths.append(f"Costo competitivo: ${sim.expected_cost_usd}")
        else:
            weaknesses.append(f"Costo elevado: ${sim.expected_cost_usd}")

        if not weaknesses:
            verdict = "approved"
            confidence = 0.95
        elif len(weaknesses) == 1:
            verdict = "needs_revision"
            confidence = 0.6
        else:
            verdict = "rejected"
            confidence = 0.3

        critique = CritiqueResponse(
            plan_id=sim.plan_id,
            verdict=verdict,
            strengths=strengths,
            weaknesses=weaknesses,
            suggested_alternatives=[],
            confidence=confidence,
        )
        self.send(
            target=AgentRole.PLANNER,
            message_type="plan.critique_response",
            payload=critique,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.message_id,
        )


class ExecutorAgent(AgentBase):
    """Ejecuta reservas y genera reportes de ejecución."""

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AgentRole.EXECUTOR, bus)
        self.register_handler("plan.execution_report", self._on_execute)

    def _on_execute(self, envelope: MessageEnvelope) -> None:
        critique: CritiqueResponse = envelope.payload
        report = ExecutionReport(
            plan_id=critique.plan_id,
            status="success" if critique.verdict == "approved" else "failed",
            bookings_confirmed=[f"BK-{uuid4().hex[:6]}"],
            bookings_failed=[],
            total_charged_usd=Decimal("450.00"),
            confirmation_codes=["CONF-001"],
        )
        self.send(
            target=AgentRole.PLANNER,
            message_type="plan.execution_report",
            payload=report,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.message_id,
        )


class UserProxyAgent(AgentBase):
    """Representa al usuario para iniciar flujos."""

    def __init__(self, bus: MessageBus) -> None:
        super().__init__(AgentRole.USER_PROXY, bus)
        self.responses: List[MessageEnvelope] = []
        self.register_handler("flight.search_response", self._store)
        self.register_handler("plan.execution_report", self._store)
        self.register_handler("system.error", self._store)

    def _store(self, envelope: MessageEnvelope) -> None:
        self.responses.append(envelope)

    def request_plan(self, request: FlightSearchRequest) -> MessageEnvelope:
        return self.send(
            target=AgentRole.PLANNER,
            message_type="flight.search_request",
            payload=request,
        )
