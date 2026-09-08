"""
UC-290 — Motor de Puntos de Escalamiento.

Gestiona:
- Activación de puntos de escalamiento obligatorios.
- Notificaciones a revisores humanos.
- Timeouts de escalamiento.
- Políticas anti-sobredelegación.
- Cola de expedientes pendientes de revisión.
"""

import time
from typing import Dict, Any, List, Optional

from models_290 import (
    HITLConfig,
    DecisionDossier,
    DossierStatus,
    HITLDecision,
    HumanReview,
    HumanAction,
    generate_id,
)


class EscalationEngine:
    """Gestiona puntos de escalamiento y revisión humana."""

    def __init__(self, config: HITLConfig = None):
        self.config = config or HITLConfig()
        self.pending_reviews: Dict[str, DecisionDossier] = {}
        self.completed_reviews: Dict[str, HumanReview] = {}
        self.escalation_history: List[Dict[str, Any]] = []

    def escalate(self, dossier: DecisionDossier) -> Dict[str, Any]:
        """
        Activa el punto de escalamiento para un expediente.
        """
        dossier.status = DossierStatus.PENDING_REVIEW
        dossier.decision = HITLDecision.ESCALATE

        self.pending_reviews[dossier.dossier_id] = dossier

        notification = {
            "escalation_id": generate_id(),
            "dossier_id": dossier.dossier_id,
            "trace_id": dossier.trace_id,
            "timestamp": time.time(),
            "risk_level": dossier.risk_assessment.risk_level.value if dossier.risk_assessment else "unknown",
            "reasons": dossier.risk_assessment.escalation_reasons if dossier.risk_assessment else [],
            "status": "pending",
            "expires_at": dossier.expires_at,
        }

        self.escalation_history.append(notification)
        return notification

    def submit_review(
        self,
        dossier_id: str,
        reviewer_id: str,
        action: HumanAction,
        modified_suggestion: str = "",
        override_reason: str = "",
        review_notes: str = "",
    ) -> Optional[DecisionDossier]:
        """
        Registra la revisión humana de un expediente pendiente.
        """
        if dossier_id not in self.pending_reviews:
            return None

        dossier = self.pending_reviews[dossier_id]
        review_start = dossier.timestamp
        review_duration = time.time() - review_start

        review = HumanReview(
            reviewer_id=reviewer_id,
            action=action,
            modified_suggestion=modified_suggestion,
            override_reason=override_reason,
            review_notes=review_notes,
            review_duration_sec=review_duration,
        )

        self.completed_reviews[dossier_id] = review
        dossier.human_review = review.to_dict()

        # Actualizar estado del expediente según la acción
        if action == HumanAction.APPROVE:
            dossier.status = DossierStatus.APPROVED
            dossier.decision = HITLDecision.APPROVED
        elif action == HumanAction.MODIFY:
            dossier.status = DossierStatus.MODIFIED
            dossier.decision = HITLDecision.MODIFIED
            dossier.ai_suggestion = modified_suggestion or dossier.ai_suggestion
        elif action == HumanAction.REJECT:
            dossier.status = DossierStatus.REJECTED
            dossier.decision = HITLDecision.REJECTED
        elif action == HumanAction.REQUEST_MORE_INFO:
            # Mantener pendiente pero registrar la solicitud
            dossier.status = DossierStatus.PENDING_REVIEW
            review_notes = f"[REQUEST_MORE_INFO] {review_notes}"
        elif action == HumanAction.DELEGATE:
            # Delegar a otro revisor (mantener pendiente)
            dossier.status = DossierStatus.PENDING_REVIEW

        # Recalcular hash
        dossier.compute_hash()

        # Mover a completados si no sigue pendiente
        if dossier.status != DossierStatus.PENDING_REVIEW:
            del self.pending_reviews[dossier_id]

        return dossier

    def check_timeouts(self) -> List[str]:
        """Verifica expedientes que han excedido el timeout de escalamiento."""
        now = time.time()
        expired_ids = []
        for dossier_id, dossier in list(self.pending_reviews.items()):
            if now > dossier.expires_at:
                dossier.status = DossierStatus.EXPIRED
                dossier.decision = HITLDecision.TIMEOUT
                expired_ids.append(dossier_id)
                del self.pending_reviews[dossier_id]
        return expired_ids

    def get_pending(self) -> List[Dict[str, Any]]:
        """Retorna expedientes pendientes de revisión."""
        return [
            {
                "dossier_id": d.dossier_id,
                "trace_id": d.trace_id,
                "ai_suggestion": d.ai_suggestion,
                "risk_level": d.risk_assessment.risk_level.value if d.risk_assessment else "unknown",
                "escalation_reasons": d.risk_assessment.escalation_reasons if d.risk_assessment else [],
                "expires_at": d.expires_at,
                "timestamp": d.timestamp,
            }
            for d in self.pending_reviews.values()
        ]

    def get_review(self, dossier_id: str) -> Optional[HumanReview]:
        """Obtiene la revisión de un expediente completado."""
        return self.completed_reviews.get(dossier_id)

    def get_escalation_history(self) -> List[Dict[str, Any]]:
        """Retorna el historial de escalamientos."""
        return self.escalation_history

    def reset(self):
        """Reinicia el motor de escalamiento."""
        self.pending_reviews.clear()
        self.completed_reviews.clear()
        self.escalation_history.clear()
