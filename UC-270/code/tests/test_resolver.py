"""Tests del pipeline completo de resolución de conflictos."""
from __future__ import annotations

import random

from conflict_resolver import ConflictManager
from models import AgentProfile, ResourceClaim, ResolutionStrategy


def test_prioritization_different_priorities() -> None:
    random.seed(42)
    manager = ConflictManager()
    claims = [
        ResourceClaim(agent_name="high", resource_id="R1", need=0.5, priority=9, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="low", resource_id="R1", need=0.9, priority=3, flexibility=0.9, willingness=0.9),
    ]
    profiles = {
        "high": AgentProfile(name="high", priority=9, flexibility=0.5, negotiation_skill=0.5),
        "low": AgentProfile(name="low", priority=3, flexibility=0.9, negotiation_skill=0.9),
    }
    outcomes = manager.resolve_all(claims, profiles)
    assert len(outcomes) == 1
    assert outcomes[0].winner == "high"
    assert outcomes[0].strategy == ResolutionStrategy.prioritization


def test_equal_priority_uses_negotiation_or_escalation() -> None:
    random.seed(42)
    manager = ConflictManager()
    claims = [
        ResourceClaim(agent_name="a", resource_id="R1", need=0.8, priority=7, flexibility=0.6, willingness=0.7),
        ResourceClaim(agent_name="b", resource_id="R1", need=0.7, priority=7, flexibility=0.5, willingness=0.6),
    ]
    profiles = {
        "a": AgentProfile(name="a", priority=7, flexibility=0.6, negotiation_skill=0.7, reputation=0.85),
        "b": AgentProfile(name="b", priority=7, flexibility=0.5, negotiation_skill=0.6, reputation=0.75),
    }
    outcomes = manager.resolve_all(claims, profiles)
    assert len(outcomes) == 1
    o = outcomes[0]
    assert o.strategy in (ResolutionStrategy.negotiation, ResolutionStrategy.escalation)
    assert o.winner is not None
    assert len(o.audit_trail) > 0


def test_commit_records_created() -> None:
    random.seed(42)
    manager = ConflictManager()
    claims = [
        ResourceClaim(agent_name="x", resource_id="GPU", need=0.8, priority=5, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="y", resource_id="GPU", need=0.7, priority=5, flexibility=0.5, willingness=0.5),
    ]
    profiles = {
        "x": AgentProfile(name="x", priority=5, flexibility=0.5, negotiation_skill=0.5),
        "y": AgentProfile(name="y", priority=5, flexibility=0.5, negotiation_skill=0.5),
    }
    outcomes = manager.resolve_all(claims, profiles)
    assert len(outcomes) == 1
    assert len(outcomes[0].commits) >= 1


def test_no_conflict_no_outcome() -> None:
    manager = ConflictManager()
    claims = [
        ResourceClaim(agent_name="a", resource_id="R1", need=0.5, priority=5, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="b", resource_id="R2", need=0.5, priority=5, flexibility=0.5, willingness=0.5),
    ]
    outcomes = manager.resolve_all(claims, {})
    assert len(outcomes) == 0
