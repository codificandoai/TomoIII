"""Tests del motor de negociación."""
from __future__ import annotations

import random

from config import NegotiationConfig
from models import AgentProfile, DetectedConflict, ConflictType, ConflictSeverity, ResourceClaim
from negotiation import NegotiationEngine


def _make_conflict(agents: list[str], resource: str = "R1") -> DetectedConflict:
    claims = [
        ResourceClaim(agent_name=a, resource_id=resource, need=0.7, priority=5, flexibility=0.5, willingness=0.5)
        for a in agents
    ]
    return DetectedConflict(
        conflict_type=ConflictType.resource_contention,
        severity=ConflictSeverity.medium,
        resource_id=resource,
        claimants=agents,
        claims=claims,
    )


def _make_profiles(agents: list[str]) -> dict[str, AgentProfile]:
    return {
        a: AgentProfile(name=a, priority=5, flexibility=0.6, negotiation_skill=0.7, reputation=0.8)
        for a in agents
    }


def test_negotiation_reaches_agreement() -> None:
    random.seed(1)
    config = NegotiationConfig(max_rounds=10, agreement_base_prob=0.5, concession_rate=0.15)
    engine = NegotiationEngine(config)
    conflict = _make_conflict(["a", "b"])
    profiles = _make_profiles(["a", "b"])
    result = engine.negotiate(conflict, profiles)
    assert result.total_rounds >= 1
    assert result.agreement_reached is True
    assert result.final_allocation is not None
    assert abs(sum(result.final_allocation.values()) - 1.0) < 0.01


def test_negotiation_multiple_rounds() -> None:
    config = NegotiationConfig(max_rounds=3, agreement_base_prob=0.0, concession_rate=0.01)
    random.seed(99)
    engine = NegotiationEngine(config)
    conflict = _make_conflict(["x", "y"])
    profiles = _make_profiles(["x", "y"])
    result = engine.negotiate(conflict, profiles)
    assert result.total_rounds <= 3
    assert len(result.rounds) <= 3
