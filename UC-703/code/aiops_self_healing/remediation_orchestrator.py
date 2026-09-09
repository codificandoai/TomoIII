"""Orquesta acciones de remediación preautorizadas, idempotentes y reversibles."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from aiops_self_healing.models_aiops import (
    CorrelationGroup,
    RemediationAction,
    RemediationType,
)
from aiops_self_healing.risk_policy_engine import RiskPolicyEngine


class RemediationOrchestrator:
    """
    Ejecuta acciones de remediación deterministas simulando autoscaling,
    rate limiting, circuit breaker, fallback, rollback, sandbox y health tests.
    Las acciones de alto impacto requieren aprobación previa en la política.
    """

    def __init__(self, policy_engine: Optional[RiskPolicyEngine] = None) -> None:
        self.policy_engine = policy_engine or RiskPolicyEngine()
        self._actions: List[RemediationAction] = []
        self._last_execution: Dict[str, float] = {}

    def execute(
        self,
        group: CorrelationGroup,
        action_type: RemediationType,
        target: str,
        params: Optional[Dict[str, Any]] = None,
        approver: str = "",
    ) -> Optional[RemediationAction]:
        if action_type.value not in {t.value for t in RemediationType}:
            return None

        requires = self.policy_engine.requires_approval(
            action_type.value, group.category, group.severity
        )
        if requires and not approver:
            action = RemediationAction(
                group_id=group.group_id,
                action_type=action_type.value,
                target=target,
                params=params or {},
                status="pending_approval",
                requires_approval=True,
            )
            self._actions.append(action)
            return action

        action = RemediationAction(
            group_id=group.group_id,
            action_type=action_type.value,
            target=target,
            params=params or {},
            status="succeeded",
            result=self._simulate_effect(action_type, target, params or {}),
            approved_by=approver,
            requires_approval=requires,
        )
        self._actions.append(action)
        self._last_execution[f"{action_type.value}:{target}"] = time.time()
        return action

    def _simulate_effect(
        self,
        action_type: RemediationType,
        target: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        effects = {
            RemediationType.AUTOSCALE: {"replicas": params.get("replicas", 2), "target": target},
            RemediationType.RATE_LIMIT: {"rate": params.get("rate", 100), "target": target},
            RemediationType.CIRCUIT_BREAKER: {"open": True, "target": target},
            RemediationType.FALLBACK_MODEL: {"model": params.get("model", "stable-model"), "target": target},
            RemediationType.FALLBACK_PROVIDER: {"provider": params.get("provider", "provider-b"), "target": target},
            RemediationType.ROLLBACK_PROMPT: {"version": params.get("version", "v-previous"), "target": target},
            RemediationType.ROLLBACK_MODEL: {"version": params.get("version", "v-previous"), "target": target},
            RemediationType.ROLLBACK_CONFIG: {"config": params.get("config", {}), "target": target},
            RemediationType.SANDBOX_ISOLATION: {"isolated": True, "target": target},
            RemediationType.HEALTH_TEST: {"passed": True, "target": target},
            RemediationType.HUMAN_ESCALATION: {"escalated": True, "target": target},
        }
        return effects.get(action_type, {"executed": True, "target": target})

    def rollback(self, action_id: str) -> Optional[RemediationAction]:
        for action in self._actions:
            if action.action_id == action_id:
                action.status = "rolled_back"
                action.result["rolled_back"] = True
                return action
        return None

    def list_actions(self, group_id: str = "") -> List[RemediationAction]:
        if not group_id:
            return list(self._actions)
        return [a for a in self._actions if a.group_id == group_id]
