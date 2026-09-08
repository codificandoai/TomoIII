"""
UC-300 — Auditoría inmutable con cadena de hashes.

Cada entrada referencia el hash de la entrada anterior, formando una
cadena inmutable. Alterar cualquier entrada rompe la cadena.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from models_300 import AuditEntry, generate_id


class ImmutableAuditTrail:
    """Trail de auditoría con hash chain."""

    def __init__(self):
        self.entries: List[AuditEntry] = []
        self._previous_hash = "0" * 64  # genesis hash

    def record(
        self,
        actor: str,
        event: str,
        details: Dict[str, Any],
        trace_id: str = "",
    ) -> AuditEntry:
        entry = AuditEntry(
            entry_id=generate_id(),
            trace_id=trace_id,
            timestamp=time.time(),
            actor=actor,
            event=event,
            details=details,
            previous_hash=self._previous_hash,
        )
        entry.compute_hash()
        self.entries.append(entry)
        self._previous_hash = entry.content_hash
        return entry

    def get_entries(
        self,
        trace_id: Optional[str] = None,
        event: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        result = self.entries
        if trace_id:
            result = [e for e in result if e.trace_id == trace_id]
        if event:
            result = [e for e in result if e.event == event]
        return [e.to_dict() for e in result]

    def verify_chain(self) -> bool:
        """Verifica integridad de la cadena de hashes."""
        previous_hash = "0" * 64
        for entry in self.entries:
            # Recalcular hash de la entrada
            payload = json.dumps({
                "entry_id": entry.entry_id,
                "trace_id": entry.trace_id,
                "timestamp": entry.timestamp,
                "actor": entry.actor,
                "event": entry.event,
                "details": entry.details,
                "previous_hash": entry.previous_hash,
            }, sort_keys=True, separators=(",", ":"), default=str)
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if expected_hash != entry.content_hash:
                return False
            if entry.previous_hash != previous_hash:
                return False
            previous_hash = entry.content_hash
        return True

    def tamper_check(self) -> List[Dict[str, Any]]:
        """Devuelve discrepancias si la cadena fue alterada."""
        issues = []
        previous_hash = "0" * 64
        for idx, entry in enumerate(self.entries):
            payload = json.dumps({
                "entry_id": entry.entry_id,
                "trace_id": entry.trace_id,
                "timestamp": entry.timestamp,
                "actor": entry.actor,
                "event": entry.event,
                "details": entry.details,
                "previous_hash": entry.previous_hash,
            }, sort_keys=True, separators=(",", ":"), default=str)
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if expected_hash != entry.content_hash:
                issues.append({"index": idx, "issue": "content_hash mismatch", "entry_id": entry.entry_id})
            if entry.previous_hash != previous_hash:
                issues.append({"index": idx, "issue": "previous_hash mismatch", "entry_id": entry.entry_id})
            previous_hash = entry.content_hash
        return issues

    def reset(self) -> None:
        self.entries.clear()
        self._previous_hash = "0" * 64
