"""Cross-team approval gate con pausa/reanudación durable via Temporal."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fine_tuning.quality_gate.models_quality import ApprovalSignature, CrossTeamApproval


class CrossTeamApprovalGate:
    """
    Gate de aprobación interdisciplinaria. El flujo se pausa hasta recibir las
    firmas de todos los equipos requeridos. Se integra con Temporal para
    durabilidad mediante signals/queries.
    """

    DEFAULT_TEAMS = ["engineering", "compliance", "business"]

    def __init__(self, required_teams: Optional[List[str]] = None, ttl_seconds: float = 86400.0) -> None:
        self.required_teams = required_teams or self.DEFAULT_TEAMS
        self.ttl_seconds = ttl_seconds
        self._approvals: Dict[str, CrossTeamApproval] = {}
        self._temporal = None  # inyectable

    def inject_temporal(self, temporal_adapter: Any) -> None:
        self._temporal = temporal_adapter

    def request_approval(
        self,
        run_id: str,
        report_id: str,
        workflow_id: str = "",
    ) -> CrossTeamApproval:
        approval = CrossTeamApproval(
            required_teams=list(self.required_teams),
            paused_workflow_id=workflow_id or f"qg-{run_id}",
            expires_at=time.time() + self.ttl_seconds,
            status="pending",
        )
        self._approvals[approval.approval_id] = approval

        if self._temporal and workflow_id:
            # Start or signal a durable workflow that waits for approval.
            existing = self._temporal.get_workflow(workflow_id)
            if not existing:
                self._temporal.start_workflow(
                    activities=[{"name": "wait_for_approval", "params": {"approval_id": approval.approval_id}}],
                    workflow_id=workflow_id,
                )
        return approval

    def submit_signature(
        self,
        approval_id: str,
        team: str,
        signed_by: str,
        comment: str = "",
    ) -> CrossTeamApproval:
        approval = self._approvals.get(approval_id)
        if not approval:
            raise ValueError("approval not found")
        if approval.status == "rejected":
            raise ValueError("approval already rejected")
        if time.time() > (approval.expires_at or 0):
            approval.status = "rejected"
            raise ValueError("approval expired")
        if team not in approval.required_teams:
            raise ValueError(f"team {team} not required")
        # Avoid duplicate signatures
        approval.signatures = [s for s in approval.signatures if s.team != team]
        approval.signatures.append(ApprovalSignature(
            team=team,
            signed_by=signed_by,
            comment=comment,
        ))
        if approval.is_approved():
            approval.status = "approved"
            if self._temporal and approval.paused_workflow_id:
                self._temporal.signal_workflow(
                    approval.paused_workflow_id,
                    "resume",
                    {"approval_id": approval_id, "status": "approved"},
                )
        return approval

    def reject(self, approval_id: str, team: str, reason: str = "") -> CrossTeamApproval:
        approval = self._approvals.get(approval_id)
        if not approval:
            raise ValueError("approval not found")
        approval.status = "rejected"
        if self._temporal and approval.paused_workflow_id:
            self._temporal.signal_workflow(
                approval.paused_workflow_id,
                "cancel",
                {"approval_id": approval_id, "reason": reason},
            )
        return approval

    def get(self, approval_id: str) -> Optional[CrossTeamApproval]:
        return self._approvals.get(approval_id)

    def status(self, approval_id: str) -> Dict[str, Any]:
        approval = self._approvals.get(approval_id)
        if not approval:
            return {"status": "not_found"}
        return approval.to_dict()
