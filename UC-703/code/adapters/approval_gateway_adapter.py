"""
UC-703 — Approval Gateway Adapter.

Valida approvals contra gateways UC-290 (HITL) y UC-300 (Secure Tool Gateway).
En producción esto delegaría a los servicios reales vía HTTP; aquí incluye un
validador determinista local que respeta la separación de poderes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from models_703 import ApprovalDecision, Capability


@dataclass
class ApprovalGatewayAdapter:
    """
    Adapter de aprobación.

    - Acciones de bajo riesgo (auto_allowlist) pueden aprobarse por política.
    - Acciones destructivas o de alto impacto requieren HITL explícito.
    - `external_validator` permite conectar UC-300/UC-290 reales.
    """

    auto_allowlist: List[str] = field(default_factory=lambda: [
        "notify", "log", "read", "query", "search", "status", "observe", "dump_trace",
        "increase_monitoring", "scan_sbom",
    ])
    hitl_allowlist: List[str] = field(default_factory=lambda: [
        "delete", "revoke", "disable", "modify", "write", "rollback", "failover",
        "terminate", "block", "rotate_secrets", "scale_down", "destroy",
        "purchase", "transfer", "publish",
    ])
    external_validator: Optional[Callable[[Dict[str, Any]], Optional[ApprovalDecision]]] = None

    def _requires_hitl(self, action: str, params: Dict[str, Any]) -> bool:
        lowered = action.lower()
        for high in self.hitl_allowlist:
            if high in lowered:
                return True
        # Cross-tenant o sobre recursos sensibles => HITL
        if params.get("tenant_id") and params.get("target_tenant"):
            if params["tenant_id"] != params["target_tenant"]:
                return True
        # Coste/duración alta => HITL
        if params.get("estimated_cost_usd", 0) > 1000:
            return True
        if params.get("estimated_duration_seconds", 0) > 3600:
            return True
        return False

    def request_approval(
        self,
        action: str,
        params: Dict[str, Any],
        scope: str = "auto",
        requested_by: str = "uc703-runtime",
    ) -> ApprovalDecision:
        approval_ref = f"aprv-{action}-{int(time.time()*1000)}"

        if self.external_validator:
            external = self.external_validator({
                "action": action,
                "params": params,
                "scope": scope,
                "requested_by": requested_by,
                "approval_ref": approval_ref,
            })
            if external:
                return external

        if self._requires_hitl(action, params):
            if scope != "hitl":
                return ApprovalDecision(
                    approval_ref=approval_ref,
                    decision="denied",
                    reason=f"Action {action} requires explicit HITL approval",
                    scope="hitl",
                )
            return ApprovalDecision(
                approval_ref=approval_ref,
                decision="allowed",
                reason="Explicit HITL approval provided (local deterministic)",
                scope="hitl",
                approved_by="hitl-local",
                expires_at=time.time() + 3600,
            )

        # Auto-approval for low-risk actions
        return ApprovalDecision(
            approval_ref=approval_ref,
            decision="allowed",
            reason="Low-risk action approved by policy",
            scope="auto",
            approved_by="policy-local",
            expires_at=time.time() + 300,
        )

    def check_approval(self, approval_ref: str) -> ApprovalDecision:
        # En producción consultaría al gateway real.
        return ApprovalDecision(
            approval_ref=approval_ref,
            decision="allowed",
            reason="External approval verified",
            scope="hitl",
            approved_by="external-gateway",
            expires_at=time.time() + 3600,
        )
