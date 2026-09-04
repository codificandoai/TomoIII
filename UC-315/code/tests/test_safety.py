"""Tests del Safety Supervisor UC-315."""
from __future__ import annotations

from domain_policy import PolicyRegistry
from domain_skills import build_default_registry
from safety_supervisor_315 import SafetySupervisor315


def test_market_execution_requires_trader_role():
    policy_reg = PolicyRegistry()
    safety = SafetySupervisor315(policy_reg)
    skill = build_default_registry().get("MarketExecutionSkill")
    decision = safety.check(skill, {}, user_roles=["analyst"], domain_state={"risk_approved": True, "circuit_breaker_open": True})
    assert not decision["allowed"]
    assert any("rol requerido" in issue for issue in decision["issues"])


def test_payment_requires_approval():
    safety = SafetySupervisor315(PolicyRegistry())
    skill = build_default_registry().get("PaymentSkill")
    decision = safety.check(skill, {}, user_roles=["payment_processor", "payment.charge"], domain_state={"availability_confirmed": True, "user_consent": True})
    assert decision["allowed"]
    assert decision["requires_approval"]


def test_unknown_domain_uses_default_policy():
    safety = SafetySupervisor315(PolicyRegistry())
    # default domain policy allows everything unless restricted
    skill = build_default_registry().get("NotificationSkill")
    decision = safety.check(skill, {}, user_roles=["anonymous"], domain_state={})
    assert decision["allowed"]
