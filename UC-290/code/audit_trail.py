"""
UC-290 — Trail de Auditoría.

Persiste todos los eventos del pipeline HITL de forma auditable:
- Creación de expedientes.
- Escalamientos.
- Revisiones humanas.
- Aprobaciones, modificaciones, rechazos.
- Timeouts.
- Auto-ejecuciones.

Cada entrada incluye hash de integridad para prevenir manipulación.
"""

import time
import json
import hashlib
from typing import Dict, Any, List, Optional

from models_290 import AuditEntry, DecisionDossier, generate_id


class AuditTrail:
    """Trail de auditoría inmutable para el pipeline HITL."""

    def __init__(self, max_entries: int = 10000):
        self.entries: List[AuditEntry] = []
        self.max_entries = max_entries
        self._chain_hash: str = ""  # hash encadenado estilo blockchain

    def record(
        self,
        dossier: DecisionDossier,
        event: str,
        actor: str,
        details: Dict[str, Any] = None,
    ) -> AuditEntry:
        """Registra un evento en el trail de auditoría."""
        entry = AuditEntry(
            entry_id=generate_id(),
            dossier_id=dossier.dossier_id,
            trace_id=dossier.trace_id,
            timestamp=time.time(),
            event=event,
            actor=actor,
            details=details or {},
        )

        # Hash encadenado: cada entrada incluye el hash de la anterior
        chain_payload = json.dumps({
            "entry_id": entry.entry_id,
            "dossier_id": entry.dossier_id,
            "trace_id": entry.trace_id,
            "timestamp": entry.timestamp,
            "event": entry.event,
            "actor": entry.actor,
            "details": entry.details,
            "previous_hash": self._chain_hash,
        }, sort_keys=True, default=str)
        entry.content_hash = hashlib.sha256(chain_payload.encode()).hexdigest()
        self._chain_hash = entry.content_hash

        self.entries.append(entry)

        # Limitar tamaño
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

        return entry

    def record_dossier_created(self, dossier: DecisionDossier) -> AuditEntry:
        return self.record(
            dossier, "dossier_created", "system",
            {"status": dossier.status.value, "decision": dossier.decision.value}
        )

    def record_escalation(self, dossier: DecisionDossier, reasons: List[str]) -> AuditEntry:
        return self.record(
            dossier, "escalation_activated", "system",
            {"reasons": reasons, "risk_level": dossier.risk_assessment.risk_level.value if dossier.risk_assessment else "unknown"}
        )

    def record_human_review(self, dossier: DecisionDossier, review: Dict[str, Any]) -> AuditEntry:
        return self.record(
            dossier, "human_review", "human",
            review
        )

    def record_auto_execute(self, dossier: DecisionDossier) -> AuditEntry:
        return self.record(
            dossier, "auto_execute", "system",
            {"ai_suggestion": dossier.ai_suggestion, "confidence": dossier.ai_confidence}
        )

    def record_timeout(self, dossier: DecisionDossier) -> AuditEntry:
        return self.record(
            dossier, "escalation_timeout", "system",
            {"expires_at": dossier.expires_at}
        )

    def record_blocked(self, dossier: DecisionDossier, reason: str) -> AuditEntry:
        return self.record(
            dossier, "decision_blocked", "system",
            {"reason": reason}
        )

    def get_entries(self, dossier_id: str = None, trace_id: str = None) -> List[Dict[str, Any]]:
        """Filtra entradas por dossier o trace."""
        result = []
        for e in self.entries:
            if dossier_id and e.dossier_id != dossier_id:
                continue
            if trace_id and e.trace_id != trace_id:
                continue
            result.append(e.to_dict())
        return result

    def verify_chain(self) -> bool:
        """Verifica que la cadena de hashes no ha sido manipulada."""
        prev_hash = ""
        for entry in self.entries:
            chain_payload = json.dumps({
                "entry_id": entry.entry_id,
                "dossier_id": entry.dossier_id,
                "trace_id": entry.trace_id,
                "timestamp": entry.timestamp,
                "event": entry.event,
                "actor": entry.actor,
                "details": entry.details,
                "previous_hash": prev_hash,
            }, sort_keys=True, default=str)
            expected = hashlib.sha256(chain_payload.encode()).hexdigest()
            if entry.content_hash != expected:
                return False
            prev_hash = entry.content_hash
        return True

    def get_summary(self) -> Dict[str, Any]:
        """Resumen del trail de auditoría."""
        events: Dict[str, int] = {}
        actors: Dict[str, int] = {}
        for e in self.entries:
            events[e.event] = events.get(e.event, 0) + 1
            actors[e.actor] = actors.get(e.actor, 0) + 1
        return {
            "total_entries": len(self.entries),
            "events": events,
            "actors": actors,
            "chain_verified": self.verify_chain(),
            "latest_entry": self.entries[-1].to_dict() if self.entries else None,
        }

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.entries], indent=2, default=str)

    def reset(self):
        self.entries.clear()
        self._chain_hash = ""
