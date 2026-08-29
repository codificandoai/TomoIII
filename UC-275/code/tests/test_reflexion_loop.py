"""Tests del ReflexionLoop y SelfReflectiveAgent para UC-275."""
from __future__ import annotations

from critic import SelfCritic
from evaluator import MetricEvaluator
from memory import ReflectionMemory
from models import ActionTrace, OutcomeObservation, ReflectionOutcome
from refiner import SelfRefiner
from reflexion_loop import ReflexionLoop, SelfReflectiveAgent


def _loop(agent_id="test_agent", max_iterations=3, threshold=0.8):
    memory = ReflectionMemory()
    evaluator = MetricEvaluator({
        "correctness": 0.4, "completeness": 0.25,
        "clarity": 0.2, "efficiency": 0.15,
    })
    return ReflexionLoop(
        agent_id=agent_id,
        evaluator=evaluator,
        critic=SelfCritic(),
        refiner=SelfRefiner(),
        memory=memory,
        max_iterations=max_iterations,
        convergence_threshold=threshold,
    )


def test_execute_simple_reflection():
    loop = _loop()
    expected = {"correctness": 0.7, "completeness": 0.6, "clarity": 0.6, "efficiency": 0.6}

    call_count = [0]
    def action_fn(params):
        call_count[0] += 1
        base = 0.5 + call_count[0] * 0.15
        return {k: min(1.0, base) for k in expected}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics=result,
        )

    episode = loop.execute_with_reflection(
        action_fn=action_fn, observe_fn=observe_fn,
        action_params={"type": "trade"}, expected_outcome=expected,
    )

    assert episode.final_score is not None
    assert episode.final_outcome is not None
    assert episode.reflection_hash is not None
    assert len(episode.reflection_hash) == 64


def test_converges_early():
    loop = _loop(threshold=0.5)
    expected = {"correctness": 0.5, "completeness": 0.5}

    def action_fn(params):
        return {"correctness": 0.9, "completeness": 0.9}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics=result,
        )

    episode = loop.execute_with_reflection(
        action_fn=action_fn, observe_fn=observe_fn,
        action_params={"type": "trade"}, expected_outcome=expected,
    )

    # Should converge on first try
    assert episode.iterations == 0


def test_max_iterations_respected():
    loop = _loop(max_iterations=2, threshold=0.99)
    expected = {"correctness": 0.99, "completeness": 0.99}

    def action_fn(params):
        return {"correctness": 0.3, "completeness": 0.3}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics=result,
        )

    episode = loop.execute_with_reflection(
        action_fn=action_fn, observe_fn=observe_fn,
        action_params={"type": "trade"}, expected_outcome=expected,
    )

    assert episode.iterations <= 2


def test_episode_stored_in_memory():
    loop = _loop()
    expected = {"correctness": 0.7}

    def action_fn(params):
        return {"correctness": 0.8}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics=result,
        )

    loop.execute_with_reflection(
        action_fn=action_fn, observe_fn=observe_fn,
        action_params={"type": "trade"}, expected_outcome=expected,
    )

    assert len(loop.memory.episodes) >= 1


def test_refinements_tracked():
    loop = _loop(max_iterations=3, threshold=0.99)
    expected = {"correctness": 0.99}

    call_count = [0]
    def action_fn(params):
        call_count[0] += 1
        return {"correctness": 0.3 + call_count[0] * 0.1}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics=result,
        )

    episode = loop.execute_with_reflection(
        action_fn=action_fn, observe_fn=observe_fn,
        action_params={"type": "trade"}, expected_outcome=expected,
    )

    if episode.iterations > 0:
        assert len(episode.refinements) > 0


# ============================================================
# SelfReflectiveAgent tests
# ============================================================

def test_self_reflective_agent_default():
    agent = SelfReflectiveAgent(agent_id="test")
    result = agent.run("Write a hello world function")
    assert "output" in result
    assert "score" in result
    assert "iterations" in result
    assert result["iterations"] >= 1


def test_self_reflective_agent_custom_criteria():
    agent = SelfReflectiveAgent(
        agent_id="test",
        criteria={"accuracy": 0.5, "speed": 0.5},
    )
    result = agent.run("Optimize a sorting algorithm")
    assert "score" in result


def test_self_reflective_agent_with_custom_generate():
    def my_gen(prompt):
        return "custom output"

    agent = SelfReflectiveAgent(
        agent_id="test",
        generate_fn=my_gen,
    )
    result = agent.run("Test task")
    assert "output" in result


def test_self_reflective_agent_history():
    agent = SelfReflectiveAgent(agent_id="test")
    agent.run("Task 1")
    agent.run("Task 2")
    assert len(agent.history) == 2


def test_self_reflective_agent_accepts_when_score_high():
    def always_good_critique(task, output):
        return {
            "correctness": {"status": "PASS", "score": 0.95, "feedback": "ok"},
            "completeness": {"status": "PASS", "score": 0.9, "feedback": "ok"},
            "clarity": {"status": "PASS", "score": 0.9, "feedback": "ok"},
            "efficiency": {"status": "PASS", "score": 0.9, "feedback": "ok"},
        }

    agent = SelfReflectiveAgent(
        agent_id="test",
        threshold=0.8,
        critique_fn=always_good_critique,
    )
    result = agent.run("Easy task")
    assert result["accepted"] is True
    assert result["iterations"] == 1
