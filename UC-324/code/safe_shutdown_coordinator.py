"""UC-324 — SafeShutdownCoordinator: orquestador de shutdown seguro.

Extensión de UC-324 (Containment Protocol) que coordina un shutdown
determinista y seguro a través de subsistemas de UC-300, UC-317, UC-309,
UC-296/UC-326 (MAQRI) y UC-290 mediante protocolos/interfaces de adaptador.

Diseño:
- UC-324 es la autoridad de orquestación y contención.
- Shutdown es idempotente, correlado por shutdown_id/trace_id.
- Toda la operación es determinista/offline/simulada: no hay SIGKILL,
  red real, destrucción de DB ni eliminación de archivos.
- La reactivación requiere aprobación humana explícita con hash exacto,
  TTL, anti-replay y health checks.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from safe_shutdown_models import (
    ShutdownStatus,
    EvidenceChain,
    ReactivationRequest,
    ReactivationResult,
    RedactedPostmortem,
    ShutdownConfig,
    ShutdownReason,
    ShutdownState,
    VALID_TRANSITIONS,
)


# ═══════════════════════════════════════════════════════════════════════════
# Adapter Protocols (interfaces con defaults no-op seguros)
# ═══════════════════════════════════════════════════════════════════════════

@runtime_checkable
class ToolGatewayAdapter(Protocol):
    """UC-300: SecureToolGateway shutdown adapter."""

    def quiesce(self, shutdown_id: str) -> Dict[str, Any]:
        ...

    def revoke_pending(self, shutdown_id: str) -> Dict[str, Any]:
        ...

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        ...

    def status(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class SchedulerAdapter(Protocol):
    """UC-317: AgentScheduler/AgentKernel shutdown adapter."""

    def stop_accepting_tasks(self, shutdown_id: str) -> Dict[str, Any]:
        ...

    def drain_tasks(self, shutdown_id: str, timeout_seconds: float) -> Dict[str, Any]:
        ...

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        ...

    def status(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class ObservabilityAdapter(Protocol):
    """UC-309: Observability postmortem ingestion adapter."""

    def ingest_postmortem(self, postmortem: Dict[str, Any]) -> Dict[str, Any]:
        ...


@runtime_checkable
class MemorySnapshotAdapter(Protocol):
    """UC-296/UC-326: Redacted memory snapshot adapter."""

    def redacted_snapshot(self, shutdown_id: str) -> Dict[str, Any]:
        ...


@runtime_checkable
class ReactivationApprovalAdapter(Protocol):
    """UC-290: Recovery/reactivation approval adapter."""

    def request_reactivation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        ...


# ═══════════════════════════════════════════════════════════════════════════
# Defaults no-op seguros
# ═══════════════════════════════════════════════════════════════════════════

class NoOpToolGatewayAdapter:
    """Safe no-op: no modifica nada, reporta estado neutral."""

    def quiesce(self, shutdown_id: str) -> Dict[str, Any]:
        return {"adapter": "noop_tool_gateway", "quiesced": True, "shutdown_id": shutdown_id}

    def revoke_pending(self, shutdown_id: str) -> Dict[str, Any]:
        return {"adapter": "noop_tool_gateway", "revoked": 0, "shutdown_id": shutdown_id}

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        return {"adapter": "noop_tool_gateway", "resumed": True, "shutdown_id": shutdown_id}

    def status(self) -> Dict[str, Any]:
        return {"adapter": "noop_tool_gateway", "state": "idle"}


class NoOpSchedulerAdapter:
    """Safe no-op scheduler adapter."""

    def stop_accepting_tasks(self, shutdown_id: str) -> Dict[str, Any]:
        return {"adapter": "noop_scheduler", "stopped": True, "shutdown_id": shutdown_id}

    def drain_tasks(self, shutdown_id: str, timeout_seconds: float) -> Dict[str, Any]:
        return {"adapter": "noop_scheduler", "drained": 0, "cancelled": 0, "shutdown_id": shutdown_id}

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        return {"adapter": "noop_scheduler", "resumed": True, "shutdown_id": shutdown_id}

    def status(self) -> Dict[str, Any]:
        return {"adapter": "noop_scheduler", "state": "idle"}


class NoOpObservabilityAdapter:
    """Safe no-op observability adapter."""

    def ingest_postmortem(self, postmortem: Dict[str, Any]) -> Dict[str, Any]:
        return {"adapter": "noop_observability", "ingested": True}


class NoOpMemorySnapshotAdapter:
    """Safe no-op memory snapshot adapter."""

    def redacted_snapshot(self, shutdown_id: str) -> Dict[str, Any]:
        return {"adapter": "noop_memory", "snapshot_hash": "", "total_entries": 0}


class NoOpReactivationApprovalAdapter:
    """Safe no-op reactivation adapter — always denies (safe default)."""

    def request_reactivation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "adapter": "noop_reactivation",
            "approved": False,
            "reason": "no reactivation adapter configured",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Concrete local adapters that wrap real subsystem objects (duck-typed)
# ═══════════════════════════════════════════════════════════════════════════

class ConcreteToolGatewayAdapter:
    """Adapts a UC-300 SecureToolGateway (or duck-typed) to the coordinator protocol."""

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    def quiesce(self, shutdown_id: str) -> Dict[str, Any]:
        fn = getattr(self._gateway, "quiesce_for_shutdown", None) or getattr(self._gateway, "quiesce", None)
        if fn is None:
            return {"adapter": "uc300_concrete", "quiesced": False, "error": "no quiesce method"}
        return fn(shutdown_id)

    def revoke_pending(self, shutdown_id: str) -> Dict[str, Any]:
        fn = getattr(self._gateway, "revoke_pending_for_shutdown", None) or getattr(self._gateway, "revoke_pending", None)
        if fn is None:
            return {"adapter": "uc300_concrete", "revoked": 0, "error": "no revoke method"}
        return fn(shutdown_id)

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        # Only the coordinator may call this; default no-op unless gateway exposes it.
        fn = getattr(self._gateway, "resume_after_approved_reactivation", None)
        if fn is None:
            return {"adapter": "uc300_concrete", "resumed": False, "note": "no resume hook"}
        return fn(shutdown_id)

    def status(self) -> Dict[str, Any]:
        fn = getattr(self._gateway, "shutdown_status", None) or getattr(self._gateway, "get_status", None)
        if fn is None:
            return {"adapter": "uc300_concrete", "state": "unknown"}
        return fn()


class ConcreteSchedulerAdapter:
    """Adapts a UC-317 AgentScheduler/AgentKernel (or duck-typed) to the protocol."""

    def __init__(self, scheduler: Any) -> None:
        self._scheduler = scheduler

    def stop_accepting_tasks(self, shutdown_id: str) -> Dict[str, Any]:
        fn = getattr(self._scheduler, "stop_accepting_tasks", None)
        if fn is None:
            return {"adapter": "uc317_concrete", "stopped": False, "error": "no stop method"}
        return fn(shutdown_id)

    def drain_tasks(self, shutdown_id: str, timeout_seconds: float) -> Dict[str, Any]:
        fn = getattr(self._scheduler, "drain_and_cancel", None) or getattr(self._scheduler, "drain_tasks", None)
        if fn is None:
            return {"adapter": "uc317_concrete", "drained": 0, "cancelled": 0, "error": "no drain method"}
        return fn(shutdown_id, timeout_seconds)

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        fn = getattr(self._scheduler, "resume_accepting_tasks", None)
        if fn is None:
            return {"adapter": "uc317_concrete", "resumed": False, "note": "no resume hook"}
        return fn()

    def status(self) -> Dict[str, Any]:
        fn = getattr(self._scheduler, "status", None)
        if fn is None:
            return {"adapter": "uc317_concrete", "state": "unknown"}
        return fn()


class ConcreteObservabilityAdapter:
    """Adapts a UC-309 ObservabilityOrchestrator."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def ingest_postmortem(self, postmortem: Dict[str, Any]) -> Dict[str, Any]:
        fn = getattr(self._orchestrator, "ingest_postmortem", None)
        if fn is None:
            return {"adapter": "uc309_concrete", "ingested": False, "error": "no ingest_postmortem method"}
        return fn(postmortem)


