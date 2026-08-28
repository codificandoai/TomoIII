"""Tests del módulo de seguridad."""
from __future__ import annotations

from models import AgentProfile, AgentRole
from security import SecurityManager


def _profile(name: str = "test", role: AgentRole = AgentRole.coder, sa: str = "test-sa") -> AgentProfile:
    return AgentProfile(name=name, role=role, skill=0.8, cost=1.0, latency_ms=200, service_account=sa)


def test_generate_rbac() -> None:
    sm = SecurityManager()
    profile = _profile(role=AgentRole.supervisor)
    rbac = sm.generate_rbac(profile)
    assert rbac.agent_name == "test"
    assert rbac.role_name == "test-role"
    assert len(rbac.rules) >= 2


def test_generate_network_policy() -> None:
    sm = SecurityManager()
    profile = _profile()
    np = sm.generate_network_policy(profile, ["researcher", "coder"])
    assert np.agent_name == "test"
    assert len(np.rules) == 2
    assert np.rules[0].direction == "ingress"
    assert np.rules[1].direction == "egress"


def test_generate_service_account() -> None:
    sm = SecurityManager()
    profile = _profile()
    sa = sm.generate_service_account(profile)
    assert sa.name == "test-sa"
    assert sa.automount_token is False


def test_generate_security_context() -> None:
    sm = SecurityManager()
    profile = _profile()
    ctx = sm.generate_security_context(profile)
    assert ctx.run_as_non_root is True
    assert ctx.read_only_root_fs is True
    assert "ALL" in ctx.drop_capabilities
    assert ctx.allow_privilege_escalation is False


def test_validate_agent_with_service_account() -> None:
    sm = SecurityManager()
    profile = _profile(sa="my-sa")
    violations = sm.validate_agent_security(profile)
    assert "no service account configured" not in " ".join(violations)


def test_validate_agent_without_service_account() -> None:
    sm = SecurityManager()
    profile = AgentProfile(name="bad", role=AgentRole.coder, skill=0.8, cost=1.0, latency_ms=200, service_account="")
    violations = sm.validate_agent_security(profile)
    assert any("no service account" in v for v in violations)


def test_audit_trail_recorded() -> None:
    sm = SecurityManager()
    profile = _profile()
    sm.generate_rbac(profile)
    sm.generate_network_policy(profile, [])
    assert len(sm.audit_trail) >= 2
