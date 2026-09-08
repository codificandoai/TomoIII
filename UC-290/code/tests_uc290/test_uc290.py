"""
UC-290 — Tests unitarios y de integración para HITL Guardian.

Cubre:
- Modelos de datos (dataclasses, enums, hash).
- RiskAssessor (riesgo bajo, alto, bloqueado).
- DossierBuilder (expediente auto-execute y escalado).
- EscalationEngine (approve, modify, reject, timeout).
- HumanReviewInterface (presentación, Slack, webhook).
- AuditTrail (registro, cadena, tamper detection).
- ObservabilityManager (logs, métricas, Prometheus).
- HITLGuardian (pipeline completo, revisión humana, reset).
- API REST (todos los endpoints).
- Integración end-to-end.
"""

import sys
import os
import json
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models_290 import (
    HITLConfig,
    DecisionInput,
    DecisionDossier,
    RiskAssessment,
    RiskLevel,
    HITLDecision,
    DossierStatus,
    HumanAction,
    HumanReview,
    ReasoningStep,
    ReasoningStepType,
    AuditEntry,
    HITLResult,
    generate_id,
)
from risk_assessor import RiskAssessor
from decision_dossier import DossierBuilder
from escalation_engine import EscalationEngine
from human_review_interface import HumanReviewInterface
from audit_trail import AuditTrail
from observability_290 import ObservabilityManager
from hitl_guardian import HITLGuardian


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reasoning_step(num=1, desc="Test step", confidence=0.8):
    return ReasoningStep(
        step_number=num,
        step_type=ReasoningStepType.INFERENCE,
        description=desc,
        confidence=confidence,
        source="uc315",
    )


def _make_low_risk_input():
    return DecisionInput(
        decision_id="test_001",
        trace_id="test_trace_001",
        context={"current_price": 105.0, "predicted_move": 1.0, "volume": 75000},
        ai_suggestion="BUY",
        ai_confidence=0.85,
        ai_reasoning_steps=[_make_reasoning_step(1, "Tendencia alcista")],
        uc087_integrity_passed=True,
        uc162_llmops_passed=True,
        uc325_reflection_score=0.82,
        uc322_conflict_detected=False,
    )


def _make_high_risk_input():
    return DecisionInput(
        decision_id="test_002",
        trace_id="test_trace_002",
        context={"current_price": 100.0, "predicted_move": 8.0, "volume": 95000},
        ai_suggestion="BUY",
        ai_confidence=0.55,
        ai_reasoning_steps=[_make_reasoning_step(1, "Volatilidad extrema", 0.55)],
        uc087_integrity_passed=True,
        uc162_llmops_passed=True,
        uc325_reflection_score=0.40,
        uc322_conflict_detected=True,
        uc322_conflict_details={"agents": ["uc329", "uc325"]},
    )


def _make_blocked_input():
    return DecisionInput(
        decision_id="test_003",
        trace_id="test_trace_003",
        context={"current_price": 100.0, "predicted_move": 1.0},
        ai_suggestion="SELL",
        ai_confidence=0.90,
        uc087_integrity_passed=False,
        uc087_integrity_details={"error": "hash_mismatch"},
        uc162_llmops_passed=True,
        uc325_reflection_score=0.80,
        uc322_conflict_detected=False,
    )


# ---------------------------------------------------------------------------
# Tests: Modelos de datos
# ---------------------------------------------------------------------------

