"""Tests para MLOpsHITLFeedbackLoop."""
import time

import pytest

from mlops_hitl_feedback_loop import (
    FeedbackExample,
    HITLDecisionInput,
    MLOpsHITLFeedbackLoop,
    RegulatoryPolicy,
    compute_ambiguity_score,
    validate_training_dataset,
)
from mlops_self_healing_orchestrator import MLOpsSelfHealingOrchestrator
from models_087 import MLSecOpsConfig


@pytest.fixture
def loop():
    config = MLSecOpsConfig(min_samples_for_training=3)
    orchestrator = MLOpsSelfHealingOrchestrator(config=config, retrain_source="hitl_feedback")
    return MLOpsHITLFeedbackLoop(
        self_healing_orchestrator=orchestrator,
        min_examples_for_retrain=3,
        min_reviewers_for_retrain=1,
        min_temporal_span_days=0.0,
    )


def test_approved_generates_example(loop):
    dec = HITLDecisionInput(
        trace_id="t-1",
        dossier_id="d-1",
        decision="approved",
        reviewer_id="rev-1",
        final_action="BUY",
        ai_suggestion="buy",
        modified_suggestion=None,
        review_notes="looks good",
        input_context={"features": [1.0, 2.0, 3.0, 4.0]},
        timestamp=0.0,
    )
    ex = loop.ingest_decision(dec)
    assert ex is not None
    assert ex.label == 1
    assert ex.to_data_point().features == [1.0, 2.0, 3.0, 4.0]


def test_rejected_skipped(loop):
    dec = HITLDecisionInput(
        trace_id="t-2",
        dossier_id="d-2",
        decision="rejected",
        reviewer_id="rev-1",
        final_action="HOLD",
        ai_suggestion="buy",
        modified_suggestion=None,
        review_notes="risky",
        input_context={"features": [1.0, 2.0, 3.0, 4.0]},
        timestamp=0.0,
    )
    ex = loop.ingest_decision(dec)
    assert ex is None


def test_modified_generates_sell_label(loop):
    dec = HITLDecisionInput(
        trace_id="t-3",
        dossier_id="d-3",
        decision="modified",
        reviewer_id="rev-1",
        final_action="SELL",
        ai_suggestion="buy",
        modified_suggestion="SELL",
        review_notes="change to sell",
        input_context={"features": [-1.0, -2.0, -3.0, -4.0]},
        timestamp=0.0,
    )
    ex = loop.ingest_decision(dec)
    assert ex is not None
    assert ex.label == 0


def test_should_retrain_threshold(loop):
    assert not loop.should_retrain()
    for i in range(3):
        loop.ingest_decision(HITLDecisionInput(
            trace_id=f"t-{i}",
            dossier_id=f"d-{i}",
            decision="approved",
            reviewer_id="rev-1",
            final_action="BUY",
            ai_suggestion="buy",
            modified_suggestion=None,
            review_notes="ok",
            input_context={"features": [1.0, 2.0, 3.0, 4.0]},
            timestamp=0.0,
        ))
    assert loop.should_retrain()


def test_maybe_retrain(loop):
    for i in range(20):
        loop.ingest_decision(HITLDecisionInput(
            trace_id=f"t-{i}",
            dossier_id=f"d-{i}",
            decision="approved",
            reviewer_id="rev-1",
            final_action="BUY",
            ai_suggestion="buy",
            modified_suggestion=None,
            review_notes="ok",
            input_context={"features": [float(i), float(i) * 0.5, float(i) * -0.2, float(i) * 0.1]},
            timestamp=0.0,
        ))
    result = loop.maybe_retrain("agent-1", force=True)
    assert result is not None
    assert "version_id" in result
    # Solo se consumen min_examples (3), el resto queda
    assert len(loop._examples) == 17


def test_event_sink(loop):
    events = []
    loop.event_sink = lambda e: events.append(e)
    dec = HITLDecisionInput(
        trace_id="t-1",
        dossier_id="d-1",
        decision="approved",
        reviewer_id="rev-1",
        final_action="BUY",
        ai_suggestion="buy",
        modified_suggestion=None,
        review_notes="ok",
        input_context={"features": [1.0, 2.0, 3.0, 4.0]},
        timestamp=0.0,
    )
    loop.ingest_decision(dec)
    assert any(e["event_type"] == "hitl_feedback_example_created" for e in events)


