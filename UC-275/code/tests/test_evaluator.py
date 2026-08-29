"""Tests del MetricEvaluator para UC-275."""
from __future__ import annotations

from evaluator import MetricEvaluator
from models import ReflectionOutcome


def _evaluator():
    return MetricEvaluator(
        metric_weights={"correctness": 0.4, "completeness": 0.25, "clarity": 0.2, "efficiency": 0.15},
        thresholds={"correctness": (0.5, 0.8), "completeness": (0.4, 0.7)},
    )


def test_evaluate_perfect_score():
    ev = _evaluator()
    result = ev.evaluate(
        actual={"correctness": 1.0, "completeness": 1.0, "clarity": 1.0, "efficiency": 1.0},
        expected={"correctness": 0.8, "completeness": 0.7, "clarity": 0.7, "efficiency": 0.7},
    )
    assert result.score >= 0.85
    assert result.outcome in (ReflectionOutcome.GOOD, ReflectionOutcome.EXCELLENT)


def test_evaluate_poor_score():
    ev = _evaluator()
    result = ev.evaluate(
        actual={"correctness": 0.2, "completeness": 0.1, "clarity": 0.2, "efficiency": 0.1},
        expected={"correctness": 0.8, "completeness": 0.7, "clarity": 0.7, "efficiency": 0.7},
    )
    assert result.score < 0.3
    assert result.outcome in (ReflectionOutcome.POOR, ReflectionOutcome.FAILURE)


def test_evaluate_with_deviations():
    ev = _evaluator()
    result = ev.evaluate(
        actual={"correctness": 0.3, "completeness": 0.3, "clarity": 0.8, "efficiency": 0.7},
        expected={"correctness": 0.8, "completeness": 0.8, "clarity": 0.7, "efficiency": 0.7},
    )
    assert len(result.deviations) > 0
    assert result.expectations_met is False


def test_evaluate_needs_reflection():
    ev = _evaluator()
    result = ev.evaluate(
        actual={"correctness": 0.4, "completeness": 0.5, "clarity": 0.5, "efficiency": 0.5},
        expected={"correctness": 0.8, "completeness": 0.8, "clarity": 0.8, "efficiency": 0.8},
    )
    assert result.needs_reflection is True


def test_evaluate_no_reflection_needed():
    ev = _evaluator()
    result = ev.evaluate(
        actual={"correctness": 0.9, "completeness": 0.9, "clarity": 0.9, "efficiency": 0.9},
        expected={"correctness": 0.8, "completeness": 0.8, "clarity": 0.8, "efficiency": 0.8},
    )
    assert result.needs_reflection is False


def test_evaluate_text_output():
    ev = _evaluator()
    result = ev.evaluate_text_output({
        "correctness": 0.9, "completeness": 0.8, "clarity": 0.85, "efficiency": 0.7,
    })
    assert result.score > 0.7
    assert result.outcome in (ReflectionOutcome.GOOD, ReflectionOutcome.EXCELLENT)


def test_evaluate_text_output_low():
    ev = _evaluator()
    result = ev.evaluate_text_output({
        "correctness": 0.2, "completeness": 0.3, "clarity": 0.1, "efficiency": 0.2,
    })
    assert result.score < 0.3


def test_weights_normalized():
    ev = MetricEvaluator({"a": 2.0, "b": 8.0})
    assert abs(ev.weights["a"] - 0.2) < 1e-9
    assert abs(ev.weights["b"] - 0.8) < 1e-9


def test_score_metric_zero_expected():
    ev = _evaluator()
    assert ev._score_metric("test", 0.0, 0.0) == 1.0
    assert ev._score_metric("test", 0.5, 0.0) == 0.0