class TestModels:
    def test_hitl_config_defaults(self):
        config = HITLConfig()
        assert config.confidence_threshold == 0.65
        assert config.risk_high_threshold == 0.70
        assert config.require_human_for_critical is True

    def test_hitl_config_to_dict(self):
        config = HITLConfig()
        d = config.to_dict()
        assert "confidence_threshold" in d
        assert "risk_high_threshold" in d

    def test_risk_level_enum(self):
        assert RiskLevel.NONE.value == "none"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_hitl_decision_enum(self):
        assert HITLDecision.AUTO_EXECUTE.value == "auto_execute"
        assert HITLDecision.ESCALATE.value == "escalate"

    def test_human_action_enum(self):
        assert HumanAction.APPROVE.value == "approve"
        assert HumanAction.REJECT.value == "reject"

    def test_dossier_status_enum(self):
        assert DossierStatus.DRAFT.value == "draft"
        assert DossierStatus.PENDING_REVIEW.value == "pending_review"

    def test_reasoning_step_to_dict(self):
        step = ReasoningStep(1, ReasoningStepType.DATA, "test", "evidence", 0.9, "uc315")
        d = step.to_dict()
        assert d["step_number"] == 1
        assert d["step_type"] == "data"
        assert d["description"] == "test"

    def test_decision_input_to_dict(self):
        inp = _make_low_risk_input()
        d = inp.to_dict()
        assert d["ai_suggestion"] == "BUY"
        assert d["uc087_integrity_passed"] is True

    def test_decision_dossier_compute_hash(self):
        inp = _make_low_risk_input()
        ra = RiskAssessor()
        risk = ra.assess(inp)
        builder = DossierBuilder()
        dossier = builder.build(inp, risk)
        assert len(dossier.content_hash) == 64

    def test_decision_dossier_hash_deterministic(self):
        inp = _make_low_risk_input()
        ra = RiskAssessor()
        risk = ra.assess(inp)
        builder = DossierBuilder()
        dossier = builder.build(inp, risk)
        h1 = dossier.content_hash
        dossier.compute_hash()
        assert h1 == dossier.content_hash

    def test_generate_id_unique(self):
        id1 = generate_id()
        id2 = generate_id()
        assert id1 != id2

    def test_risk_assessment_to_dict(self):
        risk = RiskAssessment(risk_score=0.5, risk_level=RiskLevel.MEDIUM, confidence_score=0.7)
        d = risk.to_dict()
        assert d["risk_level"] == "medium"
        assert d["risk_score"] == 0.5

    def test_human_review_to_dict(self):
        review = HumanReview(reviewer_id="r1", action=HumanAction.APPROVE)
        d = review.to_dict()
        assert d["reviewer_id"] == "r1"
        assert d["action"] == "approve"

    def test_hitl_result_to_dict(self):
        result = HITLResult(trace_id="t1", dossier_id="d1", decision=HITLDecision.AUTO_EXECUTE)
        d = result.to_dict()
        assert d["decision"] == "auto_execute"
        assert d["trace_id"] == "t1"


# ---------------------------------------------------------------------------
# Tests: Risk Assessor
# ---------------------------------------------------------------------------

