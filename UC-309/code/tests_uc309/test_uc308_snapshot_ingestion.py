"""UC-309 tests for UC-308 Champion/Challenger experiment snapshot ingestion."""

import time

import pytest

from observability_orchestrator import ObservabilityOrchestrator


@pytest.fixture
def orch():
    return ObservabilityOrchestrator()


def _snapshot():
    return {
        "experiment_id": "cc-exp-1",
        "report_hash": "abcd1234" * 8,
        "state": "awaiting_approval",
        "recommended_action": "promote",
        "reason": "challenger is statistically superior",
        "champion_version": "1.0.0",
        "challenger_version": "2.0.0",
        "timestamp": time.time(),
    }


def test_ingest_uc308_experiment_snapshot_stores_canonical_event(orch):
    result = orch.ingest_uc308_experiment_snapshot(_snapshot())
    assert result["ingested"]
    assert result["event_hash"]
    assert result["trace_id"] == "cc-exp-1"
    events = orch.store.get_all_events()
    assert len(events) >= 1


def test_ingest_uc308_experiment_snapshot_sanitizes_secrets_and_cot(orch):
    snap = _snapshot()
    snap["chain_of_thought"] = "I think therefore I trade"
    snap["secret_key"] = "sk-1234567890abcdef"
    result = orch.ingest_uc308_experiment_snapshot(snap)
    assert result["ingested"]
    for ev in orch.store.get_all_events():
        raw = str(ev.to_dict())
        assert "sk-" not in raw
        assert "chain_of_thought" not in raw.lower()


def test_ingest_uc308_experiment_snapshot_updates_metrics(orch):
    orch.ingest_uc308_experiment_snapshot(_snapshot())
    metrics = orch.get_metrics()
    assert metrics  # basic sanity; at minimum metrics are recomputed
