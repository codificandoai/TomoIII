"""Tests del orquestador general UC-315."""
from __future__ import annotations

from domain_skills import build_default_registry
from general_orchestrator import GeneralOrchestrator
from safety_supervisor_315 import SafetySupervisor315


def _orch():
    return GeneralOrchestrator(skill_registry=build_default_registry())


def test_build_flight_plan_uses_reservation_skills():
    orch = _orch()
    plan = orch.build_plan("Reservar un vuelo de Madrid a Barcelona", "reservations")
    assert plan.domain == "reservations"
    assert len(plan.steps) > 0
    skill_names = [s.skill_name for s in plan.steps]
    assert "FlightBookingSkill" in skill_names


def test_build_rail_plan_uses_rail_skill():
    orch = _orch()
    plan = orch.build_plan("Reservar un tren de Madrid a Barcelona", "reservations")
    assert plan.domain == "reservations"
    skill_names = [s.skill_name for s in plan.steps]
    assert "RailBookingSkill" in skill_names


def test_trading_plan_has_risk_before_execution():
    orch = _orch()
    plan = orch.build_plan("Comprar AAPL", "trading")
    assert plan.domain == "trading"
    names = [s.skill_name for s in plan.steps]
    assert "MarketDataSkill" in names
    assert "FinancialRiskSkill" in names
    assert "MarketExecutionSkill" in names
    assert names.index("FinancialRiskSkill") < names.index("MarketExecutionSkill")


def test_payment_blocked_without_permission():
    orch = _orch()
    plan = orch.build_plan("Reservar vuelo Madrid Barcelona", "reservations")
    executed = orch.validate_and_execute(
        plan,
        user_roles=["anonymous"],
        domain_state={"availability_confirmed": True, "user_consent": True},
        auto_approve=False,
    )
    payment_steps = [s for s in executed.steps if s.skill_name == "PaymentSkill"]
    assert payment_steps
    assert payment_steps[0].status in ("awaiting_approval", "blocked")


def test_payment_executed_with_roles_and_state():
    orch = _orch()
    plan = orch.build_plan("Reservar vuelo Madrid Barcelona", "reservations")
    executed = orch.validate_and_execute(
        plan,
        user_roles=["payment_processor", "payment.charge"],
        domain_state={"availability_confirmed": True, "user_consent": True},
        auto_approve=True,
    )
    payment_steps = [s for s in executed.steps if s.skill_name == "PaymentSkill"]
    assert payment_steps
    assert payment_steps[0].status == "executed"


def test_memory_isolated_per_domain():
    orch = _orch()
    mem_trading = orch._get_memory("trading")
    mem_reservations = orch._get_memory("reservations")
    assert "trading" in mem_trading.config.structured.db_path
    assert "reservations" in mem_reservations.config.structured.db_path
