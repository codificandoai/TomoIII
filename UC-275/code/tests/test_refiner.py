"""Tests del SelfRefiner para UC-275."""
from __future__ import annotations

from memory import ReflectionMemory
from models import CauseCategory, ReflectionOutcome, RootCauseAnalysis, SelfEvaluation
from refiner import SelfRefiner


def _eval(trace_id="t1"):
    return SelfEvaluation(
        trace_id=trace_id, outcome=ReflectionOutcome.POOR, score=0.4,
        metric_breakdown={}, expectations_met=False,
        deviations=["deviation"], severity=0.5,
    )


def _rca(category: CauseCategory):
    return RootCauseAnalysis(
        trace_id="t1", primary_cause="test",
        category=category, confidence=0.8,
    )


def test_refine_model_error():
    r = SelfRefiner()
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.model_error),
        {"regularization": 0.01, "_action_type": "trade"}, mem,
    )
    assert len(proposals) > 0
    assert any("regularization" in p.proposed_changes for p in proposals)


def test_refine_data_stale():
    r = SelfRefiner()
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.data_stale),
        {"data_refresh_interval": 60, "_action_type": "trade"}, mem,
    )
    assert len(proposals) > 0
    assert any("data_refresh_interval" in p.proposed_changes for p in proposals)


def test_refine_strategy_flaw():
    r = SelfRefiner()
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.strategy_flaw),
        {"risk_tolerance": 0.5, "position_size": 1.0, "_action_type": "trade"}, mem,
    )
    assert len(proposals) > 0


def test_refine_execution_error():
    r = SelfRefiner()
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.execution_error),
        {"slippage_tolerance": 0.02, "_action_type": "trade"}, mem,
    )
    assert len(proposals) > 0
    assert any("use_limit_orders" in p.proposed_changes for p in proposals)


def test_refine_external_shock():
    r = SelfRefiner()
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.external_shock),
        {"position_size": 1.0, "_action_type": "trade"}, mem,
    )
    assert len(proposals) > 0


def test_refine_parameter_miscalibration():
    r = SelfRefiner()
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.parameter_miscalibration),
        {"_action_type": "trade"}, mem,
    )
    assert len(proposals) > 0
    assert any("recalibrate" in p.proposed_changes for p in proposals)


def test_max_refinement_steps():
    r = SelfRefiner(max_refinement_steps=2)
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.model_error),
        {"model_weights": {"a": 1.0}, "regularization": 0.01, "_action_type": "trade"}, mem,
    )
    assert len(proposals) <= 2


def test_proposals_sorted_by_net_benefit():
    r = SelfRefiner(max_refinement_steps=10)
    mem = ReflectionMemory()
    proposals = r.propose_refinements(
        _eval(), _rca(CauseCategory.model_error),
        {"model_weights": {"a": 1.0}, "regularization": 0.01, "_action_type": "trade"}, mem,
    )
    for i in range(len(proposals) - 1):
        assert proposals[i].net_benefit >= proposals[i + 1].net_benefit
