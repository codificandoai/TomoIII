"""
UC-087 — Gestor de alertas y escalación.

Emite alertas estructuradas hacia UC-324 (contención/autorización),
UC-083 (incident response) y operadores humanos.
"""

import time
from typing import Dict, List, Any, Optional

from models_087 import ThreatCategory, DefenseAction


class AlertManager087:
    """
    Centraliza alertas de seguridad ML. Cada alerta incluye severidad,
runbook asociado y acción recomendada.
    """

    SEVERITY_MAP = {
        ThreatCategory.DATA_POISONING: "P1",
        ThreatCategory.BACKDOOR: "P1",
        ThreatCategory.ADVERSARIAL_EXAMPLE: "P2",
        ThreatCategory.MODEL_MANIPULATION: "P1",
        ThreatCategory.ARTIFACT_TAMPERING: "P1",
        ThreatCategory.UNKNOWN: "P2",
    }

    RUNBOOK_URLS = {
        ThreatCategory.DATA_POISONING: "https://wiki.trackprice.ai/runbooks/data_poisoning",
        ThreatCategory.BACKDOOR: "https://wiki.trackprice.ai/runbooks/backdoor",
        ThreatCategory.ADVERSARIAL_EXAMPLE: "https://wiki.trackprice.ai/runbooks/adversarial_example",
        ThreatCategory.MODEL_MANIPULATION: "https://wiki.trackprice.ai/runbooks/model_manipulation",
        ThreatCategory.ARTIFACT_TAMPERING: "https://wiki.trackprice.ai/runbooks/artifact_tampering",
        ThreatCategory.UNKNOWN: "https://wiki.trackprice.ai/runbooks/ml_security",
    }

    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []

    def send(
        self,
        threat: ThreatCategory,
        title: str,
        message: str,
        action: DefenseAction,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        alert = {
            "alert_id": f"alert_{len(self.alerts)+1:04d}",
            "timestamp": time.time(),
            "severity": self.SEVERITY_MAP.get(threat, "P2"),
            "threat": threat.value,
            "title": title,
            "message": message,
            "recommended_action": action.value,
            "runbook_url": self.RUNBOOK_URLS.get(threat, "https://wiki.trackprice.ai/runbooks/ml_security"),
            "destinations": self._destinations(action),
            "metadata": metadata or {},
        }
        self.alerts.append(alert)
        return alert

    def _destinations(self, action: DefenseAction) -> List[str]:
        destinations = ["uc-324-audit", "mlsecops-dashboard"]
        if action in (DefenseAction.QUARANTINE, DefenseAction.ROLLBACK, DefenseAction.ESCALATE):
            destinations.extend(["uc-083-incident-response", "pagerduty-oncall"])
        if action == DefenseAction.ESCALATE:
            destinations.append("uc-315-oversight")
        return destinations

    def list_alerts(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        if severity:
            return [a for a in self.alerts if a["severity"] == severity]
        return list(self.alerts)

    def clear(self) -> None:
        self.alerts.clear()

    def get_statistics(self) -> Dict[str, Any]:
        by_severity = {}
        for a in self.alerts:
            by_severity[a["severity"]] = by_severity.get(a["severity"], 0) + 1
        return {
            "total": len(self.alerts),
            "by_severity": by_severity,
        }

    def escalation_summary(self) -> Dict[str, Any]:
        escalated = [a for a in self.alerts if a["recommended_action"] == DefenseAction.ESCALATE.value]
        return {
            "escalated_count": len(escalated),
            "requires_human_approval": len(escalated) > 0,
            "latest": escalated[-1] if escalated else None,
        }
