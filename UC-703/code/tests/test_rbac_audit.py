"""Tests para RBAC y auditoría inmutable de gobernanza de IA."""
from __future__ import annotations

import pytest

from rbac_audit.approval_workflow import ApprovalWorkflow
from rbac_audit.audit_ledger import AuditLedger
from rbac_audit.rbac_audit_controller import RBACAuditController
from rbac_audit.rbac_engine import RBACEngine


class TestRBACEngine:
    def test_allowed_access(self):
        rb = RBACEngine()
        rb.grant_permission("perm1", "read", "model")
        rb.create_role("reader", "Model Reader", permission_ids=["perm1"])
        rb.create_principal("alice", "Alice", "user", role_ids=["reader"])
        decision = rb.check_access("alice", "read", "model-1", "model")
        assert decision.allowed

    def test_denied_access(self):
        rb = RBACEngine()
        rb.grant_permission("perm1", "read", "model")
        rb.create_role("reader", "Model Reader", permission_ids=["perm1"])
        rb.create_principal("alice", "Alice", "user", role_ids=["reader"])
        decision = rb.check_access("alice", "delete", "model-1", "model")
        assert not decision.allowed

    def test_sod_violation(self):
        rb = RBACEngine()
        rb.grant_permission("p1", "approve", "deployment")
        rb.grant_permission("p2", "deploy", "deployment")
        rb.create_role("approver", "Approver", permission_ids=["p1"])
        rb.create_role("deployer", "Deployer", permission_ids=["p2"])
        rb.add_sod_rule(["approver", "deployer"])
        rb.create_principal("bob", "Bob", "user", role_ids=["approver", "deployer"])
        decision = rb.check_access("bob", "deploy", "dep-1", "deployment")
        assert not decision.allowed
        assert "Segregation of duties" in decision.reason

    def test_admin_override(self):
        rb = RBACEngine()
        rb.grant_permission("admin", "admin", "*")
        rb.create_role("admin_role", "Admin", permission_ids=["admin"])
        rb.create_principal("root", "Root", "user", role_ids=["admin_role"])
        decision = rb.check_access("root", "delete", "anything", "model", approved=True)
        assert decision.allowed


class TestAuditLedger:
    def test_record_and_verify(self):
        ledger = AuditLedger()
        ledger.record(
            event_type="access",
            principal_id="alice",
            identity="Alice",
            role="reader",
            action="read",
            resource_id="model-1",
            resource_type="model",
            outcome="success",
        )
        assert len(ledger.list_records()) == 1
        assert ledger.verify()

    def test_query(self):
        ledger = AuditLedger()
        ledger.record(
            event_type="access",
            principal_id="alice",
            identity="Alice",
            role="reader",
            action="read",
            resource_id="model-1",
            resource_type="model",
            outcome="success",
        )
        results = ledger.query(principal_id="alice", outcome="success")
        assert len(results) == 1


class TestApprovalWorkflow:
    def test_approve(self):
        wf = ApprovalWorkflow(required_approvals=1)
        req = wf.request("alice", "deploy", "model-1", "model", "urgent fix")
        approved = wf.approve(req.request_id, "manager-1")
        assert approved
        assert approved.status == "approved"

    def test_reject(self):
        wf = ApprovalWorkflow(required_approvals=2)
        req = wf.request("alice", "deploy", "model-1", "model")
        wf.reject(req.request_id, "manager-1", "risk too high")
        assert wf.get(req.request_id).status == "rejected"


class TestRBACAuditController:
    def test_full_flow(self):
        ctrl = RBACAuditController()
        ctrl.grant_permission("read_model", "read", "model")
        ctrl.create_role("reader", "Reader", permission_ids=["read_model"])
        ctrl.create_principal("alice", "Alice", "user", role_ids=["reader"])
        ctrl.register_resource("model-1", "model", version="v1.2.3")

        decision = ctrl.check_access("alice", "read", "model-1", "model")
        assert decision.allowed
        records = ctrl.query_audit(principal_id="alice")
        assert len(records) == 1
        assert records[0].outcome == "success"

    def test_critical_operation_requires_approval(self):
        ctrl = RBACAuditController()
        ctrl.grant_permission("deploy_model", "deploy", "model")
        ctrl.create_role("deployer", "Deployer", permission_ids=["deploy_model"])
        ctrl.create_principal("bob", "Bob", "service_account", role_ids=["deployer"])
        ctrl.register_resource("model-prod", "model")

        decision = ctrl.check_access("bob", "deploy", "model-prod", "model")
        assert not decision.allowed  # critical action may still pass RBAC but workflow expects approval
        req = ctrl.request_approval("bob", "deploy", "model-prod", "model", "release v2")
        assert req.status == "pending"
        ctrl.approve(req.request_id, "manager-1")
        assert ctrl.approval.get(req.request_id).status == "approved"

    def test_ledger_integrity(self):
        ctrl = RBACAuditController()
        ctrl.create_principal("alice", "Alice", "user")
        ctrl.check_access("alice", "read", "r1", "model")
        assert ctrl.verify_ledger()


class TestRBACAuditAPI:
    @pytest.fixture
    def client(self):
        import api_703
        api_703._rbac_audit_controller = RBACAuditController()
        app = api_703.create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_role_permission_principal_resource(self, client):
        client.post("/api/v1/rbac/permissions", json={
            "permission_id": "read_model", "action": "read", "resource_type": "model"
        })
        client.post("/api/v1/rbac/roles", json={
            "role_id": "reader", "name": "Reader", "permission_ids": ["read_model"]
        })
        client.post("/api/v1/rbac/principals", json={
            "principal_id": "alice", "name": "Alice", "principal_type": "user", "role_ids": ["reader"]
        })
        client.post("/api/v1/rbac/resources", json={
            "resource_id": "model-1", "resource_type": "model", "version": "v1"
        })
        resp = client.post("/api/v1/rbac/access", json={
            "principal_id": "alice", "action": "read", "resource_id": "model-1", "resource_type": "model"
        })
        assert resp.status_code == 200
        assert resp.get_json()["data"]["allowed"] is True

    def test_sod_endpoint(self, client):
        client.post("/api/v1/rbac/sod", json={"conflicting_roles": ["approver", "deployer"]})
        resp = client.get("/api/v1/rbac/dashboard")
        assert resp.status_code == 200

    def test_approval_and_audit(self, client):
        client.post("/api/v1/rbac/principals", json={
            "principal_id": "bob", "name": "Bob", "principal_type": "service_account"
        })
        resp = client.post("/api/v1/rbac/approvals", json={
            "principal_id": "bob", "action": "deploy", "resource_id": "model-1", "resource_type": "model"
        })
        req_id = resp.get_json()["data"]["request_id"]
        client.post(f"/api/v1/rbac/approvals/{req_id}/approve", json={"approver": "manager-1"})
        audit = client.get("/api/v1/audit/query?event_type=approval")
        assert audit.status_code == 200
        assert len(audit.get_json()["data"]) >= 1

    def test_ledger_verify_endpoint(self, client):
        resp = client.get("/api/v1/audit/verify")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["valid"] is True
