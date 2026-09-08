"""
UC-290 — Guardian HITL (orquestador central).

El guardian es el componente híbrido que:
- Fast path: deja pasar decisiones de bajo riesgo automáticamente.
- Slow path: construye el Expediente de Decisión y escala a humano.

Flujo:
1. UC-315 genera una decisión (evidencia, no orden).
2. Guardian recibe la decisión + validaciones de UC-087, UC-162, UC-325, UC-322, UC-329.
3. RiskAssessor evalúa riesgo y confianza.
4. DossierBuilder construye el Expediente de Decisión.
5. Si riesgo alto o confianza baja → EscalationEngine activa punto de escalamiento.
6. Si riesgo bajo y confianza alta → auto-execute (fast path).
7. AuditTrail registra todo.
8. UC-317 solo ejecuta si el guardian lo permite.
"""

import time
from typing import Dict, Any, List, Optional

from models_290 import (
    HITLConfig,
    DecisionInput,
    DecisionDossier,
    RiskAssessment,
    HITLResult,
    HITLDecision,
    DossierStatus,
    HumanAction,
    HumanReview,
    ReasoningStep,
    ReasoningStepType,
    generate_id,
)
from risk_assessor import RiskAssessor
from decision_dossier import DossierBuilder
from escalation_engine import EscalationEngine
from human_review_interface import HumanReviewInterface
from audit_trail import AuditTrail
from observability_290 import ObservabilityManager


