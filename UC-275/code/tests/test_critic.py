"""Tests del SelfCritic para UC-275."""
from __future__ import annotations

from critic import SelfCritic
from models import CauseCategory, OutcomeObservation, ReflectionOutcome, SelfEvaluation


def _critic():
    return SelfCritic()


def _eval(score=0.4, severity=0.5, deviations=None):
    return SelfEvaluation(
        trace_id="t1", outcome=ReflectionOutcome.POOR, score=score,
        metric_breakdown={}, expectations_met=False,
        deviations=deviations or ["deviation"], severity=severity,
    )


def _obs(**metrics):
    return OutcomeObservation(
        trace_id="t1", actual_outcome={}, expected_outcome={}, metrics=metrics,
    )


def test_model_error_detected():
    c = _critic()
    obs = _obs(prediction_error=0.5, model_confidence=0.3)
    result = c.analyze(_eval(), obs)
    assert result.category == CauseCategory.model_error


def test_data_stale_detected():
    c = _critic()
    obs = _obs(data_age_seconds=500, market_volatility=0.7)
    result = c.analyze(_eval(), obs)
    assert result.category == CauseCategory.data_stale


def test_execution_error_detected():
    c = _critic()
    obs = _obs(slippage=0.1, latency_ms=2000)
    result = c.analyze(_eval(), obs)
    assert result.category == CauseCategory.execution_error


def test_external_shock_detected():
    c = _critic()
    obs = _obs(market_regime_change=0.9, black_swan_indicator=0.8)
    result = c.analyze(_eval(), obs)
    assert result.category == CauseCategory.external_shock


def test_strategy_flaw_detected():
    c = _critic()
    obs = _obs(opportunity_cost=0.4, relative_performance=0.5)
    result = c.analyze(_eval(), obs)
    assert result.category == CauseCategory.strategy_flaw


def test_parameter_miscalibration():
    c = _critic()
    obs = _obs(risk_realized=0.8, risk_expected=0.3)
    result = c.analyze(_eval(), obs)
    assert result.category == CauseCategory.parameter_miscalibration


def test_fallback_high_severity():
    c = _critic()
    obs = _obs()  # no metrics trigger heuristics
    evaluation = _eval(severity=0.8)
    result = c.analyze(evaluation, obs)
    assert result.category == CauseCategory.execution_error


def test_fallback_many_deviations():
    c = _critic()
    obs = _obs()
    evaluation = _eval(severity=0.4, deviations=["d1", "d2", "d3"])
    result = c.analyze(evaluation, obs)
    assert result.category == CauseCategory.parameter_miscalibration


def test_confidence_populated():
    c = _critic()
    obs = _obs(prediction_error=0.5, model_confidence=0.3)
    result = c.analyze(_eval(), obs)
    assert 0.0 <= result.confidence <= 1.0


def test_contributing_factors():
    c = _critic()
    obs = _obs(prediction_error=0.5, model_confidence=0.3,
               data_age_seconds=500, market_volatility=0.7)
    result = c.analyze(_eval(), obs)
    # Should have contributing factors since multiple heuristics fire
    assert isinstance(result.contributing_factors, list)
