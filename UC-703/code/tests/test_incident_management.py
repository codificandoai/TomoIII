"""Tests para Incident Management LLMOps."""
from __future__ import annotations

import pytest

from incident_management.classifier import IncidentClassifier
from incident_management.escalation_manager import EscalationManager
from incident_management.incident_management_controller import IncidentManagementController
from incident_management.models_incident import Incident, OnCallPerson
from incident_management.runbook_engine import RunbookEngine
from incident_management.slo_engine import SLOEngine


class TestIncidentClassifier:
    def test_critical_security(self):
        c = IncidentClassifier()
        inc = Incident(
            category="security",
            urgency="immediate",
            affected_users=15000,
            regulatory_criticality="critical",
            tags=["prompt_injection"],
        )
        assert c.classify(inc) == "critical"

    def test_medium_quality(self):
        c = IncidentClassifier()
        inc = Incident(
            category="quality",
            urgency="low",
            affected_users=10,
            regulatory_criticality="none",
        )
        assert c.classify(inc) == "medium"


class TestSLOEngine:
    def test_error_budget(self):
        e = SLOEngine()
        e.register_sli("availability", "Availability", "uptime", "ratio")
        slo = e.define_slo("availability", 0.99, 3600)
        assert slo
        assert slo.error_budget() == 0.01
        for _ in range(100):
            e.record_sample(slo.slo_id, True)
        for _ in range(2):
            e.record_sample(slo.slo_id, False)
        budget = e.compute_error_budget(slo.slo_id)
        assert budget
        assert budget.consumed == 2


class TestEscalationManager:
    def test_assign_incident_commander(self):
        mgr = EscalationManager()
        mgr.add_oncall(OnCallPerson(name="alice", team="SRE/DevOps"))
        inc = Incident(category="availability", assigned_team="SRE/DevOps")
        assert mgr.assign_incident_commander(inc) == "alice"

    def test_containment_actions(self):
        mgr = EscalationManager()
        inc = Incident(category="security")
        applied = mgr.apply_containment(inc, ["disable_tool", "force_hitl"])
        assert len(applied) == 2
        assert inc.status == "contained"


class TestRunbookEngine:
    def test_security_runbook(self):
        eng = RunbookEngine()
        inc = Incident(category="security")
        result = eng.execute(inc)
        assert result["status"] == "executed"
        assert result["runbook_id"] == "rb-security"


class TestIncidentController:
    def test_full_lifecycle(self):
        ctrl = IncidentManagementController()
        ctrl.add_oncall("alice", "SRE/DevOps")
        ctrl.add_oncall("bob", "Security")

        inc = ctrl.create_incident({
            "title": "Prompt injection spike",
            "category": "security",
            "description": "Detected prompt injection attempts",
            "urgency": "immediate",
            "affected_users": 15000,
            "regulatory_criticality": "high",
            "tags": ["prompt_injection"],
        })
        assert inc.severity == "critical"

        triaged = ctrl.triage(inc.incident_id)
        assert triaged
        assert triaged.assigned_team == "Security"
        assert triaged.owner == "bob"

        run = ctrl.execute_runbook(inc.incident_id)
        assert run["status"] == "executed"

        contained = ctrl.contain(inc.incident_id, ["disable_tool", "force_hitl"])
        assert contained
        assert "disable_tool" in contained.containment_actions

        resolved = ctrl.resolve(inc.incident_id)
        assert resolved
        assert resolved.status == "resolved"

        pm = ctrl.generate_post_mortem(
            inc.incident_id,
            root_cause="Missing input guardrail",
            failed_controls=["input_filter"],
            action_items=["Add stricter guardrail", "Update tests"],
            mitigation_time_minutes=5,
            recovery_time_minutes=30,
        )
        assert pm
        assert pm.root_cause == "Missing input guardrail"

    def test_slo_and_alert(self):
        ctrl = IncidentManagementController()
        ctrl.register_sli("latency", "Latency p95", "latency_p95", "ms")
        slo = ctrl.define_slo("latency", 0.95, 3600)
        assert slo
        ctrl.record_slo_sample(slo.slo_id, False)
        budget = ctrl.get_error_budget(slo.slo_id)
        assert budget["consumed"] == 1


class TestIncidentAPI:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._incident_controller = IncidentManagementController()
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_create_and_triage(self, client):
        resp = client.post("/api/v1/incidents/oncall", json={"name": "alice", "team": "Security"})
        assert resp.status_code == 201
        resp = client.post("/api/v1/incidents", json={
            "title": "PII leak",
            "category": "security",
            "urgency": "immediate",
            "affected_users": 5000,
            "regulatory_criticality": "critical",
            "tags": ["pii_leak"],
        })
        assert resp.status_code == 201
        inc_id = resp.get_json()["data"]["incident_id"]
        triage = client.post(f"/api/v1/incidents/{inc_id}/triage")
        assert triage.status_code == 200
        assert triage.get_json()["data"]["assigned_team"] == "Security"

    def test_runbook_and_post_mortem(self, client):
        inc = client.post("/api/v1/incidents", json={
            "title": "Quality drop",
            "category": "quality",
        }).get_json()["data"]
        inc_id = inc["incident_id"]
        run = client.post(f"/api/v1/incidents/{inc_id}/runbook")
        assert run.status_code == 200
        assert run.get_json()["data"]["runbook_id"] == "rb-quality"
        client.post(f"/api/v1/incidents/{inc_id}/resolve")
        pm = client.post(f"/api/v1/incidents/{inc_id}/post-mortem", json={
            "root_cause": "Model drift",
            "failed_controls": ["drift_detector"],
            "action_items": ["Retrain"],
        })
        assert pm.status_code == 201

    def test_slo_budget(self, client):
        client.post("/api/v1/incidents/sli/register", json={
            "sli_id": "avail",
            "name": "Availability",
            "metric": "uptime",
            "unit": "ratio",
        })
        slo = client.post("/api/v1/incidents/slos", json={
            "sli_id": "avail",
            "target": 0.99,
            "window_seconds": 3600,
        })
        slo_id = slo.get_json()["data"]["slo_id"]
        budget = client.post(f"/api/v1/incidents/slos/{slo_id}/sample", json={"good": False})
        assert budget.status_code == 200
        assert budget.get_json()["data"]["consumed"] == 1

    def test_dashboard(self, client):
        resp = client.get("/api/v1/incidents/dashboard")
        assert resp.status_code == 200
        assert "total_incidents" in resp.get_json()["data"]
