"""UC-324 — Integración nativa con Microsoft Agent Governance Toolkit.

Este módulo envuelve componentes reales de AGT (`agent_os`, `agent_runtime`,
`agent_sre`) de forma opcional. Si no están instalados, el sistema sigue
funcionando con las heurísticas locales del adapter.
"""
from __future__ import annotations

import asyncio
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore", category=DeprecationWarning)

AGT_AVAILABLE = False
AGT_ERROR: Optional[str] = None

try:
    from agent_os import ExecutionContext, StatelessKernel
    from agent_runtime import ExecutionRing, RingEnforcer

    AGT_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    AGT_ERROR = str(exc)


@dataclass
class AGTEvaluationResult:
    allowed: bool = True
    issues: List[str] = None  # type: ignore[assignment]
    warnings: List[str] = None  # type: ignore[assignment]
    details: Dict[str, Any] = None  # type: ignore[assignment]
    native: bool = False

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.warnings is None:
            self.warnings = []
        if self.details is None:
            self.details = {}


# Políticas declarativas por dominio inspiradas en domain_policy.py.
TRADING_POLICY = {
    "trading_read": {"blocked_actions": ["trading.MarketExecutionSkill"]},
    "trading_execute": {"blocked_actions": []},
}

RESERVATIONS_POLICY = {
    "reservations_read": {
        "blocked_actions": ["reservations.PaymentSkill", "reservations.ChangeCancelSkill"]
    },
    "reservations_pay": {"blocked_actions": []},
    "reservations_modify": {"blocked_actions": []},
}


def _default_policies() -> Dict[str, Any]:
    return {**TRADING_POLICY, **RESERVATIONS_POLICY}


class AGTNativeGovernance:
    """Wrapper sincrónico alrededor de AGT StatelessKernel + anillos de privilegio."""

    def __init__(self, policies: Optional[Dict[str, Any]] = None) -> None:
        if not AGT_AVAILABLE:
            raise ImportError(f"Microsoft AGT no está disponible: {AGT_ERROR}")
        self._kernel = StatelessKernel(policies=policies or _default_policies())
        self._ring_enforcer = RingEnforcer()

    @staticmethod
    def _action_name(skill: Any) -> str:
        domain = getattr(skill, "domain", getattr(skill, "get", lambda k: "generic")) \
            if isinstance(skill, dict) else getattr(skill, "domain", "generic")
        if isinstance(skill, dict):
            domain = skill.get("domain", "generic")
            name = skill.get("name", "unknown")
        else:
            domain = getattr(skill, "domain", "generic")
            name = getattr(skill, "name", "unknown")
        return f"{domain}.{name}"

    @staticmethod
    def _choose_policies(skill: Any, roles: List[str]) -> List[str]:
        if isinstance(skill, dict):
            domain = skill.get("domain", "generic")
            name = skill.get("name", "")
            action_class = skill.get("action_class")
        else:
            domain = getattr(skill, "domain", "generic")
            name = getattr(skill, "name", "")
            action_class = getattr(skill, "action_class", None)

        if domain == "trading":
            if action_class and action_class == "execute" or name == "MarketExecutionSkill":
                if "market.order.send" in roles or "trader" in roles:
                    return ["trading_execute"]
                return ["trading_read"]
            return ["trading_read"]
        if domain == "reservations":
            if name == "PaymentSkill" or (action_class and action_class == "transact"):
                if "payment.charge" in roles or "payment_processor" in roles:
                    return ["reservations_pay"]
                return ["reservations_read"]
            if action_class and action_class == "delete":
                if "reservation.modify" in roles or "admin" in roles:
                    return ["reservations_modify"]
                return ["reservations_read"]
            return ["reservations_read"]
        risk = skill.get("risk_level", "low") if isinstance(skill, dict) else getattr(skill, "risk_level", "low")
        if risk in ("high", "critical"):
            return ["strict"]
        return ["read_only"]

    def _ring_for_agent(self, roles: List[str]) -> "ExecutionRing":
        privileged = {"trader", "payment_processor", "admin"}
        if any(r in privileged for r in roles):
            return ExecutionRing.RING_2_STANDARD
        return ExecutionRing.RING_3_SANDBOX

    def _ring_for_action(self, skill: Any) -> "ExecutionRing":
        if isinstance(skill, dict):
            action_class = skill.get("action_class")
            risk = skill.get("risk_level", "low")
        else:
            action_class = getattr(skill, "action_class", None)
            risk = getattr(skill, "risk_level", "low")
        if action_class and action_class in ("execute", "transact", "delete"):
            return ExecutionRing.RING_2_STANDARD
        if risk in ("high", "critical"):
            return ExecutionRing.RING_2_STANDARD
        return ExecutionRing.RING_3_SANDBOX

    def evaluate(
        self,
        skill: Any,
        inputs: Dict[str, Any],
        roles: List[str],
        domain_state: Dict[str, Any],
        agent_id: str = "orchestrator_001",
    ) -> AGTEvaluationResult:
        result = AGTEvaluationResult(native=True)

        # 1. Anillos de privilegio (Agent Runtime)
        agent_ring = self._ring_for_agent(roles)
        action_ring = self._ring_for_action(skill)

        class _Action:
            action_id = self._action_name(skill)
            required_ring = action_ring
            risk_weight = 0.8 if action_ring == ExecutionRing.RING_2_STANDARD else 0.2
            reversibility = "undo" if action_ring == ExecutionRing.RING_3_SANDBOX else "none"

        ring_check = self._ring_enforcer.check(
            agent_ring=agent_ring,
            action=_Action(),
            eff_score=0.5,
            has_consensus=False,
        )
        if not ring_check.allowed:
            result.allowed = False
            result.issues.append(f"AGT RingEnforcer: {ring_check.reason}")
            return result
        result.details["agent_ring"] = agent_ring.name
        result.details["required_ring"] = action_ring.name

        # 2. Políticas declarativas (StatelessKernel)
        action_name = self._action_name(skill)
        params = {**inputs, **domain_state}
        policies = self._choose_policies(skill, roles)
        context = ExecutionContext(
            agent_id=agent_id,
            policies=policies,
            metadata={"roles": roles, "domain_state_keys": list(domain_state.keys())},
        )
        try:
            coro = self._kernel.execute(action_name, params, context)
            agt_result = asyncio.run(coro)
        except Exception as exc:
            result.allowed = False
            result.issues.append(f"AGT StatelessKernel error: {exc}")
            return result

        if not agt_result.success:
            result.allowed = False
            result.issues.append(f"AGT policy: {agt_result.error}")
        else:
            result.details["agt_request_id"] = agt_result.metadata.get("request_id")

        return result
