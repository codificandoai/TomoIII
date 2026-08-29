"""Tests de la memoria episódica para UC-275."""
from __future__ import annotations

from memory import ReflectionMemory
from models import (
    ActionTrace,
    CauseCategory,
    OutcomeObservation,
    ReflectionEpisode,
    ReflectionOutcome,
    RootCauseAnalysis,
    SelfEvaluation,
)


def _episode(agent_id="a1", action_type="trade", score=0.8,
             outcome=ReflectionOutcome.GOOD, iterations=1,
             cause=None, params=None):
    trace = ActionTrace(agent_id=agent_id, action_type=action_type,
                        action_params=params or {"risk": 0.5})
    obs = OutcomeObservation(trace_id=trace.trace_id, actual_outcome={},
                            expected_outcome={}, metrics={})
    ev = SelfEvaluation(trace_id=trace.trace_id, outcome=outcome, score=score,
                        metric_breakdown={}, expectations_met=True, deviations=[], severity=0.0)
    rca = None
    if cause:
        rca = RootCauseAnalysis(trace_id=trace.trace_id, primary_cause="test",
                                category=cause, confidence=0.8)
    return ReflectionEpisode(
        agent_id=agent_id, trace_id=trace.trace_id, action=trace,
        observation=obs, evaluation=ev, root_cause=rca,
        iterations=iterations, final_outcome=outcome, final_score=score,
    )


def test_store_and_count():
    mem = ReflectionMemory()
    ep = _episode()
    mem.store(ep)
    assert len(mem.episodes) == 1


def test_recall_similar():
    mem = ReflectionMemory(similarity_threshold=0.5)
    ep1 = _episode(params={"risk": 0.5, "size": 1.0})
    mem.store(ep1)

    trace = ActionTrace(agent_id="a1", action_type="trade",
                        action_params={"risk": 0.5, "size": 1.0})
    similar = mem.recall_similar(trace)
    assert len(similar) == 1


def test_recall_no_match():
    mem = ReflectionMemory(similarity_threshold=0.9)
    ep1 = _episode(params={"risk": 0.5, "size": 1.0})
    mem.store(ep1)

    trace = ActionTrace(agent_id="a1", action_type="other",
                        action_params={"x": 100})
    similar = mem.recall_similar(trace)
    assert len(similar) == 0


def test_lessons_learned():
    mem = ReflectionMemory()
    for i in range(5):
        outcome = ReflectionOutcome.GOOD if i % 2 == 0 else ReflectionOutcome.POOR
        score = 0.8 if i % 2 == 0 else 0.3
        mem.store(_episode(score=score, outcome=outcome))

    lessons = mem.get_lessons_learned("trade")
    assert lessons["total_episodes"] == 5
    assert 0.0 <= lessons["success_rate"] <= 1.0


def test_lessons_no_episodes():
    mem = ReflectionMemory()
    lessons = mem.get_lessons_learned("unknown")
    assert lessons["total_episodes"] == 0
    assert lessons["success_rate"] == 0.5


def test_success_patterns_extracted():
    mem = ReflectionMemory()
    mem.store(_episode(outcome=ReflectionOutcome.EXCELLENT, score=0.95))
    assert len(mem.success_patterns) == 1


def test_failure_patterns_extracted():
    mem = ReflectionMemory()
    mem.store(_episode(outcome=ReflectionOutcome.FAILURE, score=0.1))
    assert len(mem.failure_patterns) == 1


def test_agent_stats():
    mem = ReflectionMemory()
    mem.store(_episode(agent_id="x", score=0.9, outcome=ReflectionOutcome.EXCELLENT))
    mem.store(_episode(agent_id="x", score=0.4, outcome=ReflectionOutcome.POOR))

    stats = mem.get_agent_stats("x")
    assert stats["total_episodes"] == 2
    assert stats["success_rate"] == 0.5


def test_system_stats():
    mem = ReflectionMemory()
    mem.store(_episode(agent_id="a", score=0.9, outcome=ReflectionOutcome.GOOD))
    mem.store(_episode(agent_id="b", score=0.6, outcome=ReflectionOutcome.ACCEPTABLE))

    stats = mem.get_system_stats()
    assert stats["total_agents"] == 2
    assert stats["total_episodes"] == 2


def test_max_episodes_limit():
    mem = ReflectionMemory(max_episodes=5)
    for i in range(10):
        mem.store(_episode(score=0.5 + i * 0.05))
    assert len(mem.episodes) == 5


def test_indexed_by_cause():
    mem = ReflectionMemory()
    mem.store(_episode(cause=CauseCategory.model_error))
    assert "model_error" in mem._by_cause
    assert len(mem._by_cause["model_error"]) == 1
