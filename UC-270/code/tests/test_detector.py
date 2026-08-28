"""Tests de detección y clasificación de conflictos."""
from __future__ import annotations

from conflict_detector import ConflictDetector
from models import ConflictSeverity, ConflictType, ResourceClaim


def test_no_conflict_single_claim() -> None:
    detector = ConflictDetector()
    claims = [ResourceClaim(agent_name="a", resource_id="R1", need=0.5, priority=5, flexibility=0.5, willingness=0.5)]
    conflicts = detector.detect(claims)
    assert len(conflicts) == 0


def test_resource_contention_detected() -> None:
    detector = ConflictDetector()
    claims = [
        ResourceClaim(agent_name="a", resource_id="GPU_1", need=0.8, priority=7, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="b", resource_id="GPU_1", need=0.7, priority=7, flexibility=0.5, willingness=0.5),
    ]
    conflicts = detector.detect(claims)
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.resource_contention
    assert set(conflicts[0].claimants) == {"a", "b"}


def test_severity_critical_for_high_priority_and_need() -> None:
    detector = ConflictDetector()
    claims = [
        ResourceClaim(agent_name="a", resource_id="R1", need=0.9, priority=9, flexibility=0.3, willingness=0.5),
        ResourceClaim(agent_name="b", resource_id="R1", need=0.8, priority=9, flexibility=0.3, willingness=0.5),
    ]
    conflicts = detector.detect(claims)
    assert len(conflicts) == 1
    assert conflicts[0].severity == ConflictSeverity.critical


def test_multiple_resources_detected_independently() -> None:
    detector = ConflictDetector()
    claims = [
        ResourceClaim(agent_name="a", resource_id="R1", need=0.8, priority=5, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="b", resource_id="R1", need=0.6, priority=5, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="c", resource_id="R2", need=0.7, priority=6, flexibility=0.5, willingness=0.5),
        ResourceClaim(agent_name="d", resource_id="R2", need=0.9, priority=6, flexibility=0.5, willingness=0.5),
    ]
    conflicts = detector.detect(claims)
    assert len(conflicts) == 2
    resources = {c.resource_id for c in conflicts}
    assert resources == {"R1", "R2"}
