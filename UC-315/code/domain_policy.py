"""UC-315 — Políticas de autorización y seguridad por dominio.

Cada dominio define controles deterministas que el Safety Supervisor aplica antes
de permitir efectos externos. Los dominios no comparten políticas ni permisos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class DomainPolicy:
    domain: str
    max_cost_per_action: float = 100.0
    max_latency_ms: float = 1000.0
    allowed_action_classes: List[str] = field(default_factory=list)
    required_approval_for: List[str] = field(default_factory=list)
    circuit_breaker_threshold: int = 3
    rate_limit_per_minute: int = 60
    segregation_rules: List[str] = field(default_factory=list)

    def allows_action_class(self, action_class: str) -> bool:
        if not self.allowed_action_classes:
            return True
        return action_class in self.allowed_action_classes

    def requires_approval(self, action_class: str, skill_name: str) -> bool:
        return action_class in self.required_approval_for or skill_name in self.required_approval_for


TRADING_POLICY = DomainPolicy(
    domain="trading",
    max_cost_per_action=10.0,
    max_latency_ms=50.0,
    allowed_action_classes=["read", "predict", "analyze", "execute"],
    required_approval_for=["execute", "MarketExecutionSkill"],
    circuit_breaker_threshold=2,
    rate_limit_per_minute=120,
    segregation_rules=[
        "signal_cannot_execute",
        "risk_must_validate_before_execute",
        "execution_requires_risk_approval",
    ],
)

RESERVATIONS_POLICY = DomainPolicy(
    domain="reservations",
    max_cost_per_action=5.0,
    max_latency_ms=2000.0,
    allowed_action_classes=["read", "analyze", "transact", "delete"],
    required_approval_for=["transact", "delete", "PaymentSkill", "ChangeCancelSkill"],
    circuit_breaker_threshold=5,
    rate_limit_per_minute=30,
    segregation_rules=[
        "payment_requires_identity_and_availability",
        "cancellation_requires_policy_check",
        "notification_does_not_modify_reservation",
    ],
)


class PolicyRegistry:
    def __init__(self) -> None:
        self._policies: Dict[str, DomainPolicy] = {
            "trading": TRADING_POLICY,
            "reservations": RESERVATIONS_POLICY,
        }

    def get(self, domain: str) -> DomainPolicy:
        return self._policies.get(domain, DomainPolicy(domain=domain))

    def list(self) -> List[str]:
        return list(self._policies.keys())