class HITLGuardian:
    """Guardian HITL — checkpoint humano entre UC-315 y UC-317."""

    def __init__(self, config: HITLConfig = None):
        self.config = config or HITLConfig()
        self.risk_assessor = RiskAssessor(self.config)
        self.dossier_builder = DossierBuilder()
        self.escalation_engine = EscalationEngine(self.config)
        self.human_interface = HumanReviewInterface()
        self.audit_trail = AuditTrail()
        self.observability = ObservabilityManager()

        # Estado
        self.dossiers: Dict[str, DecisionDossier] = {}
        self.results: List[Dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # Pipeline principal
    # -----------------------------------------------------------------------

    def process_decision(self, decision_input: DecisionInput) -> HITLResult:
        """
        Procesa una decisión de UC-315 a través del pipeline HITL completo.

        1. Evalúa riesgo.
        2. Construye expediente.
        3. Decide: auto-execute o escalar.
        4. Registra en auditoría.
        """
        start_time = time.time()
        trace_id = decision_input.trace_id or generate_id()
        decision_input.trace_id = trace_id

        span = self.observability.start_span("hitl_process_decision", trace_id)

        # 1. Evaluar riesgo
        self.observability.log("INFO", "Evaluando riesgo de decisión", trace_id)
        risk_assessment = self.risk_assessor.assess(decision_input)

        # 2. Construir expediente
        self.observability.log("INFO", "Construyendo expediente de decisión", trace_id)
        dossier = self.dossier_builder.build(
            decision_input,
            risk_assessment,
            self.config.escalation_timeout_sec,
        )
        self.dossiers[dossier.dossier_id] = dossier

        # Registrar creación en auditoría
        self.audit_trail.record_dossier_created(dossier)

        # 3. Decidir: auto-execute o escalar
        result = HITLResult(
            trace_id=trace_id,
            dossier_id=dossier.dossier_id,
            risk_level=risk_assessment.risk_level.value,
            risk_score=risk_assessment.risk_score,
            confidence_score=risk_assessment.confidence_score,
        )

        # Verificar bloqueos duros
        blocked = self._check_hard_blocks(decision_input, risk_assessment)
        if blocked:
            dossier.status = DossierStatus.PENDING_REVIEW
            dossier.decision = HITLDecision.BLOCKED
            result.decision = HITLDecision.BLOCKED
            result.escalated = True
            result.escalation_reasons = risk_assessment.escalation_reasons
            result.issues = [blocked]
            self.audit_trail.record_blocked(dossier, blocked)
            self.observability.increment("hitl_blocked_total")
            self.observability.log("WARN", f"Decisión bloqueada: {blocked}", trace_id)
        elif risk_assessment.requires_escalation:
            # Escalar a humano
            notification = self.escalation_engine.escalate(dossier)
            result.decision = HITLDecision.ESCALATE
            result.escalated = True
            result.escalation_reasons = risk_assessment.escalation_reasons
            self.audit_trail.record_escalation(dossier, risk_assessment.escalation_reasons)
            self.observability.increment("hitl_escalations_total")
            self.observability.log("WARN", "Punto de escalamiento activado", trace_id, {
                "reasons": risk_assessment.escalation_reasons,
            })
        else:
            # Auto-execute (fast path)
            dossier.status = DossierStatus.AUTO_EXECUTED
            dossier.decision = HITLDecision.AUTO_EXECUTE
            result.decision = HITLDecision.AUTO_EXECUTE
            result.final_action = decision_input.ai_suggestion
            self.audit_trail.record_auto_execute(dossier)
            self.observability.increment("hitl_auto_execute_total")
            self.observability.log("INFO", "Auto-execute aprobado (fast path)", trace_id)

        # Completar resultado
        result.dossier = dossier.to_dict()
        result.duration_ms = (time.time() - start_time) * 1000

        self.observability.end_span(span)
        self.observability.gauge("hitl_guardian_duration_ms", result.duration_ms)
        self.observability.increment("hitl_decisions_total")

        self.results.append(result.to_dict())
        return result

    def _check_hard_blocks(self, decision_input: DecisionInput, risk: RiskAssessment) -> Optional[str]:
        """Verifica bloqueos duros que no pueden ser auto-ejecutados."""
        if not decision_input.uc087_integrity_passed:
            return "UC-087 rechazó integridad criptográfica: bloqueo automático."
        if not decision_input.uc162_llmops_passed:
            return "UC-162 rechazó gobernanza LLMOps: bloqueo automático."
        if risk.risk_level.value == "critical" and self.config.require_human_for_critical:
            return "Riesgo crítico: requiere intervención humana obligatoria."
        return None

    # -----------------------------------------------------------------------
    # Revisión humana
    # -----------------------------------------------------------------------

    def submit_human_review(
        self,
        dossier_id: str,
        reviewer_id: str,
        action: HumanAction,
        modified_suggestion: str = "",
        override_reason: str = "",
        review_notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Registra la revisión humana de un expediente escalado."""
        dossier = self.escalation_engine.submit_review(
            dossier_id, reviewer_id, action,
            modified_suggestion, override_reason, review_notes,
        )
        if dossier is None:
            return None

        # Actualizar en store local
        self.dossiers[dossier_id] = dossier

        # Registrar en auditoría
        review_data = {
            "reviewer_id": reviewer_id,
            "action": action.value,
            "modified_suggestion": modified_suggestion,
            "override_reason": override_reason,
            "review_notes": review_notes,
        }
        self.audit_trail.record_human_review(dossier, review_data)

        # Actualizar métricas
        if action == HumanAction.APPROVE:
            self.observability.increment("hitl_human_approve_total")
        elif action == HumanAction.MODIFY:
            self.observability.increment("hitl_human_modify_total")
        elif action == HumanAction.REJECT:
            self.observability.increment("hitl_human_reject_total")

        self.observability.log("INFO", f"Revisión humana: {action.value}", dossier.trace_id, review_data)

        return dossier.to_dict()

    def get_pending_reviews(self) -> List[Dict[str, Any]]:
        """Retorna expedientes pendientes de revisión humana."""
        self.escalation_engine.check_timeouts()
        return self.escalation_engine.get_pending()

    def present_dossier(self, dossier_id: str) -> Optional[Dict[str, Any]]:
        """Presenta un expediente para revisión humana."""
        dossier = self.dossiers.get(dossier_id)
        if dossier is None:
            return None
        return self.human_interface.present_dossier(dossier)

    # -----------------------------------------------------------------------
    # Consultas
    # -----------------------------------------------------------------------

    def get_dossier(self, dossier_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un expediente por ID."""
        dossier = self.dossiers.get(dossier_id)
        return dossier.to_dict() if dossier else None

    def get_audit_trail(self, dossier_id: str = None, trace_id: str = None) -> List[Dict[str, Any]]:
        """Obtiene entradas del trail de auditoría."""
        return self.audit_trail.get_entries(dossier_id, trace_id)

    def get_status(self) -> Dict[str, Any]:
        """Estado del guardian."""
        return {
            "config": self.config.to_dict(),
            "dossiers_total": len(self.dossiers),
            "pending_reviews": len(self.escalation_engine.pending_reviews),
            "completed_reviews": len(self.escalation_engine.completed_reviews),
            "audit_entries": len(self.audit_trail.entries),
            "audit_chain_verified": self.audit_trail.verify_chain(),
            "observability": self.observability.get_summary(),
        }

    def get_metrics(self) -> str:
        """Métricas Prometheus."""
        return self.observability.export_prometheus()

    def get_results(self) -> List[Dict[str, Any]]:
        """Retorna todos los resultados del pipeline."""
        return self.results

    # -----------------------------------------------------------------------
    # Gestión
    # -----------------------------------------------------------------------

    def reset(self, config: HITLConfig = None):
        """Reinicia el guardian."""
        if config:
            self.config = config
            self.risk_assessor = RiskAssessor(self.config)
            self.escalation_engine = EscalationEngine(self.config)
        self.dossiers.clear()
        self.results.clear()
        self.escalation_engine.reset()
        self.audit_trail.reset()
        self.observability.reset()

    def check_timeouts(self) -> List[str]:
        """Verifica y expira expedientes con timeout."""
        expired = self.escalation_engine.check_timeouts()
        for dossier_id in expired:
            dossier = self.dossiers.get(dossier_id)
            if dossier:
                self.audit_trail.record_timeout(dossier)
                self.observability.increment("hitl_timeout_total")
        return expired
