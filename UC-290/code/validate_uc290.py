"""
UC-290 — Validación operacional del HITL Guardian.

Ejecuta checks funcionales de todos los componentes.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models_290 import (
    HITLConfig,
    DecisionInput,
    ReasoningStep,
    ReasoningStepType,
    HumanAction,
    HITLDecision,
    RiskLevel,
    DossierStatus,
    generate_id,
)
from risk_assessor import RiskAssessor
from decision_dossier import DossierBuilder
from escalation_engine import EscalationEngine
from human_review_interface import HumanReviewInterface
from audit_trail import AuditTrail
from observability_290 import ObservabilityManager
from hitl_guardian import HITLGuardian


def _make_reasoning_step(num, desc, confidence=0.8):
    return ReasoningStep(
        step_number=num,
        step_type=ReasoningStepType.INFERENCE,
        description=desc,
        confidence=confidence,
        source="uc315",
    )


def _make_low_risk_input():
    return DecisionInput(
        decision_id="val_001",
        trace_id="val_trace_001",
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
        decision_id="val_002",
        trace_id="val_trace_002",
        context={"current_price": 100.0, "predicted_move": 8.0, "volume": 95000},
        ai_suggestion="BUY",
        ai_confidence=0.55,
        ai_reasoning_steps=[_make_reasoning_step(1, "Volatilidad extrema")],
        uc087_integrity_passed=True,
        uc162_llmops_passed=True,
        uc325_reflection_score=0.40,
        uc322_conflict_detected=True,
        uc322_conflict_details={"agents": ["uc329", "uc325"]},
    )


def _make_blocked_input():
    return DecisionInput(
        decision_id="val_003",
        trace_id="val_trace_003",
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
# Validaciones
# ---------------------------------------------------------------------------

def validate_risk_assessor_low():
    ra = RiskAssessor()
    risk = ra.assess(_make_low_risk_input())
    assert risk.risk_level in (RiskLevel.NONE, RiskLevel.LOW), f"Expected low risk, got {risk.risk_level}"
    assert not risk.requires_escalation, "Low risk should not escalate"
    return True


def validate_risk_assessor_high():
    ra = RiskAssessor()
    risk = ra.assess(_make_high_risk_input())
    assert risk.requires_escalation, "High risk should escalate"
    assert len(risk.escalation_reasons) > 0, "Should have escalation reasons"
    return True


def validate_risk_assessor_blocked():
    ra = RiskAssessor()
    risk = ra.assess(_make_blocked_input())
    assert risk.requires_escalation, "Blocked decision should escalate"
    return True


def validate_dossier_builder():
    ra = RiskAssessor()
    risk = ra.assess(_make_low_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_low_risk_input(), risk)
    assert dossier.dossier_id != ""
    assert len(dossier.reasoning_steps) > 0
    assert dossier.content_hash != ""
    assert dossier.status == DossierStatus.AUTO_EXECUTED
    return True


def validate_dossier_builder_escalation():
    ra = RiskAssessor()
    risk = ra.assess(_make_high_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_high_risk_input(), risk)
    assert dossier.status == DossierStatus.PENDING_REVIEW
    assert dossier.decision == HITLDecision.ESCALATE
    return True


def validate_escalation_engine():
    ee = EscalationEngine()
    ra = RiskAssessor()
    risk = ra.assess(_make_high_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_high_risk_input(), risk)
    notification = ee.escalate(dossier)
    assert notification["status"] == "pending"
    assert len(ee.get_pending()) == 1

    # Submit review
    reviewed = ee.submit_review(
        dossier.dossier_id, "reviewer_001", HumanAction.APPROVE,
        review_notes="OK",
    )
    assert reviewed.status == DossierStatus.APPROVED
    assert len(ee.get_pending()) == 0
    return True


def validate_escalation_reject():
    ee = EscalationEngine()
    ra = RiskAssessor()
    risk = ra.assess(_make_high_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_high_risk_input(), risk)
    ee.escalate(dossier)
    reviewed = ee.submit_review(
        dossier.dossier_id, "reviewer_001", HumanAction.REJECT,
        override_reason="Contexto macro desfavorable",
    )
    assert reviewed.status == DossierStatus.REJECTED
    return True


def validate_escalation_modify():
    ee = EscalationEngine()
    ra = RiskAssessor()
    risk = ra.assess(_make_high_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_high_risk_input(), risk)
    ee.escalate(dossier)
    reviewed = ee.submit_review(
        dossier.dossier_id, "reviewer_001", HumanAction.MODIFY,
        modified_suggestion="HOLD",
        override_reason="Reducir exposición",
    )
    assert reviewed.status == DossierStatus.MODIFIED
    assert reviewed.ai_suggestion == "HOLD"
    return True


def validate_human_review_interface():
    hi = HumanReviewInterface()
    ra = RiskAssessor()
    risk = ra.assess(_make_high_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_high_risk_input(), risk)
    presentation = hi.present_dossier(dossier)
    assert "presentation" in presentation
    assert "available_actions" in presentation
    assert "approve" in presentation["available_actions"]

    slack = hi.format_for_slack(dossier)
    assert "attachments" in slack

    webhook = hi.format_for_webhook(dossier, "https://hooks.slack.com/...")
    assert webhook["event"] == "hitl_escalation"
    return True


def validate_audit_trail():
    trail = AuditTrail()
    ra = RiskAssessor()
    risk = ra.assess(_make_low_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_low_risk_input(), risk)

    trail.record_dossier_created(dossier)
    trail.record_auto_execute(dossier)

    entries = trail.get_entries()
    assert len(entries) == 2
    assert trail.verify_chain() is True

    summary = trail.get_summary()
    assert summary["total_entries"] == 2
    assert summary["chain_verified"] is True
    return True


def validate_audit_trail_tamper_detection():
    trail = AuditTrail()
    ra = RiskAssessor()
    risk = ra.assess(_make_low_risk_input())
    builder = DossierBuilder()
    dossier = builder.build(_make_low_risk_input(), risk)
    trail.record_dossier_created(dossier)

    # Tamper
    trail.entries[0].event = "TAMPERED"
    assert trail.verify_chain() is False, "Tampered chain should not verify"
    return True


def validate_observability():
    om = ObservabilityManager()
    om.log("INFO", "test")
    om.increment("test_total")
    om.gauge("test_gauge", 42.0)
    span = om.start_span("test_op")
    om.end_span(span)

    prom = om.export_prometheus()
    assert "test_total" in prom
    assert "test_gauge" in prom
    assert 'component="uc290_hitl"' in prom

    summary = om.get_summary()
    assert summary["log_count"] == 1
    assert summary["metric_count"] == 2
    return True


def validate_guardian_auto_execute():
    g = HITLGuardian()
    result = g.process_decision(_make_low_risk_input())
    assert result.decision == HITLDecision.AUTO_EXECUTE
    assert not result.escalated
    assert result.final_action == "BUY"
    return True


def validate_guardian_escalate():
    g = HITLGuardian()
    result = g.process_decision(_make_high_risk_input())
    assert result.decision == HITLDecision.ESCALATE
    assert result.escalated
    assert len(result.escalation_reasons) > 0
    return True


def validate_guardian_blocked():
    g = HITLGuardian()
    result = g.process_decision(_make_blocked_input())
    assert result.decision == HITLDecision.BLOCKED
    assert len(result.issues) > 0
    return True


def validate_guardian_human_review():
    g = HITLGuardian()
    result = g.process_decision(_make_high_risk_input())
    assert result.escalated

    pending = g.get_pending_reviews()
    assert len(pending) == 1

    dossier_id = pending[0]["dossier_id"]
    reviewed = g.submit_human_review(
        dossier_id, "reviewer_001", HumanAction.APPROVE,
        review_notes="Aprobado tras revisión",
    )
    assert reviewed is not None
    assert reviewed["status"] == "approved"

    pending_after = g.get_pending_reviews()
    assert len(pending_after) == 0
    return True


def validate_guardian_audit():
    g = HITLGuardian()
    g.process_decision(_make_low_risk_input())
    g.process_decision(_make_high_risk_input())

    trail = g.get_audit_trail()
    assert len(trail) >= 4  # at least 2 events per decision
    assert g.get_status()["audit_chain_verified"] is True
    return True


def validate_guardian_metrics():
    g = HITLGuardian()
    g.process_decision(_make_low_risk_input())
    g.process_decision(_make_high_risk_input())
    metrics = g.get_metrics()
    assert "hitl_decisions_total" in metrics
    assert "hitl_auto_execute_total" in metrics
    assert "hitl_escalations_total" in metrics
    return True


def validate_guardian_reset():
    g = HITLGuardian()
    g.process_decision(_make_low_risk_input())
    g.reset()
    status = g.get_status()
    assert status["dossiers_total"] == 0
    assert status["audit_entries"] == 0
    return True


def validate_guardian_status():
    g = HITLGuardian()
    g.process_decision(_make_low_risk_input())
    status = g.get_status()
    assert "config" in status
    assert status["dossiers_total"] == 1
    assert "audit_chain_verified" in status
    return True


def validate_guardian_present_dossier():
    g = HITLGuardian()
    result = g.process_decision(_make_high_risk_input())
    presentation = g.present_dossier(result.dossier_id)
    assert presentation is not None
    assert "presentation" in presentation
    assert "available_actions" in presentation
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

VALIDATIONS = [
    ("RiskAssessor low risk", validate_risk_assessor_low),
    ("RiskAssessor high risk", validate_risk_assessor_high),
    ("RiskAssessor blocked", validate_risk_assessor_blocked),
    ("DossierBuilder auto-execute", validate_dossier_builder),
    ("DossierBuilder escalation", validate_dossier_builder_escalation),
    ("EscalationEngine approve", validate_escalation_engine),
    ("EscalationEngine reject", validate_escalation_reject),
    ("EscalationEngine modify", validate_escalation_modify),
    ("HumanReviewInterface", validate_human_review_interface),
    ("AuditTrail", validate_audit_trail),
    ("AuditTrail tamper detection", validate_audit_trail_tamper_detection),
    ("ObservabilityManager", validate_observability),
    ("Guardian auto-execute", validate_guardian_auto_execute),
    ("Guardian escalate", validate_guardian_escalate),
    ("Guardian blocked", validate_guardian_blocked),
    ("Guardian human review", validate_guardian_human_review),
    ("Guardian audit", validate_guardian_audit),
    ("Guardian metrics", validate_guardian_metrics),
    ("Guardian reset", validate_guardian_reset),
    ("Guardian status", validate_guardian_status),
    ("Guardian present dossier", validate_guardian_present_dossier),
]


def main():
    print("=" * 60)
    print("UC-290 — HITL Guardian Validación Operacional")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, func in VALIDATIONS:
        try:
            func()
            print(f"  [OK] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print("-" * 60)
    print(f"Resultado: {passed}/{passed + failed} OK, {failed} failed")
    if failed == 0:
        print("[OK] Todos los procesos están funcionando correctamente.")
    else:
        print("[FAIL] Hay procesos que no funcionan correctamente.")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
