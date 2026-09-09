"""Tests para Compliance as Code layer en UC-703."""
from __future__ import annotations

import pytest

from compliance_as_code.compliance_controller import ComplianceController
from compliance_as_code.models_compliance import (
    AccessDecision,
    ArtifactBundle,
    ComplianceRule,
)


class TestPromptVersionControl:
    def test_commit_and_history(self):
        cac = ComplianceController()
        v1 = cac.commit_prompt("system", "Answer concisely.", "alice", commit_message="initial")
        v2 = cac.commit_prompt("system", "Answer concisely and safely.", "bob", regulatory_change=True, approved_by=["alice"])
        assert v2.parent_version_id == v1.version_id
        assert v2.regulatory_change
        history = cac.prompt_history("system")
        assert len(history) == 2

    def test_approve(self):
        cac = ComplianceController()
        v1 = cac.commit_prompt("system", "x", "alice")
        cac.approve_prompt("system", v1.version_id, "bob")
        v = cac.prompt_versioning.get_version("system", v1.version_id)
        assert "bob" in v.approved_by


class TestDataLineageTracker:
    def test_register_and_transform(self):
        cac = ComplianceController()
        lineage = cac.register_dataset(
            dataset_id="ds1",
            source="CRM export",
            consent_tags=["marketing_opt_in"],
            purpose="fine_tuning",
            privacy_controls=["deidentify", "dp_sgd"],
        )
        assert lineage.purpose == "fine_tuning"
        updated = cac.add_dataset_transformation("ds1", "deidentify", "remove PII", tool="presidio")
        assert updated and len(updated.transformations) == 1


class TestInferenceAuditLedger:
    def test_record_and_query(self):
        cac = ComplianceController()
        bundle = ArtifactBundle(base_weights="llama-7b", adapter="lora-v1", prompt_version_id="pv-1")
        rec = cac.record_inference(
            request_id="req1",
            session_id="s1",
            requester_id="user1",
            requester_roles=["operator"],
            artifact_bundle=bundle,
            input_text="hello",
            output_text="hi",
            access_decision="allowed",
            policies_applied=["pii_redaction"],
            e_discovery_tag="tag1",
        )
        assert rec.hash_chain
        assert len(cac.query_inference_audit(tag="tag1")) == 1
        assert cac.verify_ledger()


class TestAccessControlEnforcer:
    def test_allow_and_deny(self):
        cac = ComplianceController()
        cac.grant_role("operator", "model", "infer", environments=["prod"])
        cac.access_control.set_environment_roles("prod", ["operator"])
        cac.access_control.register_cmk("tenant-a", "cmk-123")
        decision = cac.evaluate_access(
            requester_id="user1",
            roles=["operator"],
            resource="model",
            action="infer",
            environment="prod",
            tenant="tenant-a",
        )
        assert decision.decision == "allow"
        assert decision.cmk_key_id == "cmk-123"

    def test_deny_wrong_environment(self):
        cac = ComplianceController()
        cac.grant_role("operator", "model", "infer", environments=["prod"])
        cac.access_control.set_environment_roles("prod", ["operator"])
        decision = cac.evaluate_access(
            requester_id="user1",
            roles=["operator"],
            resource="model",
            action="infer",
            environment="dev",
        )
        assert decision.decision == "deny"


class TestComplianceMappingAndAlerting:
    def test_default_rules(self):
        cac = ComplianceController()
        rules = cac.list_rules()
        frameworks = {r.framework for r in rules}
        assert "GDPR" in frameworks
        assert "DORA" in frameworks

    def test_alert_generation(self):
        cac = ComplianceController()
        alerts = cac.ingest_metric("pii_detected_rate", 0.2)
        assert alerts
        assert alerts[0].framework == "GDPR"
        assert alerts[0].status == "open"

    def test_dashboard_and_report(self):
        cac = ComplianceController()
        cac.ingest_metric("pii_detected_rate", 0.02)
        cac.ingest_metric("unauthorized_access_attempts", 1)
        report = cac.compliance_report()
        assert report["overall_status"] == "non_compliant"
        dashboard = cac.dashboard()
        assert "scores" in dashboard


class TestComplianceAPI:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._cac_controller = ComplianceController()
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_prompt_commit_and_history(self, client):
        resp = client.post("/api/v1/compliance/prompt/commit", json={
            "prompt_name": "api-prompt",
            "content": "Be helpful.",
            "author": "api",
            "regulatory_change": True,
        })
        assert resp.status_code == 201
        history = client.get("/api/v1/compliance/prompt/history/api-prompt")
        assert history.status_code == 200
        assert len(history.get_json()["data"]) == 1

    def test_dataset_register(self, client):
        resp = client.post("/api/v1/compliance/dataset/register", json={
            "dataset_id": "ds-api",
            "source": "API test",
            "purpose": "testing",
        })
        assert resp.status_code == 201
        get = client.get("/api/v1/compliance/dataset/ds-api")
        assert get.status_code == 200
        assert get.get_json()["data"]["purpose"] == "testing"

    def test_access_evaluate(self, client):
        client.post("/api/v1/compliance/access/grant", json={
            "role": "reader",
            "resource": "report",
            "action": "read",
        })
        resp = client.post("/api/v1/compliance/access/evaluate", json={
            "requester_id": "u1",
            "roles": ["reader"],
            "resource": "report",
            "action": "read",
            "environment": "prod",
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["decision"] == "allow"

    def test_inference_record_and_query(self, client):
        resp = client.post("/api/v1/compliance/inference/record", json={
            "request_id": "req-api",
            "session_id": "s-api",
            "requester_id": "u1",
            "requester_roles": ["operator"],
            "artifact_bundle": {
                "base_weights": "w",
                "adapter": "a",
                "prompt_version_id": "pv-1",
            },
            "input_text": "q",
            "output_text": "a",
            "access_decision": "allowed",
            "policies_applied": ["pii"],
            "e_discovery_tag": " litigation-123",
        })
        assert resp.status_code == 201
        query = client.get("/api/v1/compliance/inference/query?tag=%20litigation-123")
        assert query.status_code == 200
        assert len(query.get_json()["data"]) == 1

    def test_metrics_ingest_and_report(self, client):
        resp = client.post("/api/v1/compliance/metrics/ingest", json={
            "metric_name": "pii_detected_rate",
            "value": 0.5,
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["alerts"]
        report = client.get("/api/v1/compliance/report")
        assert report.status_code == 200
        assert report.get_json()["data"]["overall_status"] in ("at_risk", "non_compliant")

    def test_rules_and_dashboard(self, client):
        rules = client.get("/api/v1/compliance/rules")
        assert rules.status_code == 200
        assert any(r["framework"] == "GDPR" for r in rules.get_json()["data"])
        dash = client.get("/api/v1/compliance/dashboard")
        assert dash.status_code == 200