class TestRiskAssessor:
    def test_low_risk(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        assert risk.risk_level in (RiskLevel.NONE, RiskLevel.LOW)
        assert not risk.requires_escalation

    def test_high_risk(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        assert risk.requires_escalation
        assert len(risk.escalation_reasons) > 0

    def test_blocked_risk(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_blocked_input())
        assert risk.requires_escalation

    def test_volatility_calculation(self):
        ra = RiskAssessor()
        inp = DecisionInput(
            context={"current_price": 100.0, "predicted_move": 8.0},
            ai_confidence=0.9,
            uc087_integrity_passed=True,
            uc162_llmops_passed=True,
            uc325_reflection_score=0.8,
        )
        risk = ra.assess(inp)
        assert risk.volatility == 0.08  # 8/100

    def test_factors_list(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        assert len(risk.factors) > 0

    def test_conflict_escalation(self):
        ra = RiskAssessor()
        inp = _make_low_risk_input()
        inp.uc322_conflict_detected = True
        risk = ra.assess(inp)
        assert risk.requires_escalation
        assert any("conflict" in r.lower() for r in risk.escalation_reasons)

    def test_low_confidence_escalation(self):
        ra = RiskAssessor()
        inp = _make_low_risk_input()
        inp.ai_confidence = 0.30
        risk = ra.assess(inp)
        assert risk.requires_escalation

    def test_risk_score_range(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        assert 0.0 <= risk.risk_score <= 1.0


# ---------------------------------------------------------------------------
# Tests: Dossier Builder
# ---------------------------------------------------------------------------

class TestDossierBuilder:
    def test_build_auto_execute(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        assert dossier.status == DossierStatus.AUTO_EXECUTED
        assert dossier.decision == HITLDecision.AUTO_EXECUTE

    def test_build_escalation(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        assert dossier.status == DossierStatus.PENDING_REVIEW
        assert dossier.decision == HITLDecision.ESCALATE

    def test_reasoning_steps_consolidated(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        # Should have at least: 1 AI step + UC-087 + UC-162 + UC-325 + UC-322 + risk + suggestion
        assert len(dossier.reasoning_steps) >= 7

    def test_hash_computed(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        assert len(dossier.content_hash) == 64

    def test_to_summary(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        summary = builder.to_summary(dossier)
        assert "EXPEDIENTE" in summary
        assert "RAZONAMIENTO" in summary

    def test_expires_at_set(self):
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk, escalation_timeout_sec=1800)
        assert dossier.expires_at > dossier.timestamp


# ---------------------------------------------------------------------------
# Tests: Escalation Engine
# ---------------------------------------------------------------------------

class TestEscalationEngine:
    def test_escalate(self):
        ee = EscalationEngine()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        notification = ee.escalate(dossier)
        assert notification["status"] == "pending"
        assert len(ee.get_pending()) == 1

    def test_submit_approve(self):
        ee = EscalationEngine()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        ee.escalate(dossier)
        reviewed = ee.submit_review(dossier.dossier_id, "r1", HumanAction.APPROVE)
        assert reviewed.status == DossierStatus.APPROVED
        assert len(ee.get_pending()) == 0

    def test_submit_reject(self):
        ee = EscalationEngine()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        ee.escalate(dossier)
        reviewed = ee.submit_review(dossier.dossier_id, "r1", HumanAction.REJECT, override_reason="No")
        assert reviewed.status == DossierStatus.REJECTED

    def test_submit_modify(self):
        ee = EscalationEngine()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        ee.escalate(dossier)
        reviewed = ee.submit_review(
            dossier.dossier_id, "r1", HumanAction.MODIFY, modified_suggestion="HOLD"
        )
        assert reviewed.status == DossierStatus.MODIFIED
        assert reviewed.ai_suggestion == "HOLD"

    def test_submit_nonexistent(self):
        ee = EscalationEngine()
        result = ee.submit_review("nonexistent", "r1", HumanAction.APPROVE)
        assert result is None

    def test_timeout(self):
        ee = EscalationEngine(HITLConfig(escalation_timeout_sec=0.01))
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk, escalation_timeout_sec=0.01)
        ee.escalate(dossier)
        time.sleep(0.02)
        expired = ee.check_timeouts()
        assert len(expired) == 1

    def test_escalation_history(self):
        ee = EscalationEngine()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        ee.escalate(dossier)
        history = ee.get_escalation_history()
        assert len(history) == 1

    def test_reset(self):
        ee = EscalationEngine()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        ee.escalate(dossier)
        ee.reset()
        assert len(ee.get_pending()) == 0


# ---------------------------------------------------------------------------
# Tests: Human Review Interface
# ---------------------------------------------------------------------------

class TestHumanReviewInterface:
    def test_present_dossier(self):
        hi = HumanReviewInterface()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        presentation = hi.present_dossier(dossier)
        assert "presentation" in presentation
        assert "dossier" in presentation
        assert "available_actions" in presentation

    def test_format_for_slack(self):
        hi = HumanReviewInterface()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        slack = hi.format_for_slack(dossier)
        assert "attachments" in slack
        assert len(slack["attachments"]) == 1

    def test_format_for_webhook(self):
        hi = HumanReviewInterface()
        ra = RiskAssessor()
        risk = ra.assess(_make_high_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_high_risk_input(), risk)
        webhook = hi.format_for_webhook(dossier, "https://hooks.example.com")
        assert webhook["event"] == "hitl_escalation"
        assert webhook["webhook_url"] == "https://hooks.example.com"

    def test_create_review(self):
        hi = HumanReviewInterface()
        review = hi.create_review("r1", HumanAction.APPROVE, review_notes="OK")
        assert review.reviewer_id == "r1"
        assert review.action == HumanAction.APPROVE


# ---------------------------------------------------------------------------
# Tests: Audit Trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_record_and_retrieve(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        entries = trail.get_entries()
        assert len(entries) == 1

    def test_chain_verified(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        trail.record_auto_execute(dossier)
        assert trail.verify_chain() is True

    def test_tamper_detection(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        trail.entries[0].event = "TAMPERED"
        assert trail.verify_chain() is False

    def test_filter_by_dossier(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        entries = trail.get_entries(dossier_id=dossier.dossier_id)
        assert len(entries) == 1
        entries_other = trail.get_entries(dossier_id="nonexistent")
        assert len(entries_other) == 0

    def test_summary(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        trail.record_auto_execute(dossier)
        summary = trail.get_summary()
        assert summary["total_entries"] == 2
        assert summary["chain_verified"] is True

    def test_to_json(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        j = trail.to_json()
        parsed = json.loads(j)
        assert len(parsed) == 1

    def test_reset(self):
        trail = AuditTrail()
        ra = RiskAssessor()
        risk = ra.assess(_make_low_risk_input())
        builder = DossierBuilder()
        dossier = builder.build(_make_low_risk_input(), risk)
        trail.record_dossier_created(dossier)
        trail.reset()
        assert len(trail.entries) == 0


# ---------------------------------------------------------------------------
# Tests: Observability
# ---------------------------------------------------------------------------

class TestObservabilityManager:
    def test_log(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        assert len(om.logs) == 1

    def test_increment(self):
        om = ObservabilityManager()
        om.increment("test_total")
        om.increment("test_total")
        assert om.metrics["test_total"] == 2.0

    def test_gauge(self):
        om = ObservabilityManager()
        om.gauge("test_gauge", 42.0)
        assert om.metrics["test_gauge"] == 42.0

    def test_spans(self):
        om = ObservabilityManager()
        span = om.start_span("op")
        om.end_span(span)
        assert span["end"] is not None
        assert span["duration_ms"] >= 0

    def test_export_prometheus(self):
        om = ObservabilityManager()
        om.increment("test_counter_total")
        om.gauge("test_gauge", 1.5)
        prom = om.export_prometheus()
        assert "test_counter_total" in prom
        assert "test_gauge" in prom
        assert 'component="uc290_hitl"' in prom

    def test_summary(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        om.increment("m")
        summary = om.get_summary()
        assert summary["log_count"] == 1

    def test_reset(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        om.increment("m")
        om.reset()
        assert len(om.logs) == 0
        assert len(om.metrics) == 0

    def test_to_json(self):
        om = ObservabilityManager()
        om.log("INFO", "test")
        j = om.to_json()
        parsed = json.loads(j)
        assert "logs" in parsed


# ---------------------------------------------------------------------------
# Tests: HITL Guardian
# ---------------------------------------------------------------------------

class TestHITLGuardian:
    def test_auto_execute(self):
        g = HITLGuardian()
        result = g.process_decision(_make_low_risk_input())
        assert result.decision == HITLDecision.AUTO_EXECUTE
        assert not result.escalated
        assert result.final_action == "BUY"

    def test_escalate(self):
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        assert result.decision == HITLDecision.ESCALATE
        assert result.escalated
        assert len(result.escalation_reasons) > 0

    def test_blocked(self):
        g = HITLGuardian()
        result = g.process_decision(_make_blocked_input())
        assert result.decision == HITLDecision.BLOCKED
        assert len(result.issues) > 0

    def test_human_review_approve(self):
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        pending = g.get_pending_reviews()
        assert len(pending) == 1
        reviewed = g.submit_human_review(
            pending[0]["dossier_id"], "r1", HumanAction.APPROVE
        )
        assert reviewed["status"] == "approved"
        assert len(g.get_pending_reviews()) == 0

    def test_human_review_reject(self):
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        pending = g.get_pending_reviews()
        reviewed = g.submit_human_review(
            pending[0]["dossier_id"], "r1", HumanAction.REJECT,
            override_reason="No",
        )
        assert reviewed["status"] == "rejected"

    def test_human_review_modify(self):
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        pending = g.get_pending_reviews()
        reviewed = g.submit_human_review(
            pending[0]["dossier_id"], "r1", HumanAction.MODIFY,
            modified_suggestion="HOLD",
        )
        assert reviewed["status"] == "modified"
        assert reviewed["ai_suggestion"] == "HOLD"

    def test_get_dossier(self):
        g = HITLGuardian()
        result = g.process_decision(_make_low_risk_input())
        dossier = g.get_dossier(result.dossier_id)
        assert dossier is not None
        assert dossier["dossier_id"] == result.dossier_id

    def test_get_dossier_not_found(self):
        g = HITLGuardian()
        assert g.get_dossier("nonexistent") is None

    def test_present_dossier(self):
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        presentation = g.present_dossier(result.dossier_id)
        assert presentation is not None
        assert "presentation" in presentation

    def test_audit_trail(self):
        g = HITLGuardian()
        g.process_decision(_make_low_risk_input())
        trail = g.get_audit_trail()
        assert len(trail) >= 2

    def test_audit_chain_verified(self):
        g = HITLGuardian()
        g.process_decision(_make_low_risk_input())
        g.process_decision(_make_high_risk_input())
        status = g.get_status()
        assert status["audit_chain_verified"] is True

    def test_metrics(self):
        g = HITLGuardian()
        g.process_decision(_make_low_risk_input())
        g.process_decision(_make_high_risk_input())
        metrics = g.get_metrics()
        assert "hitl_decisions_total" in metrics
        assert "hitl_auto_execute_total" in metrics
        assert "hitl_escalations_total" in metrics

    def test_status(self):
        g = HITLGuardian()
        g.process_decision(_make_low_risk_input())
        status = g.get_status()
        assert status["dossiers_total"] == 1
        assert "config" in status

    def test_reset(self):
        g = HITLGuardian()
        g.process_decision(_make_low_risk_input())
        g.reset()
        status = g.get_status()
        assert status["dossiers_total"] == 0
        assert status["audit_entries"] == 0

    def test_trace_id_present(self):
        g = HITLGuardian()
        result = g.process_decision(_make_low_risk_input())
        assert result.trace_id is not None
        assert len(result.trace_id) > 0

    def test_duration_positive(self):
        g = HITLGuardian()
        result = g.process_decision(_make_low_risk_input())
        assert result.duration_ms >= 0

    def test_results_history(self):
        g = HITLGuardian()
        g.process_decision(_make_low_risk_input())
        g.process_decision(_make_high_risk_input())
        results = g.get_results()
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Tests: API REST
# ---------------------------------------------------------------------------

class TestAPI:
    @pytest.fixture
    def client(self):
        from api_290 import app, _guardian
        _guardian.reset()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "endpoints" in data

    def test_schema(self, client):
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "input_cards" in data
        assert "output_cards" in data
        assert "POST /api/v1/process-decision" in data["input_cards"]

    def test_process_decision_auto(self, client):
        resp = client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.85,
            "context": {"current_price": 105.0, "predicted_move": 1.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.82,
            "uc322_conflict_detected": False,
            "ai_reasoning_steps": [
                {"step_type": "data", "description": "Tendencia alcista", "confidence": 0.9}
            ],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] == "auto_execute"

    def test_process_decision_escalate(self, client):
        resp = client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.55,
            "context": {"current_price": 100.0, "predicted_move": 8.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.40,
            "uc322_conflict_detected": True,
            "uc322_conflict_details": {"agents": ["uc329", "uc325"]},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] == "escalate"
        assert data["escalated"] is True

    def test_process_decision_blocked(self, client):
        resp = client.post("/api/v1/process-decision", json={
            "ai_suggestion": "SELL",
            "ai_confidence": 0.90,
            "context": {"current_price": 100.0, "predicted_move": 1.0},
            "uc087_integrity_passed": False,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.80,
            "uc322_conflict_detected": False,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["decision"] == "blocked"

    def test_submit_review(self, client):
        # First escalate
        resp = client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.55,
            "context": {"current_price": 100.0, "predicted_move": 8.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.40,
            "uc322_conflict_detected": True,
        })
        dossier_id = resp.get_json()["dossier_id"]

        # Then review
        resp2 = client.post("/api/v1/submit-review", json={
            "dossier_id": dossier_id,
            "reviewer_id": "trader_001",
            "action": "approve",
            "review_notes": "OK",
        })
        assert resp2.status_code == 200
        assert resp2.get_json()["status"] == "approved"

    def test_submit_review_not_found(self, client):
        resp = client.post("/api/v1/submit-review", json={
            "dossier_id": "nonexistent",
            "reviewer_id": "r1",
            "action": "approve",
        })
        assert resp.status_code == 404

    def test_submit_review_invalid_action(self, client):
        resp = client.post("/api/v1/submit-review", json={
            "dossier_id": "x",
            "reviewer_id": "r1",
            "action": "invalid_action",
        })
        assert resp.status_code == 400

    def test_pending_reviews(self, client):
        client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.55,
            "context": {"current_price": 100.0, "predicted_move": 8.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.40,
            "uc322_conflict_detected": True,
        })
        resp = client.get("/api/v1/pending-reviews")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1

    def test_get_dossier(self, client):
        resp = client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.85,
            "context": {"current_price": 105.0, "predicted_move": 1.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.82,
            "uc322_conflict_detected": False,
        })
        dossier_id = resp.get_json()["dossier_id"]
        resp2 = client.get(f"/api/v1/dossier/{dossier_id}")
        assert resp2.status_code == 200
        assert resp2.get_json()["dossier"]["dossier_id"] == dossier_id

    def test_get_dossier_not_found(self, client):
        resp = client.get("/api/v1/dossier/nonexistent")
        assert resp.status_code == 404

    def test_present_dossier(self, client):
        resp = client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.55,
            "context": {"current_price": 100.0, "predicted_move": 8.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.40,
            "uc322_conflict_detected": True,
        })
        dossier_id = resp.get_json()["dossier_id"]
        resp2 = client.get(f"/api/v1/present/{dossier_id}")
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert "presentation" in data
        assert "available_actions" in data

    def test_audit_trail(self, client):
        client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.85,
            "context": {"current_price": 105.0, "predicted_move": 1.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.82,
            "uc322_conflict_detected": False,
        })
        resp = client.get("/api/v1/audit-trail")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] > 0

    def test_status(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "config" in data
        assert "dossiers_total" in data

    def test_results(self, client):
        client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.85,
            "context": {"current_price": 105.0, "predicted_move": 1.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.82,
            "uc322_conflict_detected": False,
        })
        resp = client.get("/api/v1/results")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1

    def test_metrics(self, client):
        client.post("/api/v1/process-decision", json={
            "ai_suggestion": "BUY",
            "ai_confidence": 0.85,
            "context": {"current_price": 105.0, "predicted_move": 1.0},
            "uc087_integrity_passed": True,
            "uc162_llmops_passed": True,
            "uc325_reflection_score": 0.82,
            "uc322_conflict_detected": False,
        })
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "hitl_" in resp.get_data(as_text=True)

    def test_reset(self, client):
        resp = client.post("/api/v1/reset", json={})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests: Integración end-to-end
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_pipeline_auto_execute(self):
        """Pipeline completo: decisión de bajo riesgo → auto-execute."""
        g = HITLGuardian()
        result = g.process_decision(_make_low_risk_input())
        assert result.decision == HITLDecision.AUTO_EXECUTE
        # Verificar auditoría
        trail = g.get_audit_trail(dossier_id=result.dossier_id)
        assert len(trail) >= 2
        assert g.get_status()["audit_chain_verified"] is True

    def test_full_pipeline_escalate_and_approve(self):
        """Pipeline completo: decisión de alto riesgo → escalar → humano aprueba."""
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        assert result.decision == HITLDecision.ESCALATE
        pending = g.get_pending_reviews()
        assert len(pending) == 1
        reviewed = g.submit_human_review(
            pending[0]["dossier_id"], "reviewer_001", HumanAction.APPROVE,
            review_notes="Aprobado",
        )
        assert reviewed["status"] == "approved"
        assert len(g.get_pending_reviews()) == 0

    def test_full_pipeline_escalate_and_reject(self):
        """Pipeline completo: decisión de alto riesgo → escalar → humano rechaza."""
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        pending = g.get_pending_reviews()
        reviewed = g.submit_human_review(
            pending[0]["dossier_id"], "reviewer_001", HumanAction.REJECT,
            override_reason="Contexto macro desfavorable",
        )
        assert reviewed["status"] == "rejected"

    def test_full_pipeline_escalate_and_modify(self):
        """Pipeline completo: decisión de alto riesgo → escalar → humano modifica."""
        g = HITLGuardian()
        result = g.process_decision(_make_high_risk_input())
        pending = g.get_pending_reviews()
        reviewed = g.submit_human_review(
            pending[0]["dossier_id"], "reviewer_001", HumanAction.MODIFY,
            modified_suggestion="HOLD",
            override_reason="Reducir exposición",
        )
        assert reviewed["status"] == "modified"
        assert reviewed["ai_suggestion"] == "HOLD"

    def test_full_pipeline_blocked(self):
        """Pipeline completo: UC-087 rechaza → bloqueo automático."""
        g = HITLGuardian()
        result = g.process_decision(_make_blocked_input())
        assert result.decision == HITLDecision.BLOCKED
        assert "UC-087" in result.issues[0]

    def test_audit_trail_complete(self):
        """Verifica que el trail de auditoría registra todos los eventos."""
        g = HITLGuardian()
        # Auto-execute
        g.process_decision(_make_low_risk_input())
        # Escalate
        g.process_decision(_make_high_risk_input())
        # Block
        g.process_decision(_make_blocked_input())

        trail = g.get_audit_trail()
        # At least 2 events per decision (created + auto/escalate/block)
        assert len(trail) >= 6
        assert g.get_status()["audit_chain_verified"] is True

    def test_multiple_decisions_and_reset(self):
        """Múltiples decisiones seguidas de reset."""
        g = HITLGuardian()
        for i in range(5):
            inp = _make_low_risk_input()
            inp.decision_id = f"multi_{i}"
            g.process_decision(inp)
        assert g.get_status()["dossiers_total"] == 5
        g.reset()
        assert g.get_status()["dossiers_total"] == 0

    def test_principle_evidence_not_order(self):
        """
        Verifica el principio: 'Un modelo genera evidencia. La evidencia no es una orden.'
        UC-315 genera una sugerencia (evidencia), pero la decisión final
        depende del guardian HITL, no de UC-315 directamente.
        """
        g = HITLGuardian()
        # UC-315 sugiere BUY con alta confianza
        inp = _make_high_risk_input()
        inp.ai_suggestion = "BUY"
        inp.ai_confidence = 0.55  # pero confianza baja

        result = g.process_decision(inp)
        # El guardian debe escalar, no auto-ejecutar
        assert result.decision == HITLDecision.ESCALATE
        # La sugerencia de UC-315 es evidencia, no orden
        assert result.dossier["ai_suggestion"] == "BUY"
        # Pero la decisión del guardian es ESCALATE, no BUY
        assert result.decision.value != "BUY"
