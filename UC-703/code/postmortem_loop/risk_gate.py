"""Puerta de supervisión humana configurable por nivel de riesgo."""
from __future__ import annotations

from postmortem_loop.models_pm import RootCauseHypothesis


class RiskGate:
    """
    Decide si un post-mortem avanza automáticamente o requiere
    aprobación humana, basándose en la severidad del incidente y la
    confianza de la hipótesis de causa raíz.
    """

    def __init__(
        self,
        auto_severities: tuple = ("low", "medium"),
        auto_confidence_threshold: float = 0.75,
    ) -> None:
        self.auto_severities = set(auto_severities)
        self.auto_confidence_threshold = auto_confidence_threshold

    def needs_human_review(self, severity: str, top_hypothesis: RootCauseHypothesis) -> bool:
        if severity not in self.auto_severities:
            return True
        if top_hypothesis.confidence < self.auto_confidence_threshold:
            return True
        return False

    def decision(
        self,
        severity: str,
        top_hypothesis: RootCauseHypothesis,
        approver: str = "",
    ) -> dict:
        needs = self.needs_human_review(severity, top_hypothesis)
        if needs:
            if not approver:
                return {"approved": False, "reason": "Awaiting human review"}
            return {"approved": True, "reason": f"Approved by {approver}", "human_approval": True}
        return {"approved": True, "reason": "Auto-approved by risk policy", "human_approval": False}
