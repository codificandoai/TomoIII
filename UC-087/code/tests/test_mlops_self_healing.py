"""Tests para MLOpsSelfHealingOrchestrator."""
import os
import tempfile

import pytest

from mlops_self_healing_orchestrator import (
    HealingAction,
    MLOpsSelfHealingOrchestrator,
)
from models_087 import DataPoint, MLSecOpsConfig


def _make_data(n=60, clean=True):
    import random
    rng = random.Random(42)
    data = []
    for _ in range(n):
        features = [rng.gauss(0, 1) for _ in range(4)]
        label = 1 if sum(features[:2]) > 0 else 0
        data.append(DataPoint(features=features, label=label))
    if not clean:
        for item in data[:10]:
            item.features[0] = 100.0
            item.label = 1
    return data


@pytest.fixture
def orchestrator():
    tmpdir = tempfile.mkdtemp()
    return MLOpsSelfHealingOrchestrator(
        config=MLSecOpsConfig(
            min_samples_for_training=20,
            canary_traffic_ratio=0.05,
            max_failed_retrain_attempts=3,
        ),
        rollback_manager=None,
        cache_predictor=lambda q: 0.5,
    )


def test_decide_rollback_when_no_baseline(orchestrator):
    # Sin versión promocionada, siempre escala
    orchestrator.rollback.versions = []
    action = orchestrator.decide_action("drift", "critical", 0.5, _make_data(60))
    assert action == HealingAction.ESCALATE


def test_decide_retrain_on_critical_with_data(orchestrator):
    # Simular baseline promocionado
    orchestrator.rollback.save_candidate({"fake": True}, metrics={"baseline": True})
    promoted = orchestrator.rollback.get_promoted()
    if promoted is None:
        orchestrator.rollback.promote(orchestrator.rollback.versions[0].version_id)
    action = orchestrator.decide_action("drift", "critical", 0.5, _make_data(60))
    assert action == HealingAction.RETRAIN


def test_decide_rollback_on_critical_without_data(orchestrator):
    orchestrator.rollback.save_candidate({"fake": True}, metrics={"baseline": True})
    orchestrator.rollback.promote(orchestrator.rollback.versions[0].version_id)
    action = orchestrator.decide_action("drift", "critical", 0.5, None)
    assert action == HealingAction.ROLLBACK


def test_decide_fallback_cache_on_degraded(orchestrator):
    orchestrator.rollback.save_candidate({"fake": True}, metrics={"baseline": True})
    orchestrator.rollback.promote(orchestrator.rollback.versions[0].version_id)
    action = orchestrator.decide_action("drift", "degraded", 0.3, _make_data(60))
    assert action == HealingAction.FALLBACK_CACHE


def test_handle_critical_triggers_rollback(orchestrator):
    orchestrator.rollback.save_candidate({"fake": True}, metrics={"baseline": True})
    orchestrator.rollback.promote(orchestrator.rollback.versions[0].version_id)
    event = orchestrator.handle_signal("concept_drift", "critical", "agent-1", 0.9)
    assert event.action == HealingAction.ROLLBACK
    assert event.requires_approval


def test_handle_degraded_triggers_cache_fallback(orchestrator):
    orchestrator.rollback.save_candidate({"fake": True}, metrics={"baseline": True})
    orchestrator.rollback.promote(orchestrator.rollback.versions[0].version_id)
    event = orchestrator.handle_signal("quality_drift", "degraded", "agent-1", 0.5, query=[1.0, 2.0])
    assert event.action == HealingAction.FALLBACK_CACHE
    assert event.evidence.get("prediction") == 0.5


def test_retrain_creates_candidate(orchestrator):
    data = _make_data(60)
    result = orchestrator.retrain(data, "agent-1")
    assert result is not None
    assert "version_id" in result
    assert orchestrator.rollback.versions


def test_canary_and_promote(orchestrator):
    data = _make_data(60)
    retrain = orchestrator.retrain(data, "agent-1")
    version_id = retrain["version_id"]
    canary = orchestrator.canary(version_id, "agent-1")
    assert canary["status"] == "canary"
    promoted = orchestrator.promote(version_id, "agent-1")
    assert promoted is not None
    assert promoted["status"] == "promoted"


def test_rollback_safe(orchestrator):
    data = _make_data(60)
    retrain = orchestrator.retrain(data, "agent-1")
    version_id = retrain["version_id"]
    orchestrator.promote(version_id, "agent-1")
    new_version = orchestrator.rollback.save_candidate({"fake": True})
    orchestrator.rollback.promote(new_version.version_id)
    rolled = orchestrator.rollback_safe("agent-1", version_id)
    assert rolled["version_id"] == version_id