# ---------------------------------------------------------------------------
# Nuevas funcionalidades: políticas regulatorias, ambiguity, validación
# ---------------------------------------------------------------------------

def test_regulatory_policy_healthcare():
    policy = RegulatoryPolicy.for_domain("healthcare")
    assert policy.is_feature_prohibited("race")
    assert policy.is_feature_prohibited("RACE")
    assert not policy.is_feature_prohibited("age")
    assert policy.min_confidence_for_auto == 0.95
    assert "hipaa" in policy.compliance


def test_regulatory_policy_finance():
    policy = RegulatoryPolicy.for_domain("finance")
    assert policy.is_feature_prohibited("gender")
    assert "sox" in policy.compliance


def test_regulatory_policy_criminal_justice():
    policy = RegulatoryPolicy.for_domain("criminal_justice")
    assert policy.requires_human_review
    assert policy.min_confidence_for_auto == 1.0


def test_ambiguity_score_low_confidence():
    score = compute_ambiguity_score(0.3, {"f1": 0.5, "f2": 0.5})
    assert score > 0.5


def test_ambiguity_score_high_confidence_concentrated():
    score = compute_ambiguity_score(0.95, {"f1": 0.9, "f2": 0.1})
    assert score < 0.3


def test_ambiguity_score_no_features():
    score = compute_ambiguity_score(0.5)
    assert 0.0 <= score <= 1.0


def test_prohibited_feature_blocks_ingest():
    config = MLSecOpsConfig(min_samples_for_training=3)
    orchestrator = MLOpsSelfHealingOrchestrator(config=config, retrain_source="hitl_feedback")
    loop = MLOpsHITLFeedbackLoop(
        self_healing_orchestrator=orchestrator,
        min_examples_for_retrain=3,
        domain="healthcare",
    )
    dec = HITLDecisionInput(
        trace_id="t-blocked",
        dossier_id="d-blocked",
        decision="approved",
        reviewer_id="rev-1",
        final_action="BUY",
        ai_suggestion="buy",
        modified_suggestion=None,
        review_notes="ok",
        input_context={"race": "hispanic", "features": [1.0, 2.0]},
        timestamp=0.0,
    )
    result = loop.ingest_decision(dec)
    assert result is None


def test_ambiguity_stored_in_example():
    config = MLSecOpsConfig(min_samples_for_training=3)
    orchestrator = MLOpsSelfHealingOrchestrator(config=config, retrain_source="hitl_feedback")
    loop = MLOpsHITLFeedbackLoop(
        self_healing_orchestrator=orchestrator,
        min_examples_for_retrain=3,
    )
    dec = HITLDecisionInput(
        trace_id="t-amb",
        dossier_id="d-amb",
        decision="approved",
        reviewer_id="rev-1",
        final_action="BUY",
        ai_suggestion="buy",
        modified_suggestion=None,
        review_notes="ok",
        input_context={"features": [1.0, 2.0, 3.0, 4.0]},
        timestamp=0.0,
        confidence_score=0.45,
        feature_importance={"f1": 0.3, "f2": 0.3, "f3": 0.4},
    )
    ex = loop.ingest_decision(dec)
    assert ex is not None
    assert ex.ambiguity_score > 0.0
    assert ex.confidence_score == 0.45


def test_validation_blocks_single_reviewer():
    policy = RegulatoryPolicy.for_domain("default")
    examples = []
    for i in range(5):
        ex = FeedbackExample(
            example_id=f"ex-{i}",
            trace_id=f"t-{i}",
            dossier_id=f"d-{i}",
            reviewer_id="rev-1",
            input_features=[1.0, 2.0],
            label=1,
            target_action="BUY",
            reason="ok",
            timestamp=time.time(),
            approved=True,
        )
        examples.append(ex)
    result = validate_training_dataset(examples, policy, min_reviewers=2)
    assert not result.compliant
    assert "insufficient_reviewer_diversity" in result.violations


