"""Tests para risk_management_framework.py — marco de gestión de riesgos AGI/MLOps."""
from __future__ import annotations

import pytest

from risk_management_framework import (
    ProactiveRiskPlan,
    Risk,
    RiskCategory,
    RiskGate,
    RiskPolicy,
    RiskRegister,
    RiskScorer,
    RiskSeverity,
    RiskStatus,
    RiskTrend,
    RunbookCatalog,
    risk_from_agent_tool_abuse,
    risk_from_drift,
    risk_from_gate_failure,
    risk_from_online_quarantine,
    risk_from_supply_chain,
)


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

class TestRiskScorer:
    def test_severity_thresholds(self):
        assert RiskScorer.severity(0.90) == RiskSeverity.CRITICAL
        assert RiskScorer.severity(0.75) == RiskSeverity.HIGH
        assert RiskScorer.severity(0.50) == RiskSeverity.MEDIUM
        assert RiskScorer.severity(0.20) == RiskSeverity.LOW
        assert RiskScorer.severity(0.05) == RiskSeverity.NEGLIGIBLE

    def test_risk_recompute(self):
        risk = Risk(probability=0.8, impact=0.8, exposure=1.0, control_effectiveness=0.2)
        assert risk.inherent_risk == pytest.approx(0.64)
        assert risk.residual_risk == pytest.approx(0.44)
        assert risk.severity == RiskSeverity.MEDIUM


# ---------------------------------------------------------------------------
# Risk register
# ---------------------------------------------------------------------------

class TestRiskRegister:
    def test_register_and_get(self):
        reg = RiskRegister()
        risk = Risk(category=RiskCategory.DATA, subcategory="pii_leak", description="PII leak")
        reg.register(risk)
        assert reg.get(risk.risk_id) is risk

    def test_update_mitigation_reduces_residual(self):
        reg = RiskRegister()
        risk = Risk(probability=0.8, impact=0.8, control_effectiveness=0.0)
        reg.register(risk)
        before = risk.residual_risk
        reg.update(risk.risk_id, mitigations=["mask_pii"], control_effectiveness=0.5)
        assert risk.residual_risk < before
        assert any("mask_pii" in m for m in risk.mitigations)

    def test_summary_counts_severity(self):
        reg = RiskRegister()
        reg.register(Risk(probability=0.9, impact=0.9, control_effectiveness=0.0))
        reg.register(Risk(probability=0.2, impact=0.2, control_effectiveness=0.0))
        summary = reg.summary()
        assert summary["open_high_critical"] == 1
        assert summary["classification"]["by_severity"]["critical"] == 1

    def test_list_filters(self):
        reg = RiskRegister()
        reg.register(Risk(category=RiskCategory.DATA, subcategory="drift", description="d"))
        reg.register(Risk(category=RiskCategory.MODEL, subcategory="bias", description="b"))
        assert len(reg.list(category=RiskCategory.DATA)) == 1


# ---------------------------------------------------------------------------
# Proactive risk plan
# ---------------------------------------------------------------------------

class TestProactiveRiskPlan:
    def test_recommendations(self):
        policy = RiskPolicy()
        plan = ProactiveRiskPlan(policy)
        low = Risk(probability=0.1, impact=0.1, control_effectiveness=0.0)
        high = Risk(probability=0.85, impact=0.85, control_effectiveness=0.0)
        critical = Risk(probability=1.0, impact=1.0, control_effectiveness=0.0)
        assert plan.recommend_action(low) == "monitor"
        assert plan.recommend_action(high) == "requires_hitl_review"
        assert plan.recommend_action(critical) == "freeze_and_escalate"

    def test_next_steps(self):
        reg = RiskRegister()
        reg.register(Risk(category=RiskCategory.AGENT, subcategory="tool_abuse", probability=0.9, impact=0.9))
        plan = ProactiveRiskPlan()
        actions = plan.next_steps(reg)
        assert any(a["recommendation"] == "freeze_and_escalate" for a in actions)


# ---------------------------------------------------------------------------
# Risk gate
# ---------------------------------------------------------------------------

class TestRiskGate:
    def test_pass_when_empty(self):
        gate = RiskGate()
        result = gate.evaluate()
        assert result.passed
        assert not result.requires_hitl

    def test_block_high_residual(self):
        reg = RiskRegister()
        reg.register(Risk(category=RiskCategory.DATA, subcategory="poisoning", probability=0.9, impact=0.9))
        gate = RiskGate(register=reg, policy=RiskPolicy(max_residual_for_auto_promote=0.30))
        result = gate.evaluate()
        assert not result.passed
        assert result.requires_hitl or result.requires_freeze

    def test_aggregate_residual_blocks(self):
        reg = RiskRegister()
        for _ in range(5):
            reg.register(Risk(probability=0.5, impact=0.5, control_effectiveness=0.0))
        policy = RiskPolicy(max_residual_for_auto_promote=0.30, max_aggregate_residual=0.5)
        gate = RiskGate(register=reg, policy=policy)
        result = gate.evaluate()
        assert not result.passed


# ---------------------------------------------------------------------------
# Runbooks
# ---------------------------------------------------------------------------

class TestRunbookCatalog:
    def test_agent_runbook_has_disable_tool(self):
        cat = RunbookCatalog()
        book = cat.get(RiskCategory.AGENT)
        assert any("tool" in step.lower() for step in book["steps"])
        assert "disable_tool" in book["auto_controls"]

    def test_all_categories_present(self):
        cat = RunbookCatalog()
        assert len(cat.all()) == 8


# ---------------------------------------------------------------------------
# Event-to-risk helpers
# ---------------------------------------------------------------------------

class TestRiskHelpers:
    def test_drift_risk(self):
        r = risk_from_drift(0.85, run_id="run-1", artifact_ids=["art-1"])
        assert r.category == RiskCategory.DATA
        assert r.trigger_event == "drift_exceeded"
        assert "run-1" in r.linked_run_ids

    def test_agent_tool_abuse_risk(self):
        r = risk_from_agent_tool_abuse("agent-1", "aws", "deleted bucket")
        assert r.category == RiskCategory.AGENT
        assert r.requires_hitl

    def test_supply_chain_risk(self):
        r = risk_from_supply_chain("transformers", "malicious adapter", artifact_ids=["art-1"])
        assert r.category == RiskCategory.INFRASTRUCTURE
        assert r.subcategory == "supply_chain_compromise"

    def test_gate_failure_risk(self):
        r = risk_from_gate_failure(
            RiskCategory.REGULATORY,
            "explainability_failure",
            "No SHAP report",
            "explainability_gate",
            "missing explanation",
            run_id="run-2",
        )
        assert r.category == RiskCategory.REGULATORY
        assert r.trigger_event == "explainability_gate_failure"

    def test_online_quarantine_risk(self):
        r = risk_from_online_quarantine("learner-1", "integrity_failure", "mb-1")
        assert r.category == RiskCategory.DATA
        assert "learner-1" in r.linked_agent_ids


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

class TestRiskStatus:
    def test_trend_default_stable(self):
        r = Risk()
        assert r.trend == RiskTrend.STABLE

    def test_status_can_be_updated(self):
        reg = RiskRegister()
        r = Risk(status=RiskStatus.OPEN)
        reg.register(r)
        reg.update(r.risk_id, status=RiskStatus.MITIGATED)
        assert r.status == RiskStatus.MITIGATED
