"""Ledger inmutable (blockchain-like) para UC-273.

Audit trail con cadena de hashes verificable:
- Cada entrada apunta al hash de la anterior.
- Firma del monitor en cada entrada.
- Verificación de integridad de toda la cadena.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@dataclass(frozen=True)
class LedgerEntry:
    """Entrada del ledger inmutable."""
    index: int
    timestamp: float
    agent_id: str
    event_type: str
    event_data: str
    previous_hash: str
    entry_hash: str
    signature: bytes


class AuditLedger:
    """Ledger inmutable tipo blockchain para auditoría."""

    def __init__(self, monitor_private_key: Ed25519PrivateKey) -> None:
        self.entries: List[LedgerEntry] = []
        self.private_key = monitor_private_key

    def append(self, agent_id: str, event_type: str, event_data: dict) -> LedgerEntry:
        """Añade entrada firmada al ledger."""
        timestamp = time.time()
        previous_hash = self._last_hash()
        index = len(self.entries)
        data_str = json.dumps(event_data, sort_keys=True, default=str)

        content = f"{index}|{timestamp}|{agent_id}|{event_type}|{data_str}|{previous_hash}"
        entry_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        signature = self.private_key.sign(entry_hash.encode("utf-8"))

        entry = LedgerEntry(
            index=index,
            timestamp=timestamp,
            agent_id=agent_id,
            event_type=event_type,
            event_data=data_str,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            signature=signature,
        )
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        """Verifica integridad de toda la cadena."""
        for i, entry in enumerate(self.entries):
            if i == 0:
                if entry.previous_hash != "0" * 64:
                    return False, i
            else:
                if entry.previous_hash != self.entries[i - 1].entry_hash:
                    return False, i

            content = (
                f"{entry.index}|{entry.timestamp}|{entry.agent_id}|"
                f"{entry.event_type}|{entry.event_data}|{entry.previous_hash}"
            )
            computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if computed != entry.entry_hash:
                return False, i

        return True, None

    def get_agent_history(self, agent_id: str) -> List[LedgerEntry]:
        return [e for e in self.entries if e.agent_id == agent_id]

    def get_security_events(self) -> List[LedgerEntry]:
        return [e for e in self.entries if e.event_type.startswith("security.")]

    def _last_hash(self) -> str:
        if not self.entries:
            return "0" * 64
        return self.entries[-1].entry_hash

    @property
    def chain_length(self) -> int:
        return len(self.entries)
