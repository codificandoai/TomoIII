"""Tests unitarios del evaluador de tres niveles de UC-307."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from config import THRESHOLDS
from evaluator import AgentPerformanceEvaluator
from models import DecisionAction, EfficiencyMetrics, EvaluationInput


@pytest.fixture
def evaluator():
    return AgentPerformanceEvaluator()


def test_normalize_quality_1_to_5(evaluator):
    assert evaluator.normalize_quality(5.0) == pytest.approx(1.0)
    assert evaluator.normalize_quality(2.5) == pytest.approx(0.5)
    assert evaluator.normalize_quality(1.0) == pytest.approx(0.2)


def test_normalize_quality_already_normalized(evaluator):
    assert evaluator.normalize_quality(0.8, scale=1.0) == pytest.approx(0.8)
    assert evaluator.normalize_quality(0.0, scale=1.0) == 0.0
    assert evaluator.normalize_quality(1.0, scale=1.0) == 1.0


def test_efficiency_score_perfect(evaluator):
    eff = EfficiencyMetrics(tokens_used=0, tool_calls=0, latency_seconds=0.0)
    assert evaluator.compute_efficiency_score(eff) == pytest.approx(1.0)


def test_efficiency_score_worst(evaluator):
    eff = EfficiencyMetrics(
        tokens_used=THRESHOLDS.max_tokens * 2,
        tool_calls=THRESHOLDS.max_tool_calls * 2,
        latency_seconds=THRESHOLDS.max_latency_seconds * 2,
    )
    assert evaluator.compute_efficiency_score(eff) == pytest.approx(0.0)


def test_compute_fitness_elite(evaluator):
    fitness = evaluator.compute_fitness(1.0, 1.0, 1.0)
    assert fitness == pytest.approx(1.0)


def test_compute_fitness_zero(evaluator):
    fitness = evaluator.compute_fitness(0.0, 0.0, 0.0)
    assert fitness == pytest.approx(0.0)


def test_evaluate_returns_actions(evaluator):
    payload = EvaluationInput(
        agent_id="test_agent",
        task_success_rate=0.95,
        quality_score=4.5,
        efficiency=EfficiencyMetrics(tokens_used=500, tool_calls=1, latency_seconds=0.5),
    )
    result = evaluator.evaluate(payload, population_size=5)
    assert result.agent_id == "test_agent"
    assert 0.0 <= result.fitness <= 1.0
    assert result.verdict in DecisionAction
    assert len(result.actions) >= 1
    assert result.reasoning


def test_evaluate_low_success_triggers_action(evaluator):
    payload = EvaluationInput(
        agent_id="bad_agent",
        task_success_rate=0.10,
        quality_score=1.0,
        efficiency=EfficiencyMetrics(tokens_used=6000, tool_calls=8, latency_seconds=12.0),
    )
    result = evaluator.evaluate(payload, population_size=5)
    assert DecisionAction.ELIMINATE in result.actions
