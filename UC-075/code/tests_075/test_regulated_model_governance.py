"""Tests para regulated_model_governance.py — gobernanza sectorial, explicabilidad y selección regulada."""
from __future__ import annotations

import pytest

from regulated_model_governance import (
    ExplainabilityGate,
    ModelCard,
    ModelType,
    RegulatoryControl,
    RegulatoryDomain,
    RegulatoryPolicy,
    RegulatedModelSelector,
    StakeholderRequirement,
    StakeholderRequirements,
)


# ---------------------------------------------------------------------------
# RegulatoryPolicy
# ---------------------------------------------------------------------------

class TestRegulatoryPolicy:
    def test_default_controls_energy(self):
        p = RegulatoryPolicy(domain=RegulatoryDomain.ENERGY)
        assert RegulatoryControl.HITL_REQUIRED in p.required_controls
        assert RegulatoryControl.INTERPRETABILITY_REQUIRED in p.required_controls
        assert RegulatoryControl.REDUNDANCY_REQUIRED in p.required_controls
        assert RegulatoryControl.SHADOW_DEPLOYMENT_REQUIRED in p.required_controls

    def test_default_controls_finance(self):
        p = RegulatoryPolicy(domain=RegulatoryDomain.FINANCE)
        assert RegulatoryControl.FAIRNESS_BY_SUBGROUP in p.required_controls
        assert RegulatoryControl.INTERPRETABILITY_REQUIRED in p.required_controls

    def test_default_controls_healthcare(self):
        p = RegulatoryPolicy(domain=RegulatoryDomain.HEALTHCARE)
        assert RegulatoryControl.HUMAN_OVERRIDE in p.required_controls

    def test_default_controls_nuclear(self):
        p = RegulatoryPolicy(domain=RegulatoryDomain.NUCLEAR)
        assert RegulatoryControl.MAX_LATENCY_MS in p.required_controls
        assert RegulatoryControl.MIN_AVAILABILITY in p.required_controls

    def test_requires_method(self):
        p = RegulatoryPolicy(domain=RegulatoryDomain.TELECOM)
        assert p.requires(RegulatoryControl.REDUNDANCY_REQUIRED)
        assert not p.requires(RegulatoryControl.FAIRNESS_BY_SUBGROUP)

    def test_to_dict(self):
        p = RegulatoryPolicy(domain=RegulatoryDomain.WATER)
        d = p.to_dict()
        assert d["domain"] == "critical_infrastructure_water"
        assert "required_controls" in d


# ---------------------------------------------------------------------------
# StakeholderRequirements
# ---------------------------------------------------------------------------

class TestStakeholderRequirements:
    def test_unsigned_blocks_all_signed(self):
        reqs = StakeholderRequirements()
        req = StakeholderRequirement(
            stakeholder="CSO",
            description="Explicabilidad obligatoria para SCADA",
            domain=RegulatoryDomain.ENERGY,
            category="explainability",
        )
        reqs.add(req)
        assert not reqs.all_signed_off(RegulatoryDomain.ENERGY)
        req.sign_off("cso@utron.ai")
        assert reqs.all_signed_off(RegulatoryDomain.ENERGY)


# ---------------------------------------------------------------------------
# ExplainabilityGate
# ---------------------------------------------------------------------------

class TestExplainabilityGate:
    def test_interpretable_skips(self):
        policy = RegulatoryPolicy(domain=RegulatoryDomain.ENERGY)
        gate = ExplainabilityGate(policy=policy)
        card = ModelCard(
            model_id="linear-baseline",
            model_type=ModelType.INTERPRETABLE,
            algorithm="logistic_regression",
            complexity_score=0.1,
        )
        report = gate.evaluate(card, [])
        assert report.passed
        assert not report.requires_explanation

    def test_black_box_fails_without_explanation(self):
        policy = RegulatoryPolicy(
            domain=RegulatoryDomain.ENERGY,
            min_explanation_stability=0.99,
            min_explanation_coverage=0.99,
        )
        gate = ExplainabilityGate(policy=policy)
        card = ModelCard(
            model_id="deep-ensemble",
            model_type=ModelType.BLACK_BOX,
            algorithm="xgboost",
            complexity_score=0.95,
        )
        report = gate.evaluate(card, [])
        assert not report.passed
        assert report.requires_explanation
        assert any("stability" in v for v in report.violations)

    def test_black_box_passes_with_mock_provider(self):
        policy = RegulatoryPolicy(domain=RegulatoryDomain.ENERGY)

        def good_provider(model_card, X, domain):
            return {
                "method": "shap",
                "top_features": [("f0", 0.5)],
                "stability_score": 0.95,
                "coverage": 0.95,
                "faithfulness_score": 0.9,
            }

        gate = ExplainabilityGate(policy=policy, provider=good_provider)
        card = ModelCard(
            model_id="ensemble",
            model_type=ModelType.BLACK_BOX,
            algorithm="random_forest",
            complexity_score=0.7,
        )
        report = gate.evaluate(card, [])
        assert report.passed
        assert report.method == "shap"


