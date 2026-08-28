"""Tests de la pizarra compartida."""
from __future__ import annotations

from blackboard import SharedBlackboard
from models import BlackboardEntry, KnowledgeCategory


def test_write_and_read() -> None:
    bb = SharedBlackboard()
    entry = BlackboardEntry(key="k1", category=KnowledgeCategory.flight_facts, value="test", author="a", confidence=0.9)
    bb.write(entry)
    result = bb.read("k1")
    assert result is not None
    assert result.value == "test"


def test_read_returns_highest_confidence() -> None:
    bb = SharedBlackboard()
    bb.write(BlackboardEntry(key="k1", category=KnowledgeCategory.price_intel, value="low", author="a", confidence=0.6))
    bb.write(BlackboardEntry(key="k1", category=KnowledgeCategory.price_intel, value="high", author="b", confidence=0.9))
    result = bb.read("k1")
    assert result is not None
    assert result.value == "high"


def test_read_filters_by_min_confidence() -> None:
    bb = SharedBlackboard()
    bb.write(BlackboardEntry(key="k1", category=KnowledgeCategory.risk_assessment, value="risky", author="a", confidence=0.3))
    result = bb.read("k1", min_confidence=0.5)
    assert result is None


def test_read_category() -> None:
    bb = SharedBlackboard()
    bb.write(BlackboardEntry(key="a", category=KnowledgeCategory.flight_facts, value=1, author="x", confidence=0.8))
    bb.write(BlackboardEntry(key="b", category=KnowledgeCategory.flight_facts, value=2, author="y", confidence=0.9))
    bb.write(BlackboardEntry(key="c", category=KnowledgeCategory.price_intel, value=3, author="z", confidence=0.7))
    results = bb.read_category(KnowledgeCategory.flight_facts)
    assert len(results) == 2


def test_subscribe_notifies() -> None:
    bb = SharedBlackboard()
    received = []
    bb.subscribe(KnowledgeCategory.negotiation_state, lambda e: received.append(e))
    bb.write(BlackboardEntry(key="n1", category=KnowledgeCategory.negotiation_state, value="offer", author="a", confidence=1.0))
    assert len(received) == 1


def test_history_tracks_all_writes() -> None:
    bb = SharedBlackboard()
    bb.write(BlackboardEntry(key="a", category=KnowledgeCategory.flight_facts, value=1, author="x", confidence=0.8))
    bb.write(BlackboardEntry(key="b", category=KnowledgeCategory.flight_facts, value=2, author="y", confidence=0.9))
    assert len(bb.history) == 2
