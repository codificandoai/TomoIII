"""Ledger de auditoría inmutable, consultable y correlacionable."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from rbac_audit.models_rbac import AuditRecord


class AuditLedger:
    """
    Registro inmutable de eventos de autenticación, acceso, cambio,
    despliegue, aprobación y denegación. Cada registro incluye hash SHA-256
    para detectar alteraciones y permite consultas por actor, recurso, acción,
    resultado y rango de tiempo.
    """

    def __init__(self) -> None:
        self._records: List[AuditRecord] = []
        self._last_hash: str = ""

    def record(
        self,
        event_type: str,
        principal_id: str,
        identity: str,
        role: str,
        action: str,
        resource_id: str,
        resource_type: str,
        resource_version: str = "",
        outcome: str = "",
        origin: str = "",
        details: Optional[Dict[str, Any]] = None,
        decision_id: str = "",
    ) -> AuditRecord:
        rec = AuditRecord(
            event_type=event_type,
            principal_id=principal_id,
            identity=identity,
            role=role,
            action=action,
            resource_id=resource_id,
            resource_type=resource_type,
            resource_version=resource_version,
            outcome=outcome,
            origin=origin,
            timestamp=time.time(),
            details=details or {},
            decision_id=decision_id,
        )
        rec.immutable_hash = self._hash(rec)
        self._records.append(rec)
        self._last_hash = rec.immutable_hash
        return rec

    def _hash(self, record: AuditRecord) -> str:
        payload = {
            "record_id": record.record_id,
            "event_type": record.event_type,
            "principal_id": record.principal_id,
            "identity": record.identity,
            "role": record.role,
            "action": record.action,
            "resource_id": record.resource_id,
            "resource_type": record.resource_type,
            "resource_version": record.resource_version,
            "outcome": record.outcome,
            "origin": record.origin,
            "timestamp": record.timestamp,
            "details": record.details,
            "decision_id": record.decision_id,
            "previous_hash": self._last_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def query(
        self,
        principal_id: str = "",
        resource_id: str = "",
        action: str = "",
        outcome: str = "",
        event_type: str = "",
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> List[AuditRecord]:
        result = self._records
        if principal_id:
            result = [r for r in result if r.principal_id == principal_id]
        if resource_id:
            result = [r for r in result if r.resource_id == resource_id]
        if action:
            result = [r for r in result if r.action == action]
        if outcome:
            result = [r for r in result if r.outcome == outcome]
        if event_type:
            result = [r for r in result if r.event_type == event_type]
        if start is not None:
            result = [r for r in result if r.timestamp >= start]
        if end is not None:
            result = [r for r in result if r.timestamp <= end]
        return result

    def verify(self) -> bool:
        previous_hash = ""
        for rec in self._records:
            expected = self._hash_with_previous(rec, previous_hash)
            if rec.immutable_hash != expected:
                return False
            previous_hash = rec.immutable_hash
        return True

    def _hash_with_previous(self, record: AuditRecord, previous_hash: str) -> str:
        payload = {
            "record_id": record.record_id,
            "event_type": record.event_type,
            "principal_id": record.principal_id,
            "identity": record.identity,
            "role": record.role,
            "action": record.action,
            "resource_id": record.resource_id,
            "resource_type": record.resource_type,
            "resource_version": record.resource_version,
            "outcome": record.outcome,
            "origin": record.origin,
            "timestamp": record.timestamp,
            "details": record.details,
            "decision_id": record.decision_id,
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def list_records(self) -> List[AuditRecord]:
        return list(self._records)
