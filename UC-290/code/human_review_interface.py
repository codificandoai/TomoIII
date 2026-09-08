"""
UC-290 — Interfaz de Revisión Humana.

Proporciona:
- Presentación del Expediente de Decisión al revisor.
- Acciones: approve, modify, reject, request_more_info, delegate.
- Resumen ejecutivo del razonamiento transparente.
- Formato JSON para integración con Slack/Teams/webhooks.
"""

import time
from typing import Dict, Any, Optional

from models_290 import (
    DecisionDossier,
    HumanReview,
    HumanAction,
    DossierStatus,
)
from decision_dossier import DossierBuilder


class HumanReviewInterface:
    """Interfaz para que un humano revise y decida sobre un expediente."""

    def __init__(self):
        self.builder = DossierBuilder()

    def present_dossier(self, dossier: DecisionDossier) -> Dict[str, Any]:
        """
        Presenta el expediente en formato estructurado para el revisor.
        En producción, esto se enviaría a Slack/Teams/email.
        """
        summary = self.builder.to_summary(dossier)
        return {
            "presentation": summary,
            "dossier": dossier.to_dict(),
            "available_actions": [a.value for a in HumanAction],
            "instructions": (
                "Revise el razonamiento paso a paso. "
                "Puede: approve (aprobar), modify (modificar sugerencia), "
                "reject (rechazar), request_more_info (solicitar más información), "
                "delegate (delegar a otro revisor)."
            ),
        }

    def create_review(
        self,
        reviewer_id: str,
        action: HumanAction,
        modified_suggestion: str = "",
        override_reason: str = "",
        review_notes: str = "",
    ) -> HumanReview:
        """Crea un objeto HumanReview."""
        return HumanReview(
            reviewer_id=reviewer_id,
            action=action,
            modified_suggestion=modified_suggestion,
            override_reason=override_reason,
            review_notes=review_notes,
        )

    def format_for_slack(self, dossier: DecisionDossier) -> Dict[str, Any]:
        """Formatea el expediente para envío vía Slack/Teams webhook."""
        risk = dossier.risk_assessment
        color = "#36a64f"  # verde
        if risk:
            if risk.risk_level.value == "critical":
                color = "#ff0000"
            elif risk.risk_level.value == "high":
                color = "#ff6600"
            elif risk.risk_level.value == "medium":
                color = "#ffcc00"

        fields = []
        for step in dossier.reasoning_steps:
            fields.append({
                "title": f"Paso {step.step_number} [{step.source}]",
                "value": step.description,
                "short": False,
            })

        return {
            "attachments": [
                {
                    "color": color,
                    "title": f"Expediente de Decisión #{dossier.dossier_id[:8]}",
                    "text": f"Sugerencia IA: {dossier.ai_suggestion}\n"
                            f"Confianza: {dossier.ai_confidence:.2f}\n"
                            f"Riesgo: {risk.risk_level.value if risk else 'N/A'}\n"
                            f"Estado: {dossier.status.value}",
                    "fields": fields[:10],  # Slack limit
                    "footer": f"Trace: {dossier.trace_id[:8]}",
                    "ts": int(dossier.timestamp),
                }
            ]
        }

    def format_for_webhook(self, dossier: DecisionDossier, webhook_url: str = "") -> Dict[str, Any]:
        """Formatea el expediente para envío vía webhook genérico."""
        return {
            "webhook_url": webhook_url,
            "event": "hitl_escalation",
            "dossier_id": dossier.dossier_id,
            "trace_id": dossier.trace_id,
            "risk_level": dossier.risk_assessment.risk_level.value if dossier.risk_assessment else "unknown",
            "ai_suggestion": dossier.ai_suggestion,
            "escalation_reasons": dossier.risk_assessment.escalation_reasons if dossier.risk_assessment else [],
            "reasoning_summary": [s.to_dict() for s in dossier.reasoning_steps],
            "expires_at": dossier.expires_at,
        }