class ConcreteMemorySnapshotAdapter:
    """Adapts a UC-296/UC-326 memory module."""

    def __init__(self, memory_module: Any) -> None:
        self._memory = memory_module

    def redacted_snapshot(self, shutdown_id: str) -> Dict[str, Any]:
        fn = getattr(self._memory, "redacted_snapshot", None)
        if fn is None:
            return {"adapter": "uc296_326_concrete", "snapshot_hash": "", "error": "no redacted_snapshot method"}
        return fn(shutdown_id)


class ConcreteReactivationApprovalAdapter:
    """Adapts a UC-290 HITLGuardian (or duck-typed) to the protocol."""

    def __init__(self, guardian: Any) -> None:
        self._guardian = guardian

    def request_reactivation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        fn = getattr(self._guardian, "approve_reactivation", None)
        if fn is None:
            return {"adapter": "uc290_concrete", "approved": False, "error": "no approve_reactivation method"}
        return fn(request)


def build_concrete_adapters(
    tool_gateway: Optional[Any] = None,
    scheduler: Optional[Any] = None,
    observability: Optional[Any] = None,
    memory_snapshot: Optional[Any] = None,
    reactivation_approval: Optional[Any] = None,
) -> Dict[str, Any]:
    """Helper to wrap real subsystem objects into coordinator adapters."""
    return {
        "tool_gateway": ConcreteToolGatewayAdapter(tool_gateway) if tool_gateway is not None else NoOpToolGatewayAdapter(),
        "scheduler": ConcreteSchedulerAdapter(scheduler) if scheduler is not None else NoOpSchedulerAdapter(),
        "observability": ConcreteObservabilityAdapter(observability) if observability is not None else NoOpObservabilityAdapter(),
        "memory_snapshot": ConcreteMemorySnapshotAdapter(memory_snapshot) if memory_snapshot is not None else NoOpMemorySnapshotAdapter(),
        "reactivation_approval": ConcreteReactivationApprovalAdapter(reactivation_approval) if reactivation_approval is not None else NoOpReactivationApprovalAdapter(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Redaction / sanitization helpers
# ═══════════════════════════════════════════════════════════════════════════

_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|apikey|credential|auth|"
    r"private[_-]?key|session|cookie|bearer|api_secret|client_secret|secret_key|"
    r"pin|cvv|cert|key_material|access[_-]?token)"
)

_SENSITIVE_VALUE_HINTS = re.compile(
    r"(?i)(sk-[a-zA-Z0-9_\-]+|bearer\s+[a-zA-Z0-9_\-]+|[a-f0-9]{32,64})"
)


def _hash_sensitive(value: Any) -> Any:
    """Hash sensitive-looking string values; leave structure intact."""
    if isinstance(value, str) and _SENSITIVE_VALUE_HINTS.search(value):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    if isinstance(value, str) and len(value) > 48:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return value


def _redact_dict(obj: Any, path: str = "") -> Any:
    """Redact/pseudonymize sensitive keys and values recursively."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            child = f"{path}.{k}" if path else k
            if _SENSITIVE_KEY_PATTERNS.search(k):
                if isinstance(v, (dict, list)):
                    out[k] = "[REDACTED]"
                else:
                    out[k] = hashlib.sha256(str(v).encode("utf-8")).hexdigest()[:16]
            else:
                out[k] = _redact_dict(v, child)
        return out
    if isinstance(obj, list):
        return [_redact_dict(i, f"{path}[]") for i in obj]
    if isinstance(obj, str):
        # Strip chain-of-thought / raw reasoning markers
        if any(marker in obj.lower() for marker in ("chain_of_thought", "raw_thought", "internal_thought", "<|im_start|>system")):
            return "[REDACTED_PRIVATE_REASONING]"
        # Scrub embedded secret-looking tokens (sk-..., bearer ..., hex keys)
        if _SENSITIVE_VALUE_HINTS.search(obj):
            obj = _SENSITIVE_VALUE_HINTS.sub(
                lambda m: hashlib.sha256(m.group(0).encode("utf-8")).hexdigest()[:16],
                obj,
            )
        return obj
    return obj


def _sanitize_for_evidence(details: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize adapter result details before writing to evidence/postmortem."""
    redacted = _redact_dict(details)
    return redacted


# ═══════════════════════════════════════════════════════════════════════════
# Rollback registry
# ═══════════════════════════════════════════════════════════════════════════

class RollbackRegistry:
    """Registro de transacciones/checkpoints simulados para rollback."""

    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    def register(self, name: str, rollback_fn: Callable[[], Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> None:
        self._entries.append({
            "name": name,
            "rollback_fn": rollback_fn,
            "metadata": metadata or {},
            "registered_at": time.time(),
        })

    def execute_all(self) -> List[Dict[str, Any]]:
        results = []
        for entry in reversed(self._entries):
            try:
                result = entry["rollback_fn"]()
                results.append({
                    "name": entry["name"],
                    "success": True,
                    "result": _redact_dict(result),
                })
            except Exception as exc:
                results.append({
                    "name": entry["name"],
                    "success": False,
                    "error": str(exc),
                })
        return results

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════════════

class HealthChecker:
    """Verificador de salud pre-reactivación."""

    def __init__(self) -> None:
        self._checks: List[Callable[[], Dict[str, Any]]] = []

    def register(self, check_fn: Callable[[], Dict[str, Any]]) -> None:
        self._checks.append(check_fn)

    def run_all(self) -> Dict[str, Any]:
        results = []
        all_ok = True
        for fn in self._checks:
            try:
                r = fn()
                ok = r.get("healthy", True)
                results.append({"check": fn.__name__, "result": _redact_dict(r), "ok": ok})
                if not ok:
                    all_ok = False
            except Exception as exc:
                results.append({"check": fn.__name__, "error": str(exc), "ok": False})
                all_ok = False
        return {"healthy": all_ok, "checks": results}


# ═══════════════════════════════════════════════════════════════════════════
# SafeShutdownCoordinator
# ═══════════════════════════════════════════════════════════════════════════

class SafeShutdownCoordinator:
    """Orquestador de shutdown seguro para UC-324."""

    def __init__(
        self,
        config: Optional[ShutdownConfig] = None,
        tool_gateway: Optional[ToolGatewayAdapter] = None,
        scheduler: Optional[SchedulerAdapter] = None,
        observability: Optional[ObservabilityAdapter] = None,
        memory_snapshot: Optional[MemorySnapshotAdapter] = None,
        reactivation_approval: Optional[ReactivationApprovalAdapter] = None,
    ) -> None:
        self.config = config or ShutdownConfig()
        self._tool_gateway = tool_gateway or NoOpToolGatewayAdapter()
        self._scheduler = scheduler or NoOpSchedulerAdapter()
        self._observability = observability or NoOpObservabilityAdapter()
        self._memory_snapshot = memory_snapshot or NoOpMemorySnapshotAdapter()
        self._reactivation_approval = reactivation_approval or NoOpReactivationApprovalAdapter()

        # Estado
        self._state = ShutdownState.RUNNING
        self._shutdown_id: str = ""
        self._trace_id: str = ""
        self._reason: str = ""
        self._started_at: float = 0.0
        self._completed_at: float = 0.0
        self._failure_metadata: Optional[Dict[str, Any]] = None
        self._postmortem: Optional[RedactedPostmortem] = None

        # Registros
        self._evidence = EvidenceChain()
        self._rollback_registry = RollbackRegistry()
        self._health_checker = HealthChecker()

        # Anti-replay para reactivación
        self._used_request_ids: set = set()

        # Contadores de la última ejecución
        self._tasks_drained: int = 0
        self._tasks_cancelled: int = 0
        self._rollbacks_executed: int = 0
        self._rollbacks_failed: int = 0
        self._adapter_results: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Propiedades
    # ------------------------------------------------------------------
    @property
    def state(self) -> ShutdownState:
        return self._state

    @property
    def shutdown_id(self) -> str:
        return self._shutdown_id

    @property
    def evidence(self) -> EvidenceChain:
        return self._evidence

    @property
    def rollback_registry(self) -> RollbackRegistry:
        return self._rollback_registry

    @property
    def health_checker(self) -> HealthChecker:
        return self._health_checker

    # ------------------------------------------------------------------
    # Transición de estado
    # ------------------------------------------------------------------
    def _transition(self, to_state: ShutdownState, details: Optional[Dict[str, Any]] = None) -> None:
        from_state = self._state
        valid_next = VALID_TRANSITIONS.get(from_state, [])
        if to_state not in valid_next:
            self._enter_contained(
                f"invalid transition {from_state.value}->{to_state.value}",
                details,
            )
            return
        self._state = to_state
        sanitized = _sanitize_for_evidence(details or {})
        self._evidence.append(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            event_type="state_transition",
            from_state=from_state.value,
            to_state=to_state.value,
            details=sanitized,
        )

    def _enter_contained(self, reason: str, details: Optional[Dict[str, Any]] = None) -> None:
        from_state = self._state
        self._state = ShutdownState.CONTAINED
        self._failure_metadata = _redact_dict({
            "reason": reason,
            "from_state": from_state.value,
            "details": details or {},
            "timestamp": time.time(),
        })
        sanitized = _sanitize_for_evidence({"reason": reason, **(details or {})})
        self._evidence.append(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            event_type="contained_failure",
            from_state=from_state.value,
            to_state=ShutdownState.CONTAINED.value,
            details=sanitized,
        )

    def enter_safe_hold(self, reason: str, trace_id: Optional[str] = None) -> ShutdownStatus:
        """Transición a SAFE_HOLD: pausa controlada sin perder estado."""
        if self._state not in (ShutdownState.RUNNING, ShutdownState.QUIESCING):
            return self._build_status()
        if not self._shutdown_id:
            self._shutdown_id = uuid.uuid4().hex[:12]
        self._trace_id = trace_id or uuid.uuid4().hex[:16]
        self._reason = reason
        self._transition(ShutdownState.SAFE_HOLD, {"reason": reason})
        return self._build_status()

    def resume_from_safe_hold(self, trace_id: Optional[str] = None) -> ShutdownStatus:
        """Reanuda desde SAFE_HOLD a RUNNING tras resolución del incidente."""
        if self._state != ShutdownState.SAFE_HOLD:
            return self._build_status()
        self._trace_id = trace_id or uuid.uuid4().hex[:16]
        self._transition(ShutdownState.RUNNING, {"reason": "resume_from_safe_hold"})
        return self._build_status()

    # ------------------------------------------------------------------
    # Orquestación principal
    # ------------------------------------------------------------------
    def initiate_shutdown(
        self,
        reason: str = "manual",
        shutdown_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ShutdownStatus:
        proposed_id = shutdown_id or uuid.uuid4().hex[:12]

        # Idempotencia: mismo shutdown_id
        if self._shutdown_id == proposed_id and self._state != ShutdownState.RUNNING:
            return self._build_status()

        # Solo se puede iniciar desde RUNNING
        if self._state != ShutdownState.RUNNING:
            return self._build_status()

        self._shutdown_id = proposed_id
        self._trace_id = trace_id or uuid.uuid4().hex[:16]
        self._reason = reason
        self._started_at = time.time()
        self._failure_metadata = None
        self._postmortem = None
        self._tasks_drained = 0
        self._tasks_cancelled = 0
        self._rollbacks_executed = 0
        self._rollbacks_failed = 0
        self._adapter_results = {}

        sanitized_reason = _redact_dict({"reason": reason})
        self._evidence.append(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            event_type="shutdown_initiated",
            from_state=ShutdownState.RUNNING.value,
            to_state=ShutdownState.RUNNING.value,
            details=sanitized_reason,
        )

        self._phase_quiesce()
        if self._state == ShutdownState.CONTAINED:
            return self._finalize()

        self._phase_drain()
        if self._state == ShutdownState.CONTAINED:
            return self._finalize()

        self._phase_rollback()
        if self._state == ShutdownState.CONTAINED:
            return self._finalize()

        self._phase_capture()
        if self._state == ShutdownState.CONTAINED:
            return self._finalize()

        self._transition(ShutdownState.SAFE_STOPPED, {"reason": "shutdown complete"})
        return self._finalize()

    # ------------------------------------------------------------------
    # Fases individuales
    # ------------------------------------------------------------------
    def _phase_quiesce(self) -> None:
        self._transition(ShutdownState.QUIESCING, {"phase": "quiesce"})
        if self._state == ShutdownState.CONTAINED:
            return

        try:
            r = self._tool_gateway.quiesce(self._shutdown_id)
            self._adapter_results["tool_gateway_quiesce"] = "ok"
            self._evidence.append(
                self._shutdown_id, self._trace_id,
                "adapter_quiesce", details={"adapter": "tool_gateway", "result": _redact_dict(r)},
            )
        except Exception as exc:
            self._enter_contained(f"tool_gateway.quiesce failed: {exc}")
            return

        try:
            r = self._scheduler.stop_accepting_tasks(self._shutdown_id)
            self._adapter_results["scheduler_stop"] = "ok"
            self._evidence.append(
                self._shutdown_id, self._trace_id,
                "tasks_rejected", details={"adapter": "scheduler", "result": _redact_dict(r)},
            )
        except Exception as exc:
            self._enter_contained(f"scheduler.stop_accepting_tasks failed: {exc}")

    def _phase_drain(self) -> None:
        self._transition(ShutdownState.DRAINING, {"phase": "drain"})
        if self._state == ShutdownState.CONTAINED:
            return

        try:
            r = self._scheduler.drain_tasks(
                self._shutdown_id,
                timeout_seconds=self.config.drain_timeout_seconds,
            )
            self._tasks_drained = r.get("drained", 0)
            self._tasks_cancelled = r.get("cancelled", 0)
            self._adapter_results["scheduler_drain"] = "ok"
            self._evidence.append(
                self._shutdown_id, self._trace_id,
                "tasks_drained",
                details={"drained": self._tasks_drained, "cancelled": self._tasks_cancelled},
            )
        except Exception as exc:
            self._enter_contained(f"scheduler.drain_tasks failed: {exc}")
            return

        try:
            r = self._tool_gateway.revoke_pending(self._shutdown_id)
            self._adapter_results["tool_gateway_revoke"] = "ok"
            self._evidence.append(
                self._shutdown_id, self._trace_id,
                "credentials_revoked", details={"adapter": "tool_gateway", "result": _redact_dict(r)},
            )
        except Exception as exc:
            self._enter_contained(f"tool_gateway.revoke_pending failed: {exc}")

    def _phase_rollback(self) -> None:
        self._transition(ShutdownState.ROLLING_BACK, {"phase": "rollback"})
        if self._state == ShutdownState.CONTAINED:
            return

        results = self._rollback_registry.execute_all()
        self._rollbacks_executed = sum(1 for r in results if r["success"])
        self._rollbacks_failed = sum(1 for r in results if not r["success"])

        self._evidence.append(
            self._shutdown_id, self._trace_id,
            "rollback_results",
            details=_redact_dict({
                "executed": self._rollbacks_executed,
                "failed": self._rollbacks_failed,
                "results": [
                    {k: v for k, v in r.items() if k != "result"}
                    for r in results
                ],
            }),
        )

        if self._rollbacks_failed > 0:
            self._enter_contained(
                f"rollback failed: {self._rollbacks_failed} of {len(results)}",
                {"results": results},
            )

    def _phase_capture(self) -> None:
        self._transition(ShutdownState.CAPTURING, {"phase": "capture"})
        if self._state == ShutdownState.CONTAINED:
            return

        # UC-296/UC-326 MAQRI: memory snapshot
        memory_snap = {}
        try:
            memory_snap = self._memory_snapshot.redacted_snapshot(self._shutdown_id)
            self._adapter_results["memory_snapshot"] = "ok"
        except Exception as exc:
            self._adapter_results["memory_snapshot"] = f"error: {exc}"

        # Construir postmortem redactado (will be finalized/ingested in _finalize)
        self._postmortem = RedactedPostmortem(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            final_state=self._state.value,
            reason=self._reason,
            tasks_drained=self._tasks_drained,
            tasks_cancelled=self._tasks_cancelled,
            rollbacks_executed=self._rollbacks_executed,
            rollbacks_failed=self._rollbacks_failed,
            adapter_results=_redact_dict(self._adapter_results.copy()),
            evidence_chain_hash=self._evidence.last_hash,
            evidence_chain_valid=self._evidence.verify(),
            failure_metadata=_redact_dict(self._failure_metadata) if self._failure_metadata else None,
            health_snapshot=_redact_dict(memory_snap),
        )

        self._evidence.append(
            self._shutdown_id, self._trace_id,
            "postmortem_captured",
            details={
                "evidence_chain_hash": self._evidence.last_hash,
                "evidence_chain_valid": self._evidence.verify(),
            },
        )

        # Note: observability ingestion is done in _finalize after the final state is known.

    def _finalize(self) -> ShutdownStatus:
        """Finalize shutdown: append finalization evidence, then update and
        re-ingest the postmortem so final_state and evidence_hash are current."""
        self._completed_at = time.time()

        # If CONTAINED without postmortem, generate one now (but will be
        # updated after finalization evidence below).
        if self._state == ShutdownState.CONTAINED and self._postmortem is None:
            self._postmortem = RedactedPostmortem(
                shutdown_id=self._shutdown_id,
                trace_id=self._trace_id,
                final_state=self._state.value,
                reason=self._reason,
                tasks_drained=self._tasks_drained,
                tasks_cancelled=self._tasks_cancelled,
                rollbacks_executed=self._rollbacks_executed,
                rollbacks_failed=self._rollbacks_failed,
                adapter_results=_redact_dict(self._adapter_results.copy()),
                evidence_chain_hash=self._evidence.last_hash,
                evidence_chain_valid=self._evidence.verify(),
                failure_metadata=_redact_dict(self._failure_metadata) if self._failure_metadata else None,
            )

        # Append finalization evidence so the chain includes the terminal state.
        self._evidence.append(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            event_type="shutdown_finalized",
            from_state=self._state.value,
            to_state=self._state.value,
            details={
                "completed_at": self._completed_at,
                "final_state": self._state.value,
                "evidence_chain_valid": self._evidence.verify(),
            },
        )

        # Update postmortem to reflect final state and final evidence hash.
        if self._postmortem is not None:
            self._postmortem.final_state = self._state.value
            self._postmortem.evidence_chain_hash = self._evidence.last_hash
            self._postmortem.evidence_chain_valid = self._evidence.verify()
            try:
                self._observability.ingest_postmortem(_redact_dict(self._postmortem.to_dict()))
            except Exception:
                pass

        return self._build_status()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def _build_status(self) -> ShutdownStatus:
        return ShutdownStatus(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            state=self._state,
            reason=self._reason,
            started_at=self._started_at,
            completed_at=self._completed_at,
            config=self.config,
            postmortem=self._postmortem,
            evidence_chain_valid=self._evidence.verify(),
            evidence_chain_hash=self._evidence.last_hash,
            failure_metadata=_redact_dict(self._failure_metadata) if self._failure_metadata else None,
        )

    def get_status(self) -> ShutdownStatus:
        return self._build_status()

    def get_postmortem(self) -> Optional[RedactedPostmortem]:
        return self._postmortem

    def get_evidence(self) -> List[Dict[str, Any]]:
        return self._evidence.to_list()

    def is_shutdown(self) -> bool:
        return self._state in (ShutdownState.SAFE_STOPPED, ShutdownState.CONTAINED)

    def compute_recovery_state_hash(self) -> str:
        """Hash del estado actual para validación de reactivación."""
        pm_dict = self._postmortem.to_dict() if self._postmortem else {}
        payload = json.dumps({
            "shutdown_id": self._shutdown_id,
            "state": self._state.value,
            "evidence_chain_hash": self._evidence.last_hash,
            "postmortem_hash": hashlib.sha256(
                json.dumps(pm_dict, sort_keys=True, default=str).encode()
            ).hexdigest(),
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Reactivación
    # ------------------------------------------------------------------
    def request_reactivation(self, request: ReactivationRequest) -> ReactivationResult:
        result = ReactivationResult(
            shutdown_id=request.shutdown_id,
            request_id=request.request_id,
            reviewer_id=request.reviewer_id,
        )

        # Estado actual debe ser terminal
        if self._state not in (ShutdownState.SAFE_STOPPED, ShutdownState.CONTAINED):
            result.reason = f"cannot reactivate from state {self._state.value}"
            return result

        # shutdown_id debe coincidir
        if request.shutdown_id != self._shutdown_id:
            result.reason = "shutdown_id mismatch"
            return result

        # Verificar reviewer_id
        if not request.reviewer_id or not request.reviewer_id.strip():
            result.reason = "reviewer_id required for human approval"
            return result

        # ttl_seconds must be positive
        if request.ttl_seconds <= 0:
            result.reason = "ttl_seconds must be > 0"
            return result

        # timestamp cannot be unreasonably in the future (clock skew)
        now = time.time()
        if request.timestamp > now + 60.0:
            result.reason = "timestamp unreasonably far in the future (clock skew)"
            return result

        # Anti-replay: consume request_id on any attempt
        if request.request_id in self._used_request_ids:
            result.reason = "request_id already used (anti-replay)"
            return result
        self._used_request_ids.add(request.request_id)

        # TTL
        elapsed = now - request.timestamp
        if elapsed > request.ttl_seconds:
            result.reason = "reactivation request expired (TTL)"
            return result

        # Hash exacto del estado de recovery
        expected_hash = self.compute_recovery_state_hash()
        if request.recovery_state_hash != expected_hash:
            result.reason = "recovery_state_hash mismatch"
            return result

        # Health checks
        health = self._health_checker.run_all()
        if not health["healthy"]:
            result.reason = f"health checks failed: {health}"
            return result

        # UC-290: Approval adapter
        try:
            approval = self._reactivation_approval.request_reactivation(request.to_dict())
            if not approval.get("approved", False):
                result.reason = approval.get("reason", "reactivation not approved")
                return result
        except Exception as exc:
            result.reason = f"reactivation approval adapter failed: {exc}"
            return result

        # Capture terminal state before reactivation for evidence
        terminal_state = self._state

        # Aprobado — reactivar
        self._state = ShutdownState.RUNNING
        self._evidence.append(
            shutdown_id=self._shutdown_id,
            trace_id=self._trace_id,
            event_type="reactivation",
            from_state=terminal_state.value,
            to_state=ShutdownState.RUNNING.value,
            details=_redact_dict({
                "reviewer_id": request.reviewer_id,
                "request_id": request.request_id,
                "justification": request.justification,
            }),
        )

        # Resume adapters
        try:
            self._tool_gateway.resume_after_approved_reactivation(self._shutdown_id)
        except Exception:
            pass
        try:
            self._scheduler.resume_after_approved_reactivation(self._shutdown_id)
        except Exception:
            pass

        # Reset para siguiente ciclo
        self._shutdown_id = ""
        self._reason = ""
        self._started_at = 0.0
        self._completed_at = 0.0
        self._failure_metadata = None
        self._postmortem = None
        self._rollback_registry.clear()

        result.approved = True
        result.reason = "reactivation approved"
        result.new_state = ShutdownState.RUNNING.value
        return result

    # ------------------------------------------------------------------
    # UC-308 Champion/Challenger experiment containment
    # ------------------------------------------------------------------
    def stop_experiment(
        self,
        experiment_id: str,
        trace_id: Optional[str] = None,
        rollback_fn: Optional[Callable[[], Dict[str, Any]]] = None,
        reason: str = "uc308_experiment_containment",
    ) -> ShutdownStatus:
        """Narrow safe-shutdown entry point for a UC-308 experiment.

        If the coordinator is already RUNNING it registers the optional rollback
        function under the experiment identifier and initiates a normal shutdown.
        If the coordinator is already shutting down it returns the current
        terminal status, preserving idempotency.
        """
        if rollback_fn is not None:
            self._rollback_registry.register(
                name=f"experiment_{experiment_id}_rollback",
                rollback_fn=rollback_fn,
                metadata={"experiment_id": experiment_id, "trace_id": trace_id or ""},
            )
        if self._state != ShutdownState.RUNNING:
            return self._build_status()
        shutdown_id = f"uc308-{experiment_id}-{uuid.uuid4().hex[:8]}"
        return self.initiate_shutdown(reason=reason, shutdown_id=shutdown_id, trace_id=trace_id)