def test_validation_blocks_no_temporal_span():
    policy = RegulatoryPolicy.for_domain("default")
    now = time.time()
    examples = [
        FeedbackExample(
            example_id=f"ex-{i}",
            trace_id=f"t-{i}",
            dossier_id=f"d-{i}",
            reviewer_id=f"rev-{i}",
            input_features=[1.0, 2.0],
            label=1,
            target_action="BUY",
            reason="ok",
            timestamp=now,
            approved=True,
        )
        for i in range(3)
    ]
    result = validate_training_dataset(examples, policy, min_reviewers=2, min_temporal_span_days=1.0)
    assert not result.compliant
    assert "insufficient_temporal_diversity" in result.violations


def test_validation_passes_with_diversity():
    policy = RegulatoryPolicy.for_domain("default")
    base = time.time()
    examples = [
        FeedbackExample(
            example_id=f"ex-{i}",
            trace_id=f"t-{i}",
            dossier_id=f"d-{i}",
            reviewer_id=f"rev-{i}",
            input_features=[1.0, 2.0],
            label=1,
            target_action="BUY",
            reason="ok",
            timestamp=base + i * 100000,
            approved=True,
        )
        for i in range(3)
    ]
    result = validate_training_dataset(examples, policy, min_reviewers=2, min_temporal_span_days=1.0)
    assert result.compliant
    assert result.unique_reviewers == 3


def test_maybe_retrain_blocked_by_validation():
    config = MLSecOpsConfig(min_samples_for_training=3)
    orchestrator = MLOpsSelfHealingOrchestrator(config=config, retrain_source="hitl_feedback")
    loop = MLOpsHITLFeedbackLoop(
        self_healing_orchestrator=orchestrator,
        min_examples_for_retrain=3,
        min_reviewers_for_retrain=2,
    )
    for i in range(3):
        loop.ingest_decision(HITLDecisionInput(
            trace_id=f"t-{i}",
            dossier_id=f"d-{i}",
            decision="approved",
            reviewer_id="rev-1",
            final_action="BUY",
            ai_suggestion="buy",
            modified_suggestion=None,
            review_notes="ok",
            input_context={"features": [1.0, 2.0, 3.0, 4.0]},
            timestamp=0.0,
        ))
    result = loop.maybe_retrain("agent-1", force=True)
    assert result is not None
    assert result["status"] == "blocked"
    assert "insufficient_reviewer_diversity" in result["violations"]


def test_get_policy():
    config = MLSecOpsConfig(min_samples_for_training=3)
    orchestrator = MLOpsSelfHealingOrchestrator(config=config, retrain_source="hitl_feedback")
    loop = MLOpsHITLFeedbackLoop(
        self_healing_orchestrator=orchestrator,
        min_examples_for_retrain=3,
        domain="finance",
    )
    policy = loop.get_policy()
    assert policy["domain"] == "finance"
    assert "sox" in policy["compliance"]


# ---------------------------------------------------------------------------
# UC-290: SLA y asignación de revisores
# ---------------------------------------------------------------------------

def test_uc290_sla_hours():
    import sys
    sys.path.insert(0, "/Users/utron/Documents/code-books/tomoIII/UC-290/code")
    from models_290 import HITLConfig, RiskLevel

    config = HITLConfig()
    assert config.get_sla_hours(RiskLevel.MEDIUM) == 24
    assert config.get_sla_hours(RiskLevel.HIGH) == 8
    assert config.get_sla_hours(RiskLevel.CRITICAL) == 2
    assert config.get_sla_hours(RiskLevel.LOW) == 0


def test_uc290_reviewers_by_risk():
    import sys
    sys.path.insert(0, "/Users/utron/Documents/code-books/tomoIII/UC-290/code")
    from models_290 import HITLConfig, RiskLevel

    config = HITLConfig()
    assert config.get_reviewers(RiskLevel.MEDIUM) == ["domain_expert"]
    assert "compliance_officer" in config.get_reviewers(RiskLevel.HIGH)
    assert "ethics_reviewer" in config.get_reviewers(RiskLevel.CRITICAL)
    assert config.get_reviewers(RiskLevel.LOW) == []


def test_uc290_custom_sla_and_reviewers():
    import sys
    sys.path.insert(0, "/Users/utron/Documents/code-books/tomoIII/UC-290/code")
    from models_290 import HITLConfig, RiskLevel

    config = HITLConfig(
        sla_hours_critical=1,
        reviewers_high=["custom_reviewer"],
    )
    assert config.get_sla_hours(RiskLevel.CRITICAL) == 1
    assert config.get_reviewers(RiskLevel.HIGH) == ["custom_reviewer"]
