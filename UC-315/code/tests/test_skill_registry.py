"""Tests del SkillRegistry y contratos UC-315."""
from __future__ import annotations

from domain_skills import build_default_registry
from skill_contracts import ActionClass, RiskLevel


def test_domains_separated():
    registry = build_default_registry()
    domains = registry.domains()
    assert "trading" in domains
    assert "reservations" in domains


def test_skills_have_contracts():
    registry = build_default_registry()
    for skill_dict in registry.list_skills():
        assert skill_dict["name"]
        assert skill_dict["domain"]
        assert skill_dict["action_class"]
        assert skill_dict["risk_level"]


def test_critical_skills_have_preconditions():
    registry = build_default_registry()
    exec_skill = registry.get("MarketExecutionSkill")
    assert exec_skill.preconditions


def test_high_risk_skills_require_permissions():
    registry = build_default_registry()
    payment = registry.get("PaymentSkill")
    assert payment is not None
    assert payment.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert "payment.charge" in payment.permissions


def test_trading_execution_is_critical():
    registry = build_default_registry()
    exec_skill = registry.get("MarketExecutionSkill")
    assert exec_skill is not None
    assert exec_skill.risk_level == RiskLevel.CRITICAL
    assert exec_skill.action_class == ActionClass.EXECUTE
