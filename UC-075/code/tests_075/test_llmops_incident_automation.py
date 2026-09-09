"""Tests para llmops_incident_automation.py — automatización de incidentes LLMOps."""
from __future__ import annotations

import pytest

from llmops_incident_automation import (
    DrillReport,
    DrillSimulator,
    EscalationReason,
    HumanEscalationQueue,
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    LLMOpsIncidentManager,
    PlaybookRegistry,
    PolicyLearningEngine,
)
from risk_management_framework import RiskRegister


class TestIncidentClassifierAndTriage:
    def test_auto_resolve_high_confidence_common_incident(self):
        mgr = LLMOpsIncidentManager()
        inc = mgr.detect(
            category=IncidentCategory.DATA_DRIFT,
            title="data drift detectado",
            description="desviación leve",
            source="monitor",
            impact_score=0.4,
            confidence=0.9,
        )
        assert inc.status == IncidentStatus.AUTO_RESOLVED
        assert inc.actions_taken

    def test_escalate_low_confidence(self):
        mgr = LLMOpsIncidentManager()
        inc = mgr.detect(
            category=IncidentCategory.DATA_DRIFT,
            title="drift ambiguo",
            description="puede ser ruido",
            source="monitor",
            impact_score=0.5,
            confidence=0.3,
        )
        assert inc.status == IncidentStatus.ESCALATED
        assert EscalationReason.LOW_CONFIDENCE.value in inc.escalation_reasons

    def test_escalate_regulatory_alert(self):
        mgr = LLMOpsIncidentManager()
        inc = mgr.detect(
            category=IncidentCategory.REGULATORY_ALERT,
            title="posible brecha GDPR",
            description="datos personales expuestos",
            source="dpo",
            impact_score=0.6,
            confidence=0.8,
        )
        assert inc.status == IncidentStatus.ESCALATED
        assert EscalationReason.REGULATORY_CONTEXT.value in inc.escalation_reasons

    def test_escalate_unknown_novel_pattern(self):
        mgr = LLMOpsIncidentManager()
        inc = mgr.detect(
            category=IncidentCategory.UNKNOWN,
            title="comportamiento nunca visto",
            description="patrón desconocido",
            source="agent",
            impact_score=0.3,
        )
        assert inc.status == IncidentStatus.ESCALATED

    def test_escalate_high_severity_above_playbook_limit(self):
        mgr = LLMOpsIncidentManager()
        inc = mgr.detect(
            category=IncidentCategory.DATA_DRIFT,
            title="drift masivo",
            description="cambio de distribución total",
            source="monitor",
            impact_score=0.95,
            confidence=0.9,
        )
        assert inc.status == IncidentStatus.ESCALATED
        assert EscalationReason.HIGH_SEVERITY.value in inc.escalation_reasons


class ToolAbuseTests:
    def test_tool_abuse_escalates_and_risk_registered(self):
        risk_reg = RiskRegister()
        mgr = LLMOpsIncidentManager(risk_register=risk_reg)
        inc = mgr.detect(
            category=IncidentCategory.TOOL_ABUSE,
            title="agent deleted bucket",
            description="agent used aws delete_bucket",
            source="agent",
            impact_score=0.9,
            affected_agents=["agent-1"],
        )
        assert inc.status == IncidentStatus.ESCALATED
        assert EscalationReason.DESTRUCTIVE_ACTION.value in inc.escalation_reasons
        assert len(risk_reg.list()) >= 1


class TestHumanQueue:
    def test_assign_and_resolve(self):
        mgr = LLMOpsIncidentManager()
        inc = mgr.detect(
            category=IncidentCategory.UNKNOWN,
            title="ambiguo",
            description="unclear pattern",
            source="monitor",
            impact_score=0.4,
            confidence=0.3,
        )
        assert inc.status == IncidentStatus.ESCALATED
        mgr.assign_human(inc.incident_id, "analyst@utron.ai")
        mgr.resolve_human(inc.incident_id, "Revisado: falso positivo", policy_learnings=["refinar detector"])
        resolved = mgr.get(inc.incident_id)
        assert resolved.status == IncidentStatus.HUMAN_RESOLVED
        assert resolved.assigned_human == "analyst@utron.ai"


