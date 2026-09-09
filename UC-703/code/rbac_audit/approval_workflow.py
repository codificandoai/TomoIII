"""Flujo de aprobación para operaciones críticas."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from rbac_audit.models_rbac import ApprovalRequest


class ApprovalWorkflow:
    """
    Gestiona solicitudes de aprobación para operaciones críticas.
    Permite aprobaciones múltiples y rechazos, y bloquea acciones sin
    aprobación completada.
    """

    def __init__(self, required_approvals: int = 1) -> None:
        self.required_approvals = required_approvals
        self._requests: Dict[str, ApprovalRequest] = {}

    def request(
        self,
        principal_id: str,
        action: str,
        resource_id: str,
        resource_type: str,
        justification: str = "",
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            principal_id=principal_id,
            action=action,
            resource_id=resource_id,
            resource_type=resource_type,
            justification=justification,
        )
        self._requests[req.request_id] = req
        return req

    def approve(self, request_id: str, approver: str) -> Optional[ApprovalRequest]:
        req = self._requests.get(request_id)
        if not req or req.status != "pending":
            return None
        if approver not in req.approvals:
            req.approvals.append(approver)
        if len(req.approvals) >= self.required_approvals:
            req.status = "approved"
            req.resolved_at = time.time()
        return req

    def reject(self, request_id: str, approver: str, reason: str = "") -> Optional[ApprovalRequest]:
        req = self._requests.get(request_id)
        if not req or req.status != "pending":
            return None
        if approver not in req.rejections:
            req.rejections.append(approver)
        req.status = "rejected"
        req.resolved_at = time.time()
        req.details = {"rejection_reason": reason}  # type: ignore[attr-defined]
        return req

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def list_pending(self) -> List[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "pending"]

    def list_all(self) -> List[ApprovalRequest]:
        return list(self._requests.values())
