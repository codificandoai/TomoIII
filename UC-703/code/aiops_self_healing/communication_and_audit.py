"""Comunicaciones automatizadas y registro inmutable de auditoría para AIOps."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from aiops_self_healing.models_aiops import AIOpsAuditRecord, CommunicationRecord


class CommunicationEngine:
    """Genera registros de comunicación basados en plantillas."""

    def __init__(self) -> None:
        self._records: List[CommunicationRecord] = []
        self._templates: Dict[str, str] = {
            "incident_opened": "Incident {group_id} opened: {summary}. Severity: {severity}. Owner: {owner}.",
            "incident_resolved": "Incident {group_id} resolved. Outcome: {outcome}.",
            "escalation": "Incident {group_id} escalated. Reason: {reason}. Next owner: {owner}.",
        }

    def render(self, template_name: str, variables: Dict[str, Any]) -> str:
        template = self._templates.get(template_name, "{summary}")
        return template.format_map({k: str(v) for k, v in variables.items()})

    def send(
        self,
        group_id: str,
        channel: str,
        recipient: str,
        template_name: str,
        variables: Dict[str, Any],
    ) -> CommunicationRecord:
        content = self.render(template_name, variables)
        record = CommunicationRecord(
            group_id=group_id,
            channel=channel,
            recipient=recipient,
            template=template_name,
            content=content,
        )
        self._records.append(record)
        return record

    def list_records(self) -> List[CommunicationRecord]:
        return list(self._records)


class AuditLedger:
    """Registro inmutable de eventos, decisiones, acciones y resultados."""

    def __init__(self) -> None:
        self._records: List[AIOpsAuditRecord] = []

    def record(
        self,
        group_id: str,
        state: str,
        decision: str,
        responsible: str,
        raw_event_ids: List[str],
        alert_ids: List[str],
        remediation_ids: List[str],
        diagnosis_id: str = "",
        outcome: str = "",
        approvals: Optional[List[str]] = None,
    ) -> AIOpsAuditRecord:
        rec = AIOpsAuditRecord(
            group_id=group_id,
            state=state,
            decision=decision,
            responsible=responsible,
            raw_event_ids=raw_event_ids,
            alert_ids=alert_ids,
            diagnosis_id=diagnosis_id,
            remediation_ids=remediation_ids,
            outcome=outcome,
            approvals=approvals or [],
            timestamp=time.time(),
        )
        rec.immutable_hash = self._hash(rec)
        self._records.append(rec)
        return rec

    def _hash(self, record: AIOpsAuditRecord) -> str:
        payload = {
            "record_id": record.record_id,
            "group_id": record.group_id,
            "state": record.state,
            "decision": record.decision,
            "responsible": record.responsible,
            "raw_event_ids": record.raw_event_ids,
            "alert_ids": record.alert_ids,
            "diagnosis_id": record.diagnosis_id,
            "remediation_ids": record.remediation_ids,
            "outcome": record.outcome,
            "approvals": record.approvals,
            "timestamp": record.timestamp,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def list_records(self) -> List[AIOpsAuditRecord]:
        return list(self._records)