# ---------------------------------------------------------------------------
# RegulatedModelSelector
# ---------------------------------------------------------------------------

class TestRegulatedModelSelector:
    def test_selects_interpretable_when_required(self):
        policy = RegulatoryPolicy(domain=RegulatoryDomain.ENERGY)
        selector = RegulatedModelSelector(policy=policy)
        baseline = ModelCard(
            model_id="linear-baseline",
            model_type=ModelType.INTERPRETABLE,
            algorithm="logistic_regression",
            complexity_score=0.1,
            metrics={"auc": 0.80},
        )
        black_box = ModelCard(
            model_id="deep-net",
            model_type=ModelType.BLACK_BOX,
            algorithm="mlp",
            complexity_score=0.9,
            metrics={"auc": 0.90},
        )
        decision = selector.select([black_box], baseline)
        assert decision.selected_model_id == "linear-baseline"
        assert "preferencia por modelo interpretable" in decision.reason.lower() or "interpretable" in decision.reason.lower()

    def test_unsigned_requirement_blocks_blackbox(self):
        policy = RegulatoryPolicy(domain=RegulatoryDomain.FINANCE)
        reqs = StakeholderRequirements()
        reqs.add(StakeholderRequirement(
            stakeholder="Risk",
            description="No desplegar sin revisión de sesgo",
            domain=RegulatoryDomain.FINANCE,
        ))
        selector = RegulatedModelSelector(policy=policy, stakeholder_requirements=reqs)
        baseline = ModelCard(
            model_id="baseline",
            model_type=ModelType.INTERPRETABLE,
            algorithm="tree",
            complexity_score=0.2,
            metrics={"auc": 0.78},
        )
        decision = selector.select([], baseline)
        assert decision.selected_model_id == "baseline"
        assert decision.hitl_required
        assert decision.stakeholder_violations

    def test_black_box_accepted_if_interpretable_missing_and_margin_sufficient(self):
        policy = RegulatoryPolicy(
            domain=RegulatoryDomain.GENERAL,
            min_margin_to_accept_blackbox=0.05,
        )
        selector = RegulatedModelSelector(policy=policy)
        baseline = ModelCard(
            model_id="baseline",
            model_type=ModelType.INTERPRETABLE,
            algorithm="tree",
            complexity_score=0.2,
            metrics={"auc": 0.80},
        )
        black_box = ModelCard(
            model_id="deep-net",
            model_type=ModelType.BLACK_BOX,
            algorithm="mlp",
            complexity_score=0.9,
            metrics={"auc": 0.90},
        )
        decision = selector.select([black_box], baseline)
        assert decision.selected_model_id == "deep-net"
        assert decision.hitl_required  # because always_hitl_if_blackbox default True

    def test_rejects_if_baseline_fails_acceptance(self):
        policy = RegulatoryPolicy(domain=RegulatoryDomain.FINANCE, min_auc=0.99)
        selector = RegulatedModelSelector(policy=policy)
        baseline = ModelCard(
            model_id="baseline",
            model_type=ModelType.INTERPRETABLE,
            algorithm="tree",
            metrics={"auc": 0.80},
        )
        decision = selector.select([], baseline)
        assert decision.selected_model_id == "baseline"
        assert "baseline no cumple" in decision.reason.lower() or "baseline" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Integration: selector + explainability + HITL
# ---------------------------------------------------------------------------

class TestRegulatedIntegration:
    def test_energy_sector_requires_hitl_and_shadow(self):
        policy = RegulatoryPolicy(domain=RegulatoryDomain.ENERGY)
        selector = RegulatedModelSelector(policy=policy)
        baseline = ModelCard(
            model_id="linear-baseline",
            model_type=ModelType.INTERPRETABLE,
            algorithm="logistic_regression",
            complexity_score=0.1,
            metrics={"auc": 0.82, "latency_p95_ms": 50, "availability": 0.9999},
        )
        hybrid = ModelCard(
            model_id="hybrid-model",
            model_type=ModelType.HYBRID,
            algorithm="gbdt+rules",
            complexity_score=0.5,
            metrics={"auc": 0.88, "latency_p95_ms": 80, "availability": 0.9999},
        )
        decision = selector.select([hybrid], baseline)
        assert decision.selected_model_id == "linear-baseline"
        assert RegulatoryControl.SHADOW_DEPLOYMENT_REQUIRED.value in decision.regulatory_controls

    def test_model_card_to_dict(self):
        card = ModelCard(
            model_id="x",
            model_type=ModelType.HYBRID,
            algorithm="gbdt",
            metrics={"auc": 0.8},
        )
        d = card.to_dict()
        assert d["model_type"] == "hybrid"
        assert d["metrics"]["auc"] == 0.8
