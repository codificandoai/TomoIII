"""UC-324 — Safe Shutdown Coordinator: modelos, estado de máquina y cadena de evidencia.

Estado de máquina determinista:
  RUNNING -> QUIESCING -> DRAINING -> ROLLING_BACK -> CAPTURING -> SAFE_STOPPED
  Cualquier fallo -> CONTAINED (con metadata de fallo).
  No hay reinicio autónomo; la reactivación requiere aprobación humana.

Todas las estructuras son serializables y la cadena de evidencia
está vinculada por hashes (hash-chain) para integridad forense.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Estado de máquina
# ---------------------------------------------------------------------------

class ShutdownState(str, Enum):
    """Estados del ciclo de vida de shutdown seguro."""
    RUNNING = "RUNNING"
    QUIESCING = "QUIESCING"
    DRAINING = "DRAINING"
    ROLLING_BACK = "ROLLING_BACK"
    CAPTURING = "CAPTURING"
    SAFE_STOPPED = "SAFE_STOPPED"
    CONTAINED = "CONTAINED"


VALID_TRANSITIONS: Dict[ShutdownState, List[ShutdownState]] = {
    ShutdownState.RUNNING: [ShutdownState.QUIESCING],
    ShutdownState.QUIESCING: [ShutdownState.DRAINING, ShutdownState.CONTAINED],
    ShutdownState.DRAINING: [ShutdownState.ROLLING_BACK, ShutdownState.CONTAINED],
    ShutdownState.ROLLING_BACK: [ShutdownState.CAPTURING, ShutdownState.CONTAINED],
    ShutdownState.CAPTURING: [ShutdownState.SAFE_STOPPED, ShutdownState.CONTAINED],
    ShutdownState.SAFE_STOPPED: [],
    ShutdownState.CONTAINED: [],
}


class ShutdownReason(str, Enum):
    MANUAL = "manual"
    KILL_SWITCH = "kill_switch"
    CONTAINMENT_BREACH = "containment_breach"
    CIRCUIT_BREAKER = "circuit_breaker"
    POLICY_VIOLATION = "policy_violation"
    EXTERNAL = "external"


# ---------------------------------------------------------------------------
# Cadena de evidencia inmutable (hash-chain)
# ---------------------------------------------------------------------------

def _compute_hash(data: str, previous_hash: str = "") -> str:
    """SHA-256 sobre data + previous_hash."""
    payload = f"{previous_hash}:{data}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class EvidenceEntry:
    """Entrada inmutable en la cadena de evidencia."""
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    shutdown_id: str = ""
    trace_id: str = ""
    event_type: str = ""
    from_state: str = ""
    to_state: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    entry_hash: str = ""

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = _compute_hash(
                json.dumps({
                    "entry_id": self.entry_id,
                    "timestamp": self.timestamp,
                    "shutdown_id": self.shutdown_id,
                    "event_type": self.event_type,
                    "from_state": self.from_state,
                    "to_state": self.to_state,
                    "details": self.details,
                }, sort_keys=True, default=str),
                self.previous_hash,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "shutdown_id": self.shutdown_id,
            "trace_id": self.trace_id,
            "event_type": self.event_type,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


class EvidenceChain:
    """Cadena inmutable hash-linked de evidencia de shutdown."""

    def __init__(self) -> None:
        self._entries: List[EvidenceEntry] = []
        self._last_hash: str = ""

    def append(
        self,
        shutdown_id: str,
        trace_id: str,
        event_type: str,
        from_state: str = "",
        to_state: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> EvidenceEntry:
        entry = EvidenceEntry(
            shutdown_id=shutdown_id,
            trace_id=trace_id,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            details=details or {},
            previous_hash=self._last_hash,
        )
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        return entry

    def verify(self) -> bool:
        prev = ""
        for entry in self._entries:
            expected = _compute_hash(
                json.dumps({
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp,
                    "shutdown_id": entry.shutdown_id,
                    "event_type": entry.event_type,
                    "from_state": entry.from_state,
                    "to_state": entry.to_state,
                    "details": entry.details,
                }, sort_keys=True, default=str),
                prev,
            )
            if entry.entry_hash != expected or entry.previous_hash != prev:
                return False
            prev = entry.entry_hash
        return True

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def entries(self) -> List[EvidenceEntry]:
        return list(self._entries)

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries]


# ---------------------------------------------------------------------------
# Configuración de shutdown
# ---------------------------------------------------------------------------

@dataclass
class ShutdownConfig:
    """Configuración para el SafeShutdownCoordinator."""
    drain_timeout_seconds: float = 30.0
    rollback_timeout_seconds: float = 15.0
    capture_timeout_seconds: float = 10.0
    quiesce_timeout_seconds: float = 5.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drain_timeout_seconds": self.drain_timeout_seconds,
            "rollback_timeout_seconds": self.rollback_timeout_seconds,
            "capture_timeout_seconds": self.capture_timeout_seconds,
            "quiesce_timeout_seconds": self.quiesce_timeout_seconds,
        }


# ---------------------------------------------------------------------------
# Postmortem redactado
# ---------------------------------------------------------------------------

@dataclass
class RedactedPostmortem:
    """Postmortem seguro: sin secrets ni chain-of-thought crudos."""
    shutdown_id: str = ""
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    final_state: str = ""
    reason: str = ""
    tasks_drained: int = 0
    tasks_cancelled: int = 0
    rollbacks_executed: int = 0
    rollbacks_failed: int = 0
    adapter_results: Dict[str, str] = field(default_factory=dict)
    evidence_chain_hash: str = ""
    evidence_chain_valid: bool = True
    failure_metadata: Optional[Dict[str, Any]] = None
    health_snapshot: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shutdown_id": self.shutdown_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "final_state": self.final_state,
            "reason": self.reason,
            "tasks_drained": self.tasks_drained,
            "tasks_cancelled": self.tasks_cancelled,
            "rollbacks_executed": self.rollbacks_executed,
            "rollbacks_failed": self.rollbacks_failed,
            "adapter_results": self.adapter_results,
            "evidence_chain_hash": self.evidence_chain_hash,
            "evidence_chain_valid": self.evidence_chain_valid,
            "failure_metadata": self.failure_metadata,
            "health_snapshot": self.health_snapshot,
        }


# ---------------------------------------------------------------------------
# Solicitud y resultado de reactivación
# ---------------------------------------------------------------------------

@dataclass
class ReactivationRequest:
    """Solicitud de reactivación tras SAFE_STOPPED o CONTAINED."""
    shutdown_id: str = ""
    recovery_state_hash: str = ""
    reviewer_id: str = ""
    justification: str = ""
    ttl_seconds: float = 3600.0
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shutdown_id": self.shutdown_id,
            "recovery_state_hash": self.recovery_state_hash,
            "reviewer_id": self.reviewer_id,
            "justification": self.justification,
            "ttl_seconds": self.ttl_seconds,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ReactivationResult:
    """Resultado de un intento de reactivación."""
    approved: bool = False
    reason: str = ""
    shutdown_id: str = ""
    request_id: str = ""
    reviewer_id: str = ""
    new_state: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "shutdown_id": self.shutdown_id,
            "request_id": self.request_id,
            "reviewer_id": self.reviewer_id,
            "new_state": self.new_state,
        }


# ---------------------------------------------------------------------------
# Estado del shutdown
# ---------------------------------------------------------------------------

@dataclass
class ShutdownStatus:
    """Estado actual del shutdown coordinator."""
    shutdown_id: str = ""
    trace_id: str = ""
    state: ShutdownState = ShutdownState.RUNNING
    reason: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    config: Optional[ShutdownConfig] = None
    postmortem: Optional[RedactedPostmortem] = None
    evidence_chain_valid: bool = True
    evidence_chain_hash: str = ""
    failure_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shutdown_id": self.shutdown_id,
            "trace_id": self.trace_id,
            "state": self.state.value,
            "reason": self.reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "config": self.config.to_dict() if self.config else None,
            "postmortem": self.postmortem.to_dict() if self.postmortem else None,
            "evidence_chain_valid": self.evidence_chain_valid,
            "evidence_chain_hash": self.evidence_chain_hash,
            "failure_metadata": self.failure_metadata,
        }
