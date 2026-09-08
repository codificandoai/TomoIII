"""In-memory alert manager for UC-309: stores, deduplicates and acknowledges."""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional


class Alert:
    def __init__(self, payload: Dict[str, Any]):
        self.id = self._alert_id(payload)
        self.payload = payload
        self.created_at = payload.get("timestamp", time.time())
        self.acknowledged = False
        self.acknowledged_by: Optional[str] = None
        self.acknowledged_at: Optional[float] = None

    @staticmethod
    def _alert_id(payload: Dict[str, Any]) -> str:
        stable = "|".join(str(v) for k, v in sorted(payload.items()) if k not in ("timestamp",))
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            **self.payload,
            "created_at": self.created_at,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at,
        }


class AlertManager:
    def __init__(self, max_alerts: int = 10_000):
        self.max_alerts = max_alerts
        self._alerts: Dict[str, Alert] = {}

    def ingest(self, anomalies: List[Dict[str, Any]]) -> List[str]:
        added: List[str] = []
        for a in anomalies:
            alert = Alert(a)
            if alert.id not in self._alerts:
                self._alerts[alert.id] = alert
                added.append(alert.id)
        # Prune oldest if over limit
        if len(self._alerts) > self.max_alerts:
            oldest = sorted(self._alerts.values(), key=lambda x: x.created_at)[:len(self._alerts) - self.max_alerts]
            for o in oldest:
                del self._alerts[o.id]
        return added

    def acknowledge(self, alert_id: str, user: Optional[str] = None) -> bool:
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        if not alert.acknowledged:
            alert.acknowledged = True
            alert.acknowledged_by = user or "anonymous"
            alert.acknowledged_at = time.time()
        return True

    def list_alerts(self, acknowledged: Optional[bool] = None) -> List[Dict[str, Any]]:
        alerts = self._alerts.values()
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return [a.to_dict() for a in sorted(alerts, key=lambda a: a.created_at, reverse=True)]

    def get(self, alert_id: str) -> Optional[Dict[str, Any]]:
        a = self._alerts.get(alert_id)
        return a.to_dict() if a else None

    def active_count(self) -> int:
        return sum(1 for a in self._alerts.values() if not a.acknowledged)

    def reset(self):
        self._alerts.clear()
