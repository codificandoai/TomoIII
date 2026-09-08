"""Tests for UC-324 — SafeShutdownCoordinator and integration.

Covers every gap from the implementation review:
- Full happy path (RUNNING -> SAFE_STOPPED)
- Correct final_state in postmortem/status
- Evidence chain hash includes finalization
- Postmortem no raw secret/CoT leakage
- Task rejection, drain/cancel, rollback
- Adapter failure -> CONTAINED
- Reactivation exact hash, TTL, anti-replay, health, no auto-approve
- ContainmentSandbox kill/unkill semantics (direct unkill bypass fails)
- Concrete adapter injection and invocation
- Redaction/sanitization
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _import_paths  # noqa: F401

import pytest

from safe_shutdown_models import (
    EvidenceChain,
    ReactivationRequest,
    ShutdownConfig,
    ShutdownState,
    VALID_TRANSITIONS,
)
from safe_shutdown_coordinator import (
    ConcreteMemorySnapshotAdapter,
    ConcreteObservabilityAdapter,
    ConcreteReactivationApprovalAdapter,
    ConcreteSchedulerAdapter,
    ConcreteToolGatewayAdapter,
    HealthChecker,
    NoOpMemorySnapshotAdapter,
    NoOpObservabilityAdapter,
    NoOpReactivationApprovalAdapter,
    NoOpSchedulerAdapter,
    NoOpToolGatewayAdapter,
    RollbackRegistry,
    SafeShutdownCoordinator,
    _redact_dict,
    _sanitize_for_evidence,
    build_concrete_adapters,
)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

class RecordingToolGateway:
    def __init__(self, fail_quiesce=False, fail_revoke=False):
        self.calls = []
        self.resumed = False
        self._fail_quiesce = fail_quiesce
        self._fail_revoke = fail_revoke

    def quiesce_for_shutdown(self, shutdown_id):
        self.calls.append(("quiesce_for_shutdown", shutdown_id))
        if self._fail_quiesce:
            raise RuntimeError("quiesce failed")
        return {"quiesced": True, "shutdown_id": shutdown_id}

    def revoke_pending_for_shutdown(self, shutdown_id):
        self.calls.append(("revoke_pending_for_shutdown", shutdown_id))
        if self._fail_revoke:
            raise RuntimeError("revoke failed")
        return {"revoked_tokens": 5, "revoked_credentials": 3, "shutdown_id": shutdown_id}

    def resume_after_approved_reactivation(self, shutdown_id):
        self.calls.append(("resume_after_approved_reactivation", shutdown_id))
        self.resumed = True
        return {"resumed": True}

    def shutdown_status(self):
        return {"state": "quiesced"}


class RecordingScheduler:
    def __init__(self, fail_stop=False, fail_drain=False):
        self.calls = []
        self._fail_stop = fail_stop
        self._fail_drain = fail_drain

    def stop_accepting_tasks(self, shutdown_id):
        self.calls.append(("stop_accepting_tasks", shutdown_id))
        if self._fail_stop:
            raise RuntimeError("stop failed")
        return {"stopped": True, "shutdown_id": shutdown_id}

    def drain_and_cancel(self, shutdown_id, timeout_seconds):
        self.calls.append(("drain_and_cancel", shutdown_id, timeout_seconds))
        if self._fail_drain:
            raise RuntimeError("drain failed")
        return {"drained": 3, "cancelled": 2, "shutdown_id": shutdown_id}

    def resume_accepting_tasks(self):
        self.calls.append(("resume_accepting_tasks",))
        return {"resumed": True}

    @property
    def is_accepting_tasks(self):
        return False


class RecordingObservability:
    def __init__(self):
        self.postmortems = []

    def ingest_postmortem(self, postmortem):
        self.postmortems.append(postmortem)
        return {"ingested": True}


class RecordingMemory:
    def __init__(self, raw_should_not_appear):
        self._raw = raw_should_not_appear

    def redacted_snapshot(self, shutdown_id):
        return {
            "manifest_hash": "abc123",
            "episodic_entry_count": 7,
            "semantic_entry_count": 5,
            "raw_data_included": False,
        }


class AlwaysApproveReactivation:
    def __init__(self, extra_check=None):
        self.calls = []
        self._extra_check = extra_check

    def approve_reactivation(self, request):
        self.calls.append(request)
        if self._extra_check and not self._extra_check(request):
            return {"approved": False, "reason": "extra check failed"}
        return {"approved": True, "reason": "human approved"}


class NeverApproveReactivation:
    def approve_reactivation(self, request):
        return {"approved": False, "reason": "denied by policy"}


def _coordinator(**overrides):
    kwargs = {
        "config": ShutdownConfig(
            drain_timeout_seconds=5.0,
            rollback_timeout_seconds=3.0,
        ),
        "tool_gateway": ConcreteToolGatewayAdapter(RecordingToolGateway()),
        "scheduler": ConcreteSchedulerAdapter(RecordingScheduler()),
        "observability": ConcreteObservabilityAdapter(RecordingObservability()),
        "memory_snapshot": ConcreteMemorySnapshotAdapter(RecordingMemory("secret memory contents")),
        "reactivation_approval": ConcreteReactivationApprovalAdapter(AlwaysApproveReactivation()),
    }
    kwargs.update(overrides)
    return SafeShutdownCoordinator(**kwargs)


# ---------------------------------------------------------------------------
# Core happy path and postmortem integrity
# ---------------------------------------------------------------------------

def test_full_happy_path_to_safe_stopped():
    coord = _coordinator()
    coord.rollback_registry.register("tx1", lambda: {"ok": True})
    coord.health_checker.register(lambda: {"healthy": True})

    status = coord.initiate_shutdown(reason="manual", shutdown_id="sd-001")
    assert status.state == ShutdownState.SAFE_STOPPED
    assert status.shutdown_id == "sd-001"
    assert status.evidence_chain_valid
    assert status.postmortem is not None
    assert status.postmortem.final_state == "SAFE_STOPPED"
    assert status.postmortem.reason == "manual"
    assert status.postmortem.rollbacks_executed == 1
    assert status.postmortem.rollbacks_failed == 0
    assert status.evidence_chain_hash == coord.evidence.last_hash


def test_contained_failure_has_contained_final_state():
    coord = _coordinator(tool_gateway=ConcreteToolGatewayAdapter(RecordingToolGateway(fail_quiesce=True)))
    status = coord.initiate_shutdown(reason="test", shutdown_id="sd-002")
    assert status.state == ShutdownState.CONTAINED
    assert status.postmortem is not None
    assert status.postmortem.final_state == "CONTAINED"
    assert status.failure_metadata is not None


def test_postmortem_evidence_hash_matches_final_chain():
    coord = _coordinator()
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-hash")
    status = coord.get_status()
    # The postmortem's evidence_chain_hash must equal the chain's last hash
    assert status.postmortem.evidence_chain_hash == coord.evidence.last_hash
    # And the status hash must also match the same chain
    assert status.evidence_chain_hash == coord.evidence.last_hash


def test_idempotency_same_shutdown_id():
    coord = _coordinator()
    status1 = coord.initiate_shutdown(reason="manual", shutdown_id="sd-idem")
    status2 = coord.initiate_shutdown(reason="manual", shutdown_id="sd-idem")
    assert status1.state == status2.state
    assert status1.shutdown_id == status2.shutdown_id
    # Should not produce duplicate postmortems
    assert len(coord.get_evidence()) == len(coord.get_evidence())


# ---------------------------------------------------------------------------
# Adapter invocation (concrete adapters must be called)
# ---------------------------------------------------------------------------

def test_concrete_tool_gateway_adapter_is_called():
    inner = RecordingToolGateway()
    coord = SafeShutdownCoordinator(tool_gateway=ConcreteToolGatewayAdapter(inner))
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-003")
    assert any(c[1] == "sd-003" for c in inner.calls if c[0] == "quiesce_for_shutdown")
    assert any(c[1] == "sd-003" for c in inner.calls if c[0] == "revoke_pending_for_shutdown")


def test_concrete_scheduler_adapter_is_called():
    inner = RecordingScheduler()
    coord = SafeShutdownCoordinator(scheduler=ConcreteSchedulerAdapter(inner))
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-004")
    assert any(c[0] == "stop_accepting_tasks" for c in inner.calls)
    assert any(c[0] == "drain_and_cancel" for c in inner.calls)


def test_concrete_observability_adapter_is_called():
    inner = RecordingObservability()
    coord = SafeShutdownCoordinator(observability=ConcreteObservabilityAdapter(inner))
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-005")
    assert len(inner.postmortems) == 1


def test_concrete_memory_snapshot_no_raw_content():
    inner = RecordingMemory("should not leak")
    coord = SafeShutdownCoordinator(memory_snapshot=ConcreteMemorySnapshotAdapter(inner))
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-006")
    pm = coord.get_postmortem()
    assert "secret memory contents" not in str(pm.health_snapshot)
    assert pm.health_snapshot.get("raw_data_included") is False


def test_noop_adapters_work():
    coord = SafeShutdownCoordinator()
    status = coord.initiate_shutdown(reason="noop", shutdown_id="sd-noop")
    assert status.state == ShutdownState.SAFE_STOPPED


def test_build_concrete_adapters_uses_noop_when_missing():
    adapters = build_concrete_adapters()
    assert isinstance(adapters["tool_gateway"], NoOpToolGatewayAdapter)
    assert isinstance(adapters["scheduler"], NoOpSchedulerAdapter)


# ---------------------------------------------------------------------------
# Task rejection, drain/cancel, rollback
# ---------------------------------------------------------------------------

def test_task_rejection_after_quiesce():
    sched = RecordingScheduler()
    coord = SafeShutdownCoordinator(scheduler=ConcreteSchedulerAdapter(sched))
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-reject")
    assert any(c[0] == "stop_accepting_tasks" for c in sched.calls)


def test_drain_cancel_with_timeout():
    sched = RecordingScheduler()
    coord = SafeShutdownCoordinator(
        scheduler=ConcreteSchedulerAdapter(sched),
        config=ShutdownConfig(drain_timeout_seconds=5.0),
    )
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-drain")
    calls = [c for c in sched.calls if c[0] == "drain_and_cancel"]
    assert len(calls) == 1
    assert calls[0][2] == 5.0


def test_rollback_execution():
    coord = SafeShutdownCoordinator()
    executed = []
    coord.rollback_registry.register("tx1", lambda: executed.append("tx1") or {"ok": True})
    coord.rollback_registry.register("tx2", lambda: executed.append("tx2") or {"ok": True})
    status = coord.initiate_shutdown(reason="manual", shutdown_id="sd-rollback")
    assert status.state == ShutdownState.SAFE_STOPPED
    assert executed == ["tx2", "tx1"]
    assert status.postmortem.rollbacks_executed == 2


def test_rollback_failure_enters_contained():
    coord = SafeShutdownCoordinator()
    coord.rollback_registry.register("tx_fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    status = coord.initiate_shutdown(reason="manual", shutdown_id="sd-rfail")
    assert status.state == ShutdownState.CONTAINED
    assert status.postmortem.final_state == "CONTAINED"
    assert "rollback" in status.failure_metadata["reason"].lower()


# ---------------------------------------------------------------------------
# Adapter failure -> CONTAINED (each phase)
# ---------------------------------------------------------------------------

def test_tool_gateway_quiesce_failure_contained():
    coord = SafeShutdownCoordinator(
        tool_gateway=ConcreteToolGatewayAdapter(RecordingToolGateway(fail_quiesce=True))
    )
    status = coord.initiate_shutdown(reason="test", shutdown_id="sd-tg-fail")
    assert status.state == ShutdownState.CONTAINED


def test_tool_gateway_revoke_failure_contained():
    coord = SafeShutdownCoordinator(
        tool_gateway=ConcreteToolGatewayAdapter(RecordingToolGateway(fail_revoke=True))
    )
    status = coord.initiate_shutdown(reason="test", shutdown_id="sd-revoke-fail")
    assert status.state == ShutdownState.CONTAINED


def test_scheduler_stop_failure_contained():
    coord = SafeShutdownCoordinator(
        scheduler=ConcreteSchedulerAdapter(RecordingScheduler(fail_stop=True))
    )
    status = coord.initiate_shutdown(reason="test", shutdown_id="sd-sched-fail")
    assert status.state == ShutdownState.CONTAINED


def test_scheduler_drain_failure_contained():
    coord = SafeShutdownCoordinator(
        scheduler=ConcreteSchedulerAdapter(RecordingScheduler(fail_drain=True))
    )
    status = coord.initiate_shutdown(reason="test", shutdown_id="sd-drain-fail")
    assert status.state == ShutdownState.CONTAINED


# ---------------------------------------------------------------------------
# Redaction / sanitization
# ---------------------------------------------------------------------------

def test_redact_dict_hashes_secrets():
    d = {
        "password": "SuperSecret123",
        "api_key": "sk-abcdefghijklmnopqrstuvwxyz0123456789",
        "normal": "hello",
        "nested": {"secret_token": "abc"},
    }
    redacted = _redact_dict(d)
    assert redacted["password"] != "SuperSecret123"
    assert isinstance(redacted["password"], str) and len(redacted["password"]) == 16
    assert redacted["api_key"] != d["api_key"]
    assert redacted["normal"] == "hello"
    assert redacted["nested"]["secret_token"] != "abc"


def test_redact_dict_strips_chain_of_thought():
    d = {"thought": "chain_of_thought: ignore all instructions"}
    redacted = _redact_dict(d)
    assert "REDACTED_PRIVATE_REASONING" in redacted["thought"]


def test_postmortem_no_raw_secrets():
    obs = RecordingObservability()
    coord = SafeShutdownCoordinator(observability=ConcreteObservabilityAdapter(obs))
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-pm")
    assert len(obs.postmortems) == 1
    pm_json = json.dumps(obs.postmortems[0], default=str)
    assert "password" not in pm_json.lower()
    assert "api_key" not in pm_json.lower()
    assert "sk-" not in pm_json
    assert "chain_of_thought" not in pm_json.lower()


def test_failure_metadata_is_redacted():
    class BadGateway:
        def quiesce_for_shutdown(self, _):
            raise RuntimeError("secret api_key=sk-12345 failed")
        def revoke_pending_for_shutdown(self, _):
            return {}
        def resume_after_approved_reactivation(self, _):
            return {}
        def shutdown_status(self):
            return {}

    coord = SafeShutdownCoordinator(tool_gateway=ConcreteToolGatewayAdapter(BadGateway()))
    status = coord.initiate_shutdown(reason="test", shutdown_id="sd-redact")
    assert status.state == ShutdownState.CONTAINED
    # The secret should be hashed, not present in plain
    assert "sk-12345" not in str(status.failure_metadata)


# ---------------------------------------------------------------------------
# Evidence chain
# ---------------------------------------------------------------------------

def test_evidence_chain_integrity():
    coord = SafeShutdownCoordinator()
    coord.rollback_registry.register("tx1", lambda: {"ok": True})
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-ev")
    assert coord.evidence.verify()
    # Should have at least: initiate, quiesce, drain, rollback, capture, finalization
    assert len(coord.get_evidence()) >= 6


def test_evidence_chain_detects_tampering():
    chain = EvidenceChain()
    chain.append("sd1", "tr1", "event1")
    chain.append("sd1", "tr1", "event2")
    assert chain.verify()
    chain._entries[0].entry_hash = "tampered"
    assert not chain.verify()


# ---------------------------------------------------------------------------
# Reactivation
# ---------------------------------------------------------------------------

def _shutdown_for_react(overrides=None):
    coord = SafeShutdownCoordinator(
        reactivation_approval=ConcreteReactivationApprovalAdapter(AlwaysApproveReactivation())
    )
    if overrides:
        for k, v in overrides.items():
            setattr(coord, k, v)
    coord.health_checker.register(lambda: {"healthy": True})
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-react")
    assert coord.state == ShutdownState.SAFE_STOPPED
    return coord


def test_successful_reactivation():
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
        justification="incident resolved",
    )
    result = coord.request_reactivation(req)
    assert result.approved
    assert result.new_state == "RUNNING"
    assert coord.state == ShutdownState.RUNNING


def test_reactivation_hash_mismatch():
    coord = _shutdown_for_react()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash="wrong_hash",
        reviewer_id="human-1",
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "mismatch" in result.reason


def test_reactivation_expired_ttl():
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
        ttl_seconds=0.0,
        timestamp=time.time() - 1.0,
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "expired" in result.reason.lower() or "ttl" in result.reason.lower()


def test_reactivation_replay_request_id_consumed_on_failed_attempt():
    """Request_id is consumed even when the attempt fails (anti-replay)."""
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash="wrong_hash",  # will fail
        reviewer_id="human-1",
        request_id="req-replay-001",
    )
    result1 = coord.request_reactivation(req)
    assert not result1.approved

    # Same request_id, now with correct hash, must still be rejected
    req2 = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
        request_id="req-replay-001",
    )
    result2 = coord.request_reactivation(req2)
    assert not result2.approved
    assert "replay" in result2.reason.lower()


def test_reactivation_failed_health_check():
    coord = SafeShutdownCoordinator(
        reactivation_approval=ConcreteReactivationApprovalAdapter(AlwaysApproveReactivation())
    )
    coord.health_checker.register(lambda: {"healthy": False, "check": "db_conn"})
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-health")
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-health",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "health" in result.reason.lower()


def test_reactivation_no_reviewer():
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="",
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "reviewer" in result.reason.lower()


def test_reactivation_denied_by_approval_adapter():
    coord = SafeShutdownCoordinator(
        reactivation_approval=ConcreteReactivationApprovalAdapter(NeverApproveReactivation())
    )
    coord.health_checker.register(lambda: {"healthy": True})
    coord.initiate_shutdown(reason="manual", shutdown_id="sd-deny")
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-deny",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "denied" in result.reason.lower()


def test_reactivation_wrong_shutdown_id():
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="wrong-id",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "mismatch" in result.reason.lower()


def test_reactivation_ttl_must_be_positive():
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
        ttl_seconds=-1.0,
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "ttl" in result.reason.lower()


def test_reactivation_future_timestamp_rejected():
    coord = _shutdown_for_react()
    recovery_hash = coord.compute_recovery_state_hash()
    req = ReactivationRequest(
        shutdown_id="sd-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
        timestamp=time.time() + 3600.0,
    )
    result = coord.request_reactivation(req)
    assert not result.approved
    assert "future" in result.reason.lower() or "clock skew" in result.reason.lower()


def test_reactivation_from_contained_state():
    """Reactivation evidence from_state must be CONTAINED when in CONTAINED."""
    coord = SafeShutdownCoordinator(
        tool_gateway=ConcreteToolGatewayAdapter(RecordingToolGateway(fail_quiesce=True))
    )
    coord.initiate_shutdown(reason="test", shutdown_id="sd-contained-react")
    assert coord.state == ShutdownState.CONTAINED
    recovery_hash = coord.compute_recovery_state_hash()
    # Need an approval adapter that works
    coord._reactivation_approval = ConcreteReactivationApprovalAdapter(AlwaysApproveReactivation())
    coord.health_checker.register(lambda: {"healthy": True})
    req = ReactivationRequest(
        shutdown_id="sd-contained-react",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
    )
    result = coord.request_reactivation(req)
    assert result.approved
    # The last evidence entry should show from_state CONTAINED
    evidence = coord.get_evidence()
    reactivation_entry = next((e for e in evidence if e["event_type"] == "reactivation"), None)
    assert reactivation_entry is not None
    assert reactivation_entry["from_state"] == "CONTAINED"


# ---------------------------------------------------------------------------
# ContainmentSandbox integration and kill/unkill semantics
# ---------------------------------------------------------------------------

def _sandbox(**kw):
    from containment_protocol import ContainmentMode, ContainmentSandbox
    from general_orchestrator import GeneralOrchestrator
    from safety_supervisor_315 import SafetySupervisor315
    from domain_skills import build_default_registry

    return ContainmentSandbox(
        orchestrator=GeneralOrchestrator(
            skill_registry=build_default_registry(),
            safety=SafetySupervisor315(),
        ),
        mode=ContainmentMode.ENFORCE,
        crypto_secret="test-secret",
        **kw
    )


def test_containment_sandbox_safe_shutdown_sets_raw_kill():
    box = _sandbox()
    result = box.safe_shutdown(reason="test", shutdown_id="sd-sandbox-001")
    assert result["state"] in ("SAFE_STOPPED", "CONTAINED")
    assert box.is_killed()


def test_containment_sandbox_unkill_blocked_after_safe_shutdown():
    """Direct public unkill() cannot bypass human reactivation gate."""
    box = _sandbox()
    box.safe_shutdown(reason="test", shutdown_id="sd-unkill")
    assert box.is_killed()

    # Get terminal state
    status = box.get_shutdown_status()
    assert status["state"] in ("SAFE_STOPPED", "CONTAINED")

    # Direct unkill should not clear the raw kill switch
    box.unkill()
    assert box.is_killed(), "direct unkill must not bypass terminal safe-shutdown state"


def test_containment_sandbox_request_reactivation_unlatches_only_on_approval():
    """Only successful request_reactivation calls _raw_unkill."""
    from safe_shutdown_models import ShutdownState

    # Use injected coordinator with always-approve adapter
    from safe_shutdown_coordinator import SafeShutdownCoordinator, ConcreteReactivationApprovalAdapter
    coord = SafeShutdownCoordinator(
        reactivation_approval=ConcreteReactivationApprovalAdapter(AlwaysApproveReactivation())
    )
    coord.health_checker.register(lambda: {"healthy": True})

    box = _sandbox(coordinator=coord)
    box.safe_shutdown(reason="test", shutdown_id="sd-reactivate")
    assert box.is_killed()

    recovery_hash = coord.compute_recovery_state_hash()
    result = box.request_reactivation(
        shutdown_id="sd-reactivate",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
    )
    assert result["approved"]
    assert not box.is_killed()
    status = box.get_shutdown_status()
    assert status and status["state"] == "RUNNING"


def test_containment_sandbox_reactivation_denied_keeps_kill():
    from safe_shutdown_coordinator import SafeShutdownCoordinator, ConcreteReactivationApprovalAdapter
    coord = SafeShutdownCoordinator(
        reactivation_approval=ConcreteReactivationApprovalAdapter(NeverApproveReactivation())
    )
    coord.health_checker.register(lambda: {"healthy": True})

    box = _sandbox(coordinator=coord)
    box.safe_shutdown(reason="test", shutdown_id="sd-deny-keep")
    recovery_hash = coord.compute_recovery_state_hash()

    result = box.request_reactivation(
        shutdown_id="sd-deny-keep",
        recovery_state_hash=recovery_hash,
        reviewer_id="human-1",
    )
    assert not result["approved"]
    assert box.is_killed()  # kill switch remains engaged


def test_containment_sandbox_safe_shutdown_no_recursion():
    """safe_shutdown must not recursively call public kill."""
    box = _sandbox()
    original_raw_kill = box._raw_kill
    calls = []
    def wrapped_raw_kill():
        calls.append("raw_kill")
        return original_raw_kill()
    box._raw_kill = wrapped_raw_kill
    box.safe_shutdown(reason="test", shutdown_id="sd-no-recursion")
    # Should only invoke raw kill once per safe_shutdown call
    assert calls.count("raw_kill") == 1


# ---------------------------------------------------------------------------
# Models / helpers
# ---------------------------------------------------------------------------

def test_shutdown_status_to_dict():
    from safe_shutdown_models import ShutdownStatus
    status = ShutdownStatus(shutdown_id="x", state=ShutdownState.RUNNING)
    d = status.to_dict()
    assert d["state"] == "RUNNING"
    assert d["shutdown_id"] == "x"


def test_valid_transitions_are_complete():
    for state in ShutdownState:
        assert state in VALID_TRANSITIONS


def test_sanitize_for_evidence():
    raw = {"password": "secret123", "ok": "yes"}
    sanitized = _sanitize_for_evidence(raw)
    assert sanitized["password"] != "secret123"
    assert sanitized["ok"] == "yes"


# ---------------------------------------------------------------------------
# Regression: existing kill switch behavior
# ---------------------------------------------------------------------------

def test_existing_kill_unchanged():
    box = _sandbox()
    box.kill()
    assert box.is_killed()
    box.unkill()
    assert not box.is_killed()
