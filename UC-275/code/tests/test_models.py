"""Tests de modelos para UC-275."""
from __future__ import annotations

from models import (
    ActionTrace,
    CauseCategory,
    OutcomeObservation,
    ReflectionEpisode,
    ReflectionOutcome,
    RefinementProposal,
    RootCauseAnalysis,
    SelfEvaluation,
)


def test_action_trace_creation():
    trace = ActionTrace(agent_id="agent_1", action_type="trade",
                        action_params={"risk": 0.5})
    assert trace.agent_id == "agent_1"
    assert trace.action_type == "trade"
    assert len(trace.trace_id) == 16


def test_outcome_observation():
    obs = OutcomeObservation(
        trace_id="t1",
        actual_outcome={"profit": 100},
        expected_outcome={"profit": 200},
        metrics={"correctness": 0.5},
    )
    assert obs.metrics["correctness"] == 0.5


def test_self_evaluation_needs_reflection_low_score():
    ev = SelfEvaluation(
        trace_id="t1", outcome=ReflectionOutcome.POOR, score=0.4,
        metric_breakdown={"correctness": 0.4}, expectations_met=False,
        deviations=["low score"], severity=0.3,
    )
    assert ev.needs_reflection is True


def test_self_evaluation_no_reflection_high_score():
    ev = SelfEvaluation(
        trace_id="t1", outcome=ReflectionOutcome.EXCELLENT, score=0.95,
        metric_breakdown={"correctness": 0.95}, expectations_met=True,
        deviations=[], severity=0.0,
    )
    assert ev.needs_reflection is False


def test_self_evaluation_needs_reflection_high_severity():
    ev = SelfEvaluation(
        trace_id="t1", outcome=ReflectionOutcome.GOOD, score=0.75,
        metric_breakdown={}, expectations_met=False,
        deviations=["deviation"], severity=0.6,
    )
    assert ev.needs_reflection is True


def test_refinement_proposal_net_benefit():
    rp = RefinementProposal(
        trace_id="t1", iteration=1,
        proposed_changes={"risk": 0.3},
        rationale="reduce risk",
        expected_improvement=0.3,
        risk_of_change=0.1,
    )
    assert abs(rp.net_benefit - 0.2) < 1e-9


def test_root_cause_analysis():
    rca = RootCauseAnalysis(
        trace_id="t1", primary_cause="Model error",
        contributing_factors=["data issue"],
        category=CauseCategory.model_error,
        confidence=0.8,
    )
    assert rca.category == CauseCategory.model_error


def test_reflection_episode_hash():
    trace = ActionTrace(agent_id="a", action_type="t", action_params={})
    obs = OutcomeObservation(trace_id="t1", actual_outcome={},
                            expected_outcome={}, metrics={})
    ev = SelfEvaluation(
        trace_id="t1", outcome=ReflectionOutcome.GOOD, score=0.75,
        metric_breakdown={}, expectations_met=True, deviations=[], severity=0.0,
    )
    ep = ReflectionEpisode(
        agent_id="a", trace_id="t1", action=trace,
        observation=obs, evaluation=ev,
        final_outcome=ReflectionOutcome.GOOD, final_score=0.75,
    )
    h = ep.compute_hash()
    assert len(h) == 64  # SHA-256 hex


def test_reflection_outcome_values():
    assert ReflectionOutcome.EXCELLENT.value == "excellent"
    assert ReflectionOutcome.FAILURE.value == "failure"


def test_cause_category_values():
    assert CauseCategory.model_error.value == "model_error"
    assert CauseCategory.external_shock.value == "external_shock"
