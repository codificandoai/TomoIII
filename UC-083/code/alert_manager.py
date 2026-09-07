"""
UC-083 — Gestor de alertas y notificaciones para respuesta a incidentes.

Genera alertas estructuradas con enlaces a runbooks y canales de escalación.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Alert:
    alert_id: str
    severity: str
    title: str
    message: str
    runbook_url: str = ""
    channels: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    sent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "runbook_url": self.runbook_url,
            "channels": self.channels,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "sent": self.sent,
        }


class AlertManager:
    """
    Emite y registra alertas. Soporta simulación de canales (slack, pagerduty,
email, webhook) guardando el payload en lugar de enviarlo realmente.
    """

    SEVERITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "INFO": 3}

    def __init__(self, default_channels: Optional[List[str]] = None, runbook_base_url: str = ""):
        self.default_channels = default_channels or ["slack", "email"]
        self.runbook_base_url = runbook_base_url
        self._alerts: List[Alert] = []
        self._sent_payloads: List[Dict[str, Any]] = []

    def send(
        self,
        severity: str,
        title: str,
        message: str,
        runbook_name: Optional[str] = None,
        channels: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        alert_id = f"ALERT-{len(self._alerts)+1:04d}"
        runbook_url = ""
        if runbook_name:
            runbook_url = f"{self.runbook_base_url}/{runbook_name}"
        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            title=title,
            message=message,
            runbook_url=runbook_url,
            channels=channels or list(self.default_channels),
            metadata=metadata or {},
        )
        self._dispatch(alert)
        self._alerts.append(alert)
        return alert

    def _dispatch(self, alert: Alert) -> None:
        """Simula el envío a cada canal. En producción integrar webhook real."""
        for channel in alert.channels:
            payload = {
                "channel": channel,
                "alert_id": alert.alert_id,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "runbook_url": alert.runbook_url,
                "timestamp": alert.timestamp,
                "metadata": alert.metadata,
            }
            self._sent_payloads.append(payload)
        alert.sent = True

    def list_alerts(
        self,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        alerts = self._alerts
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return [a.to_dict() for a in alerts[-limit:]]

    def get_sent_payloads(self) -> List[Dict[str, Any]]:
        return list(self._sent_payloads)

    def get_statistics(self) -> Dict[str, Any]:
        counts = {}
        for a in self._alerts:
            counts[a.severity] = counts.get(a.severity, 0) + 1
        return {
            "total_alerts": len(self._alerts),
            "by_severity": counts,
            "sent_payloads": len(self._sent_payloads),
        }

    def reset(self) -> None:
        self._alerts.clear()
        self._sent_payloads.clear()
