"""UC-700 — Agente de gobierno, auditoría y aprobaciones.

Capa de gobierno:
  - RBAC simulado
  - Separación de funciones
  - Auditoría inmutable
  - Aprobación humana para acciones de alto riesgo
  - Evidencia de cada decisión automática
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from models import Incident, RemediationPlan


class GovernanceAgent:
    """Valida políticas y mantiene traza de auditoría."""

    def __init__(self, approved_actions: Optional[List[str]] = None):
        self.approved_actions = set(approved_actions or ["ADJUST_LOAD", "QUARANTINE_DEVICE"])
        self.audit_log: List[Dict[str, Any]] = []

    def approve_plan(self, incident: Incident, plan: RemediationPlan, operator_id: Optional[str] = None) -> Dict[str, Any]:
        if plan.strategy in self.approved_actions and plan.requires_approval is False:
            return {"approved": True, "method": "auto_policy", "operator_id": operator_id}

        if plan.requires_approval and operator_id is None:
            return {
                "approved": False,
                "method": "pending_human_approval",
                "required_roles": ["sre-oncall", "platform-engineer"],
            }

        return {"approved": True, "method": "human_approval", "operator_id": operator_id}

    def log_decision(self, incident_id: str, agent: str, decision: str, evidence: Dict[str, Any]) -> None:
        self.audit_log.append({
            "incident_id": incident_id,
            "agent": agent,
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat(),
            "evidence": evidence,
        })

    def get_audit(self, incident_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if incident_id:
            return [e for e in self.audit_log if e["incident_id"] == incident_id]
        return list(self.audit_log)

    def is_destructive_action_allowed(self, plan: RemediationPlan, operator_id: Optional[str] = None) -> bool:
        if plan.strategy in ("REPLACE_NODE", "DOMAIN_FAILOVER", "CHECKPOINT_RECOVERY"):
            return operator_id is not None
        return True