class TestDrillSimulator:
    def test_dry_run_drill(self):
        mgr = LLMOpsIncidentManager()
        report = mgr.run_drill("prompt-injection-weekly", [
            {"category": IncidentCategory.PROMPT_INJECTION, "title": "t1", "description": "d", "impact_score": 0.6},
            {"category": IncidentCategory.UNKNOWN, "title": "t2", "description": "unclear", "impact_score": 0.4},
        ])
        assert report.incidents_injected == 2
        assert report.auto_resolved + report.escalated == 2
        assert "Dry-run" in report.findings[0]

    def test_drill_retrievable(self):
        mgr = LLMOpsIncidentManager()
        report = mgr.run_drill("x", [])
        assert mgr.drills.get(report.drill_id) is not None


class TestPolicyLearningEngine:
    def test_prompt_injection_suggestion(self):
        engine = PolicyLearningEngine()
        inc = Incident(
            category=IncidentCategory.PROMPT_INJECTION,
            title="injection",
            description="bypass",
            confidence=0.6,
            status=IncidentStatus.AUTO_RESOLVED,
        )
        suggestions = engine.analyze([inc])
        assert any("guardrails" in s["target"] for s in suggestions)

    def test_unknown_creates_playbook_suggestion(self):
        engine = PolicyLearningEngine()
        inc = Incident(category=IncidentCategory.UNKNOWN, title="new", description="novel", status=IncidentStatus.HUMAN_RESOLVED)
        suggestions = engine.analyze([inc])
        assert any(s["target"] == "playbook" for s in suggestions)


class TestPlaybookRegistry:
    def test_default_playbooks_cover_categories(self):
        reg = PlaybookRegistry()
        pb = reg.get(IncidentCategory.TOOL_ABUSE)
        assert "revoke_credentials" in pb["auto_actions"]
        assert "disable_tool" in pb["auto_actions"]

    def test_executor_registry(self):
        reg = PlaybookRegistry()
        inc = Incident()
        ok = reg.execute("revoke_credentials", inc, LLMOpsIncidentManager())
        assert ok


class TestObservabilityIntegration:
    def test_incident_metrics_recorded(self):
        class FakeObs:
            def __init__(self):
                self.events = []
            def record_incident(self, **kwargs):
                self.events.append(("detected", kwargs))
            def record_incident_escalation(self, **kwargs):
                self.events.append(("escalated", kwargs))

        obs = FakeObs()
        mgr = LLMOpsIncidentManager(observability=obs)
        mgr.detect(category=IncidentCategory.UNKNOWN, title="x", description="y", source="z", confidence=0.3)
        assert any(e[0] == "detected" for e in obs.events)
        assert any(e[0] == "escalated" for e in obs.events)


class TestOrchestratorIntegration:
    def test_orchestrator_reports_incident(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        result = orch.report_incident(
            category="tool_abuse",
            title="bucket deletion",
            description="agent deleted production bucket",
            source="agent",
            impact_score=0.9,
            affected_agents=["agent-1"],
        )
        assert result["status"] == "escalated"
        assert orch.incident_summary()["escalated"] == 1

    def test_orchestrator_incident_drill(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        report = orch.run_incident_drill("weekly", [
            {"category": "prompt_injection", "title": "t", "description": "d", "impact_score": 0.5},
        ])
        assert report["incidents_injected"] == 1

    def test_orchestrator_learnings(self):
        from continuous_training_orchestrator import ContinuousTrainingOrchestrator
        orch = ContinuousTrainingOrchestrator()
        orch.report_incident(
            category="prompt_injection",
            title="injection",
            description="bypass",
            source="agent",
            impact_score=0.5,
            confidence=0.6,
        )
        learnings = orch.incident_policy_learnings()
        assert any(l["target"] == "guardrails" for l in learnings)
