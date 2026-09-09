"""Ingesta y normalización de eventos para AIOps."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from aiops_self_healing.models_aiops import NormalizedAlert, RawEvent


class EventIngestionOrchestrator:
    """
    Orquesta el estado de ingesta de eventos: detectado -> normalizado.
    Soporta fuentes Prometheus, Loki, seguridad, calidad y coste.
    """

    def __init__(self) -> None:
        self._events: List[RawEvent] = []
        self._alerts: List[NormalizedAlert] = []

    def ingest(self, source: str, payload: Dict[str, Any]) -> RawEvent:
        event = RawEvent(source=source, raw_payload=payload)
        self._events.append(event)
        return event

    def normalize(self, event: RawEvent) -> Optional[NormalizedAlert]:
        payload = event.raw_payload
        alert = NormalizedAlert(
            event_id=event.event_id,
            source=event.source,
            metric=payload.get("metric", ""),
            value=float(payload.get("value", 0)),
            threshold=float(payload.get("threshold", 0)),
            severity=payload.get("severity", "medium"),
            category=payload.get("category", "availability"),
            resource=payload.get("resource", ""),
            timestamp=event.timestamp,
            metadata=payload.get("metadata", {}),
        )
        self._alerts.append(alert)
        return alert

    def ingest_and_normalize(self, source: str, payload: Dict[str, Any]) -> NormalizedAlert:
        event = self.ingest(source, payload)
        alert = self.normalize(event)
        assert alert is not None
        return alert

    def list_events(self) -> List[RawEvent]:
        return list(self._events)

    def list_alerts(self) -> List[NormalizedAlert]:
        return list(self._alerts)
