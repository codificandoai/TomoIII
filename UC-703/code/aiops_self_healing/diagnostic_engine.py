"""Diagnóstico asistido por LLM con evidencia verificable."""
from __future__ import annotations

from typing import Any, Dict, List

from aiops_self_healing.models_aiops import (
    CorrelationGroup,
    Diagnosis,
    NormalizedAlert,
    RemediationType,
)


class DiagnosticEngine:
    """
    Genera hipótesis de diagnóstico a partir de un grupo de alertas correlacionadas.
    No ejecuta acciones; produce evidencia y propone runbooks/remediaciones.
    """

    def diagnose(
        self,
        group: CorrelationGroup,
        alerts: List[NormalizedAlert],
    ) -> Diagnosis:
        symptoms = ", ".join(group.symptoms) or "unknown"

        if group.category == "availability":
            root_cause = "Possible capacity exhaustion or dependency failure"
            props = [RemediationType.AUTOSCALE, RemediationType.FALLBACK_PROVIDER, RemediationType.HEALTH_TEST]
        elif group.category == "latency":
            root_cause = "Possible model or retrieval latency spike"
            props = [RemediationType.RATE_LIMIT, RemediationType.FALLBACK_MODEL, RemediationType.AUTOSCALE]
        elif group.category == "quality":
            root_cause = "Possible prompt/model drift or bad retrieval context"
            props = [RemediationType.ROLLBACK_PROMPT, RemediationType.ROLLBACK_MODEL, RemediationType.HEALTH_TEST]
        elif group.category == "security":
            root_cause = "Possible prompt injection, jailbreak or unauthorized tool use"
            props = [RemediationType.CIRCUIT_BREAKER, RemediationType.SANDBOX_ISOLATION, RemediationType.HUMAN_ESCALATION]
        elif group.category == "compliance":
            root_cause = "Possible PII leak or policy violation"
            props = [RemediationType.SANDBOX_ISOLATION, RemediationType.HUMAN_ESCALATION]
        elif group.category == "cost":
            root_cause = "Possible token consumption spike or abusive traffic"
            props = [RemediationType.RATE_LIMIT, RemediationType.AUTOSCALE]
        else:
            root_cause = "Undetermined; requires human analysis"
            props = [RemediationType.HUMAN_ESCALATION]

        requires_human = group.severity in {"critical", "high"} or group.category in {"security", "compliance"}

        evidence: List[Dict[str, Any]] = []
        for alert in alerts:
            if alert.alert_id in group.alert_ids:
                evidence.append({
                    "alert_id": alert.alert_id,
                    "metric": alert.metric,
                    "value": alert.value,
                    "threshold": alert.threshold,
                    "resource": alert.resource,
                    "metadata": alert.metadata,
                })

        return Diagnosis(
            group_id=group.group_id,
            summary=f"Detected {group.category} anomaly on {group.resource}: {symptoms}",
            root_cause_hypothesis=root_cause,
            confidence=0.7 if group.severity != "critical" else 0.9,
            proposed_remediations=props,
            evidence=evidence,
            requires_human_review=requires_human,
        )
