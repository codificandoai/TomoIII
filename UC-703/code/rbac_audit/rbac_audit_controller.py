"""Controller de RBAC y auditoría inmutable para gobernanza de IA."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rbac_audit.approval_workflow import ApprovalWorkflow
from rbac_audit.audit_ledger import AuditLedger
from rbac_audit.models_rbac import (
    AccessDecision,
    ApprovalRequest,
    AuditRecord,
    Permission,
    Principal,
    Resource,
    Role,
)
from rbac_audit.rbac_engine import RBACEngine


class RBACAuditController:
    """
    Orquesta RBAC con mínimo privilegio, segregación de funciones, flujos de
    aprobación y un ledger de auditoría inmutable y consultable.
    """

    def __init__(
        self,
        rbac_engine: Optional[RBACEngine] = None,
        approval: Optional[ApprovalWorkflow] = None,
        audit: Optional[AuditLedger] = None,
    ) -> None:
        self.rbac = rbac_engine or RBACEngine()
        self.approval = approval or ApprovalWorkflow()
        self.audit = audit or AuditLedger()

    # ------------------------------------------------------------------
    # RBAC management
    # ------------------------------------------------------------------
    def create_role(self, role_id: str, name: str, description: str = "", permission_ids: Optional[List[str]] = None) -> Role:
        return self.rbac.create_role(role_id, name, description, permission_ids)

    def grant_permission(
        self,
        permission_id: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Permission:
        return self.rbac.grant_permission(permission_id, action, resource_type, resource_id, conditions)

    def create_principal(self, principal_id: str, name: str, principal_type: str, role_ids: Optional[List[str]] = None) -> Principal:
        return self.rbac.create_principal(principal_id, name, principal_type, role_ids)

    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        owner: str = "",
        version: str = "",
        sensitivity: str = "",
        environment: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Resource:
        return self.rbac.register_resource(resource_id, resource_type, owner, version, sensitivity, environment, metadata)

    def add_sod_rule(self, conflicting_roles: List[str]) -> None:
        self.rbac.add_sod_rule(conflicting_roles)

    # ------------------------------------------------------------------
    # Access enforcement
    # ------------------------------------------------------------------
    def check_access(
        self,
        principal_id: str,
        action: str,
        resource_id: str,
        resource_type: str,
        context: Optional[Dict[str, Any]] = None,
        approved: bool = False,
    ) -> AccessDecision:
        decision = self.rbac.check_access(principal_id, action, resource_id, resource_type, context, approved=approved)
        principal = self.rbac._principals.get(principal_id)
        resource = self.rbac._resources.get(resource_id)
        self.audit.record(
            event_type="access",
            principal_id=principal_id,
            identity=principal.name if principal else principal_id,
            role=",".join(principal.roles) if principal else "",
            action=action,
            resource_id=resource_id,
            resource_type=resource_type,
            resource_version=resource.version if resource else "",
            outcome="success" if decision.allowed else "denied",
            origin=context.get("origin", "api") if context else "api",
            details={"reason": decision.reason, "context": context or {}},
            decision_id=decision.decision_id,
        )
        return decision

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------
    def request_approval(
        self,
        principal_id: str,
        action: str,
        resource_id: str,
        resource_type: str,
        justification: str = "",
    ) -> ApprovalRequest:
        req = self.approval.request(principal_id, action, resource_id, resource_type, justification)
        principal = self.rbac._principals.get(principal_id)
        self.audit.record(
            event_type="approval",
            principal_id=principal_id,
            identity=principal.name if principal else principal_id,
            role=",".join(principal.roles) if principal else "",
            action=action,
            resource_id=resource_id,
            resource_type=resource_type,
            outcome="requested",
            origin="approval_workflow",
            details={"request_id": req.request_id, "justification": justification},
        )
        return req

    def approve(self, request_id: str, approver: str) -> Optional[ApprovalRequest]:
        req = self.approval.approve(request_id, approver)
        if req:
            principal = self.rbac._principals.get(req.principal_id)
            self.audit.record(
                event_type="approval",
                principal_id=req.principal_id,
                identity=principal.name if principal else req.principal_id,
                role=",".join(principal.roles) if principal else "",
                action=req.action,
                resource_id=req.resource_id,
                resource_type=req.resource_type,
                outcome="approved",
                origin="approval_workflow",
                details={"request_id": request_id, "approver": approver},
            )
        return req

    def reject(self, request_id: str, approver: str, reason: str = "") -> Optional[ApprovalRequest]:
        req = self.approval.reject(request_id, approver, reason)
        if req:
            principal = self.rbac._principals.get(req.principal_id)
            self.audit.record(
                event_type="approval",
                principal_id=req.principal_id,
                identity=principal.name if principal else req.principal_id,
                role=",".join(principal.roles) if principal else "",
                action=req.action,
                resource_id=req.resource_id,
                resource_type=req.resource_type,
                outcome="rejected",
                origin="approval_workflow",
                details={"request_id": request_id, "approver": approver, "reason": reason},
            )
        return req

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def audit_event(
        self,
        event_type: str,
        principal_id: str,
        action: str,
        resource_id: str,
        resource_type: str,
        outcome: str,
        origin: str = "",
        details: Optional[Dict[str, Any]] = None,
        resource_version: str = "",
    ) -> AuditRecord:
        principal = self.rbac._principals.get(principal_id)
        return self.audit.record(
            event_type=event_type,
            principal_id=principal_id,
            identity=principal.name if principal else principal_id,
            role=",".join(principal.roles) if principal else "",
            action=action,
            resource_id=resource_id,
            resource_type=resource_type,
            resource_version=resource_version,
            outcome=outcome,
            origin=origin,
            details=details or {},
        )

    def query_audit(
        self,
        principal_id: str = "",
        resource_id: str = "",
        action: str = "",
        outcome: str = "",
        event_type: str = "",
    ) -> List[AuditRecord]:
        return self.audit.query(
            principal_id=principal_id,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            event_type=event_type,
        )

    def verify_ledger(self) -> bool:
        return self.audit.verify()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def dashboard(self) -> Dict[str, Any]:
        return {
            "principals": len(self.rbac.list_principals()),
            "roles": len(self.rbac.list_roles()),
            "resources": len(self.rbac.list_resources()),
            "approval_requests": len(self.approval.list_all()),
            "pending_approvals": len(self.approval.list_pending()),
            "audit_records": len(self.audit.list_records()),
            "ledger_integrity": self.audit.verify(),
        }
