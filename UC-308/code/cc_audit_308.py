"""
UC-308 — Immutable local audit hash chain for Champion/Challenger experiments.

Each entry links to the previous hash. Tampering an entry breaks verify_chain().
No filesystem or network side effects; everything stays in memory.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from cc_models_308 import AuditNode


class AuditChain:
    """Linked hash chain for experiment events, predictions, fills and decisions."""

    def __init__(self) -> None:
        self.entries: List[AuditNode] = []
        self._last_hash = self._genesis_hash()

    @staticmethod
    def _genesis_hash() -> str:
        return hashlib.sha256(b"uc308-cc-audit-genesis").hexdigest()

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def append(self, entry_type: str, data: Dict[str, Any]) -> AuditNode:
        seq = len(self.entries) + 1
        canonical = json.dumps(
            {"entry_type": entry_type, "seq": seq, "data": data},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        payload = f"{self._last_hash}:{canonical}".encode("utf-8")
        current_hash = hashlib.sha256(payload).hexdigest()
        node = AuditNode(
            entry_type=entry_type,
            seq=seq,
            data=data,
            previous_hash=self._last_hash,
            current_hash=current_hash,
            timestamp=time.time(),
        )
        self.entries.append(node)
        self._last_hash = current_hash
        return node

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    def verify_chain(self) -> bool:
        expected = self._genesis_hash()
        for node in self.entries:
            if node.previous_hash != expected:
                return False
            canonical = json.dumps(
                {"entry_type": node.entry_type, "seq": node.seq, "data": node.data},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            payload = f"{node.previous_hash}:{canonical}".encode("utf-8")
            if hashlib.sha256(payload).hexdigest() != node.current_hash:
                return False
            expected = node.current_hash
        return True

    def tamper_detected(self, seq: int) -> bool:
        """Diagnostic: recompute hash for entry seq and compare."""
        if seq < 1 or seq > len(self.entries):
            return False
        node = self.entries[seq - 1]
        prev_hash = self._genesis_hash() if seq == 1 else self.entries[seq - 2].current_hash
        canonical = json.dumps(
            {"entry_type": node.entry_type, "seq": node.seq, "data": node.data},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        payload = f"{prev_hash}:{canonical}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest() != node.current_hash
