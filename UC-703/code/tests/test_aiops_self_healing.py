"""Tests para AIOps Self-Healing Platform."""
from __future__ import annotations

import pytest

from aiops_self_healing.aiops_controller import AIOpsController
from aiops_self_healing.communication_and_audit import AuditLedger, CommunicationEngine
from aiops_self_healing.diagnostic_engine import DiagnosticEngine
from aiops_self_healing.event_correlator import EventCorrelator
from aiops_self_healing.event_ingestion_orchestrator import EventIngestionOrchestrator
from aiops_self_healing.models_aiops import AIOpsState, RemediationType
from aiops_self_healing.remediation_orchestrator import RemediationOrchestrator
from aiops_self_healing.risk_policy_engine import RiskPolicyEngine, SeverityClassifier


class TestEventIngestion:
    def test_ingest_and_normalize(self):
        orch = EventIngestionOrchestrator()
        alert = orch.ingest_and_normalize("prometheus", {
            "metric": "latency_p95",
            "value": 2.5,
            "threshold": 1.0,
            "severity": "high",
            "category": "latency",
            "resource": "llm-api",
        })
        assert alert.metric == "latency_p95"
        assert orch.list_events()


class TestEventCorrelator:
    def test_correlate_by_resource(self):
        orch = EventIngestionOrchestrator()
        orch.ingest_and_normalize("prometheus", {
            "metric": "latency_p95", "value": 2, "threshold": 1,
            "severity": "high", "category": "latency", "resource": "llm-api",
        })
        orch.ingest_and_normalize("loki", {
            "metric": "error_rate", "value": 10, "threshold": 5,
            "severity": "high", "category": "availability", "resource": "llm-api",
        })
        corr = EventCorrelator()
        groups = corr.correlate(orch.list_alerts())
        assert len(groups) == 2


class TestDiagnosticEngine:
    def test_security_diagnosis(self):
        from aiops_self_healing.models_aiops import CorrelationGroup, NormalizedAlert
        group = CorrelationGroup(
            group_id="g1",
            alert_ids=["a1"],
            category="security",
            resource="llm-api",
            severity="critical",
        )
        alerts = [NormalizedAlert(alert_id="a1", metric="prompt_injection", value=1, threshold=0, category="security")]
        diag = DiagnosticEngine().diagnose(group, alerts)
        assert "prompt injection" in diag.root_cause_hypothesis.lower()
        assert RemediationType.CIRCUIT_BREAKER in diag.proposed_remediations


class TestRiskPolicyEngine:
    def test_rollback_requires_approval(self):
        p = RiskPolicyEngine()
        assert p.requires_approval(RemediationType.ROLLBACK_PROMPT.value, "quality", "high")
        assert not p.requires_approval(RemediationType.AUTOSCALE.value, "availability", "high")


class TestRemediationOrchestrator:
    def test_autoscale(self):
        from aiops_self_healing.models_aiops import CorrelationGroup
        group = CorrelationGroup(category="availability", resource="llm-api", severity="high")
        rem = RemediationOrchestrator()
        action = rem.execute(group, RemediationType.AUTOSCALE, "llm-api", {"replicas": 3})
        assert action
        assert action.status == "succeeded"
        assert action.result["replicas"] == 3

    def test_high_impact_pending_approval(self):
        from aiops_self_healing.models_aiops import CorrelationGroup
        group = CorrelationGroup(category="quality", resource="llm-api", severity="high")
        rem = RemediationOrchestrator()
        action = rem.execute(group, RemediationType.ROLLBACK_MODEL, "model-v2")
        assert action.status == "pending_approval"


class TestAuditAndComms:
    def test_communication_render(self):
        c = CommunicationEngine()
        msg = c.render("incident_opened", {"group_id": "g1", "summary": "test", "severity": "high", "owner": "sre"})
        assert "g1" in msg

    def test_audit_hash(self):
        a = AuditLedger()
        rec = a.record(
            group_id="g1",
            state=AIOpsState.RESOLVED.value,
            decision="auto-remediation",
            responsible="aiops-controller",
            raw_event_ids=["e1"],
            alert_ids=["a1"],
            diagnosis_id="d1",
            remediation_ids=["r1"],
            outcome="resolved",
        )
        assert rec.immutable_hash


class TestAIOpsController:
    def test_full_pipeline(self):
        ctrl = AIOpsController()
        reports = ctrl.run_full_pipeline([
            {
                "source": "prometheus",
                "payload": {
                    "metric": "latency_p95",
                    "value": 2.5,
                    "threshold": 1.0,
                    "severity": "high",
                    "category": "latency",
                    "resource": "llm-api",
                },
            },
        ])
        assert reports
        assert reports[0].state in {AIOpsState.RESOLVED.value, AIOpsState.ESCALATED.value}
        assert reports[0].audit_record

    def test_security_critical_escalates(self):
        ctrl = AIOpsController()
        reports = ctrl.run_full_pipeline([
            {
                "source": "security",
                "payload": {
                    "metric": "prompt_injection",
                    "value": 1,
                    "threshold": 0,
                    "severity": "critical",
                    "category": "security",
                    "resource": "chat-api",
                },
            },
        ])
        assert reports[0].state == AIOpsState.ESCALATED.value


class TestAIOpsAPI:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._aiops_controller = AIOpsController()
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_pipeline_endpoint(self, client):
        resp = client.post("/api/v1/aiops/pipeline", json={
            "events": [
                {
                    "source": "prometheus",
                    "payload": {
                        "metric": "latency_p95",
                        "value": 2.5,
                        "threshold": 1.0,
                        "severity": "high",
                        "category": "latency",
                        "resource": "llm-api",
                    },
                },
            ],
        })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data
        assert data[0]["state"]

    def test_policy_endpoint(self, client):
        resp = client.post("/api/v1/aiops/policies", json={
            "action_type": "autoscale",
            "category": "availability",
            "severity": "high",
            "requires_approval": False,
        })
        assert resp.status_code == 201
        assert resp.get_json()["data"]["requires_approval"] is False

    def test_dashboard(self, client):
        resp = client.get("/api/v1/aiops/dashboard")
        assert resp.status_code == 200
        assert "events" in resp.get_json()["data"]
