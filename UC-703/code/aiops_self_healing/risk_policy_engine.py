"""Clasificación de severidad y políticas de riesgo para remediación."""
from __future__ import annotations

from typing import Any, Dict, List

from aiops_self_healing.models_aiops import CorrelationGroup, RemediationPolicy, RemediationType


class SeverityClassifier:
    """Clasifica la severidad global del grupo basado en alertas correlacionadas."""

    @staticmethod
    def classify(group: CorrelationGroup) -> str:
        return group.severity or "medium"


class RiskPolicyEngine:
    """
    Decide qué remediaciones están preautorizadas y cuáles requieren aprobación
    humana basándose en la categoría y severidad del incidente.
    """

    HIGH_IMPACT = {
        RemediationType.ROLLBACK_MODEL,
        RemediationType.ROLLBACK_CONFIG,
        RemediationType.SANDBOX_ISOLATION,
        RemediationType.FALLBACK_PROVIDER,
    }

    def __init__(self) -> None:
        self._policies: List[RemediationPolicy] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            RemediationPolicy(
                action_type=RemediationType.AUTOSCALE.value,
                category="availability",
                severity="high",
                requires_approval=False,
                conditions={"max_per_hour": 3},
            ),
            RemediationPolicy(
                action_type=RemediationType.RATE_LIMIT.value,
                category="latency",
                severity="high",
                requires_approval=False,
            ),
            RemediationPolicy(
                action_type=RemediationType.CIRCUIT_BREAKER.value,
                category="security",
                severity="critical",
                requires_approval=False,
            ),
            RemediationPolicy(
                action_type=RemediationType.ROLLBACK_PROMPT.value,
                category="quality",
                severity="high",
                requires_approval=True,
            ),
            RemediationPolicy(
                action_type=RemediationType.HUMAN_ESCALATION.value,
                category="*",
                severity="critical",
                requires_approval=True,
            ),
        ]
        self._policies.extend(defaults)

    def register(self, policy: RemediationPolicy) -> None:
        self._policies.append(policy)

    def requires_approval(self, action_type: str, category: str, severity: str) -> bool:
        # Exact match first
        for p in self._policies:
            if p.action_type == action_type and (p.category == category or p.category == "*") and (p.severity == severity or p.severity == "*"):
                return p.requires_approval
        # High-impact actions require approval by default
        if action_type in {a.value for a in self.HIGH_IMPACT}:
            return True
        return False

    def is_allowed(self, action_type: str) -> bool:
        return any(p.action_type == action_type for p in self._policies) or action_type in {t.value for t in RemediationType}

    def list_policies(self) -> List[RemediationPolicy]:
        return list(self._policies)
