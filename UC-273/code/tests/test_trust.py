"""Tests del trust scoring bayesiano."""
from __future__ import annotations

from config import TrustConfig
from trust import TrustRegistry, TrustScore


def test_initial_trust_is_half():
    score = TrustScore()
    assert score.trust == 0.5


def test_success_increases_trust():
    score = TrustScore()
    score.record_success()
    assert score.trust > 0.5


def test_failure_decreases_trust():
    score = TrustScore()
    score.record_failure()
    assert score.trust < 0.5


def test_lower_bound():
    score = TrustScore(alpha=10, beta=2)
    lb = score.lower_bound
    assert 0 < lb < score.trust


def test_registry_record_success():
    reg = TrustRegistry(TrustConfig(quarantine_threshold=0.3, trusted_threshold=0.7))
    trust = reg.record("agent_a", True)
    assert trust > 0.5


def test_registry_quarantine_on_failures():
    reg = TrustRegistry(TrustConfig(quarantine_threshold=0.3, trusted_threshold=0.7, failure_weight_multiplier=3.0))
    for _ in range(20):
        reg.record("bad_agent", False, weight=1.0)
    assert reg.is_quarantined("bad_agent")


def test_registry_trusted_agents():
    reg = TrustRegistry(TrustConfig(quarantine_threshold=0.3, trusted_threshold=0.7))
    for _ in range(20):
        reg.record("good_agent", True)
    trusted = reg.get_trusted_agents()
    assert "good_agent" in trusted


def test_suspicious_agents():
    reg = TrustRegistry()
    for _ in range(5):
        reg.record("sus_agent", False)
    sus = reg.get_suspicious_agents()
    agents = [a for a, _ in sus]
    assert "sus_agent" in agents


def test_get_score_model():
    reg = TrustRegistry()
    reg.record("test_agent", True)
    model = reg.get_score_model("test_agent")
    assert "agent_id" in model
    assert "trust" in model
    assert model["trust"] > 0.5
