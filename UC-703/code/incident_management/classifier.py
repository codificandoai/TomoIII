"""Clasifica incidentes según impacto, urgencia, riesgo, regulatorio y alcance."""
from __future__ import annotations

from typing import Any, Dict

from incident_management.models_incident import Incident, Severity


class IncidentClassifier:
    """
    Clasifica automáticamente la severidad de incidentes LLMOps basándose en
    múltiples dimensiones: usuarios afectados, criticidad del proceso, riesgo de
    seguridad, incumplimiento regulatorio, degradación de calidad y consumo del
    presupuesto de error.
    """

    SEVERITY_SCORES = {
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }

    def classify(self, incident: Incident) -> str:
        scores: Dict[str, int] = {}

        # 1. Impacto por usuarios afectados
        scores["users"] = self._score_users(incident.affected_users)

        # 2. Urgencia y criticidad del proceso
        scores["urgency"] = self._score_urgency(incident.urgency)

        # 3. Riesgo de seguridad
        scores["security"] = self._score_security(incident.category, incident.tags)

        # 4. Criticidad regulatoria
        scores["regulatory"] = self._score_regulatory(incident.regulatory_criticality)

        # 5. Degradación de calidad / disponibilidad / coste
        scores["operational"] = self._score_operational(incident.category, incident.impact)

        total = sum(scores.values())
        # Max possible ~ 4*5 = 20, map thresholds
        if total >= 16:
            return Severity.CRITICAL.value
        if total >= 12:
            return Severity.HIGH.value
        if total >= 7:
            return Severity.MEDIUM.value
        return Severity.LOW.value

    def _score_users(self, affected: int) -> int:
        if affected >= 10000:
            return 4
        if affected >= 1000:
            return 3
        if affected >= 100:
            return 2
        return 1

    def _score_urgency(self, urgency: str) -> int:
        return {"immediate": 4, "high": 3, "normal": 2, "low": 1}.get(urgency, 1)

    def _score_security(self, category: str, tags: Any) -> int:
        if category == "security" or any(t in {"prompt_injection", "jailbreak", "data_exfiltration", "unauthorized_tool"} for t in tags or []):
            return 4
        if any(t in {"pii_leak", "toxicity"} for t in tags or []):
            return 3
        return 1

    def _score_regulatory(self, regulatory: str) -> int:
        return {"none": 1, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(regulatory, 1)

    def _score_operational(self, category: str, impact: Dict[str, Any]) -> int:
        if category == "availability":
            return 4
        if category == "latency":
            return 2
        if category == "quality":
            return 3
        if category == "cost":
            budget_consumed = impact.get("error_budget_consumed", 0)
            if budget_consumed > 0.5:
                return 3
            if budget_consumed > 0.2:
                return 2
        if category == "compliance":
            return 4
        return 1
