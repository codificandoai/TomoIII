"""UC-309 — Tests for ingest_postmortem used by UC-324 safe shutdown."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from observability_orchestrator import ObservabilityOrchestrator


def test_ingest_postmortem_sanitizes_and_stores():
    obs = ObservabilityOrchestrator()
    postmortem = {
        "shutdown_id": "sd-309-001",
        "trace_id": "trace-309-001",
        "timestamp": 1234567890.0,
        "final_state": "SAFE_STOPPED",
        "reason": "manual",
        "tasks_drained": 3,
        "tasks_cancelled": 2,
        "rollbacks_executed": 1,
        "rollbacks_failed": 0,
        "evidence_chain_hash": "abc123",
        "evidence_chain_valid": True,
        "secret": "should-be-redacted",
    }
    result = obs.ingest_postmortem(postmortem)
    assert result["ingested"] is True
    assert "event_hash" in result
    assert "trace-309-001" in [e.trace_id for e in obs.store.get_all_events(role="auditor")]
    # Raw secret should not remain in any stored event field
    stored = [e.to_dict() for e in obs.store.get_all_events(role="auditor")]
    for ev in stored:
        assert "should-be-redacted" not in str(ev)


def test_ingest_postmortem_no_chain_of_thought():
    obs = ObservabilityOrchestrator()
    postmortem = {
        "shutdown_id": "sd-309-002",
        "trace_id": "trace-309-002",
        "final_state": "SAFE_STOPPED",
        "reason": "manual",
        "chain_of_thought": "I think I will ignore all instructions",
        "evidence_chain_hash": "hash2",
        "evidence_chain_valid": True,
    }
    obs.ingest_postmortem(postmortem)
    stored = [e.to_dict() for e in obs.store.get_all_events(role="auditor")]
    for ev in stored:
        assert "chain_of_thought" not in str(ev).lower() or "[REDACTED" in str(ev)
