"""In-memory trace store with retention, RBAC and immutable hash-chain audit."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set

from models_309 import CanonicalEvent

# Roles ordered by privilege (least to most)
ROLES = {
    "viewer": {"traces"},
    "analyst": {"traces", "metrics", "logs"},
    "auditor": {"traces", "metrics", "logs", "alerts"},
    "admin": {"traces", "metrics", "logs", "alerts", "retention", "reset"},
}

SENSITIVE_FIELDS = {
    "pii_pseudonyms", "redaction_findings", "allowlist_violations",
    "structured_reasoning_summary",
}


def has_permission(role: str, action: str) -> bool:
    perms = ROLES.get(role, set())
    return action in perms


def check_role(role: str, action: str) -> None:
    if not has_permission(role, action):
        raise PermissionError(f"role '{role}' cannot perform '{action}'")


class TraceStore:
    def __init__(
        self,
        max_records: int = 100_000,
        retention_seconds: int = 3600,
        require_role: bool = True,
    ):
        self.max_records = max_records
        self.retention_seconds = retention_seconds
        self.require_role = require_role
        # trace_id -> chronologically ordered list of events
        self._traces: Dict[str, List[CanonicalEvent]] = defaultdict(list)
        # global event order for TTL and max records
        self._event_order: deque = deque()
        self._secrets: Set[str] = set()

    def _evict(self):
        now = time.time()
        cutoff = (now - self.retention_seconds) * 1e9
        while self._event_order and self._event_order[0].timestamp_ns < cutoff:
            ev = self._event_order.popleft()
            lst = self._traces.get(ev.trace_id)
            if lst:
                try:
                    lst.remove(ev)
                except ValueError:
                    pass
                if not lst:
                    del self._traces[ev.trace_id]
        # Max records: trim oldest
        while len(self._event_order) > self.max_records:
            ev = self._event_order.popleft()
            lst = self._traces.get(ev.trace_id)
            if lst:
                try:
                    lst.remove(ev)
                except ValueError:
                    pass
                if not lst:
                    del self._traces[ev.trace_id]

    def store(self, event: CanonicalEvent) -> CanonicalEvent:
        """Store event and maintain hash-chain immutability within the trace."""
        self._evict()
        trace = self._traces.get(event.trace_id, [])
        if trace:
            last = trace[-1]
            if event.previous_event_hash is None:
                # Auto-link: seal hash chain using previous event hash
                event.previous_event_hash = last.event_hash
            elif event.previous_event_hash != last.event_hash:
                raise ValueError(
                    f"hash-chain broken for trace {event.trace_id}: "
                    f"expected {last.event_hash}, got {event.previous_event_hash}"
                )
        trace.append(event)
        self._traces[event.trace_id] = trace
        self._event_order.append(event)
        return event

    def get_trace(self, trace_id: str, role: Optional[str] = None) -> List[CanonicalEvent]:
        if self.require_role:
            if not role or not has_permission(role, "traces"):
                raise PermissionError("insufficient role for trace retrieval")
        self._evict()
        events = self._traces.get(trace_id, [])
        if role in ("viewer", "analyst") and events:
            # Only admin/auditor can see sensitive PII/redaction internal fields
            return [_redact_sensitive(ev) for ev in events]
        return events

    def list_traces(self, role: Optional[str] = None) -> List[str]:
        if self.require_role:
            if not role or not has_permission(role, "traces"):
                raise PermissionError("insufficient role for trace listing")
        self._evict()
        return list(self._traces.keys())

    def get_all_events(self, limit: Optional[int] = None, role: Optional[str] = None) -> List[CanonicalEvent]:
        if self.require_role and not has_permission(role or "viewer", "traces"):
            raise PermissionError("insufficient role")
        events = list(self._event_order)
        if limit:
            events = events[-limit:]
        if (role or "") in ("viewer", "analyst"):
            events = [_redact_sensitive(ev) for ev in events]
        return events

    def retention_stats(self) -> Dict[str, Any]:
        return {
            "total_events": len(self._event_order),
            "total_traces": len(self._traces),
            "max_records": self.max_records,
            "retention_seconds": self.retention_seconds,
        }

    def reset(self, role: Optional[str] = None):
        if self.require_role:
            check_role(role or "viewer", "reset")
        self._traces.clear()
        self._event_order.clear()

    def set_retention(self, max_records: Optional[int] = None, retention_seconds: Optional[int] = None, role: Optional[str] = None):
        if self.require_role:
            check_role(role or "viewer", "retention")
        if max_records is not None:
            self.max_records = max_records
        if retention_seconds is not None:
            self.retention_seconds = retention_seconds
        self._evict()


def _redact_sensitive(event: CanonicalEvent) -> CanonicalEvent:
    d = event.to_dict()
    for field in SENSITIVE_FIELDS:
        if field in d:
            d[field] = "[WITHHELD]"
    return CanonicalEvent.from_dict(d)
