"""
UC-300 — Motor de políticas con deny-by-default.

Evalúa permisos basados en identidad, herramienta, acción, recurso,
entorno y scopes. Por defecto todo está denegado; solo se permite
lo declarado explícitamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class PolicyRule:
    """Regla de política individual."""
    identity: str = "*"          # agent_id o "*"
    tool: str = "*"              # action/tool
    resource: str = "*"          # e.g. SKU-001 o *
    environment: str = "*"       # e.g. prod, staging, default
    effect: str = "deny"         # allow | deny
    conditions: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity,
            "tool": self.tool,
            "resource": self.resource,
            "environment": self.environment,
            "effect": self.effect,
            "conditions": self.conditions,
            "description": self.description,
        }


class PolicyEngine:
    """Motor de políticas deny-by-default con scopes."""

    def __init__(self):
        self._rules: List[PolicyRule] = []
        self._scopes: Dict[str, List[str]] = {}
        self._environments: Set[str] = {"default"}

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def set_scope(self, agent_id: str, resources: List[str]) -> None:
        self._scopes[agent_id] = list(resources)

    def allow_environment(self, environment: str) -> None:
        self._environments.add(environment)

    def is_environment_allowed(self, environment: str) -> bool:
        return environment in self._environments

    def evaluate(
        self,
        agent_id: str,
        action: str,
        params: Dict[str, Any],
        environment: str,
    ) -> Dict[str, Any]:
        """
        Evalúa si la solicitud cumple las políticas.
        Devuelve {"allowed": bool, "reason": str}.
        """
        # Denegar si el entorno no está explícitamente permitido
        if not self.is_environment_allowed(environment):
            return {"allowed": False, "reason": f"environment '{environment}' not allowed"}

        resource = self._extract_resource(action, params)

        # Denegar por defecto si no hay regla explícita allow
        allowed = False
        matched_allow = False
        matched_deny = False

        for rule in self._rules:
            if not self._matches(rule, agent_id, action, resource, environment):
                continue
            if rule.effect == "deny":
                matched_deny = True
            elif rule.effect == "allow":
                matched_allow = True
                if not self._check_conditions(rule, params):
                    return {"allowed": False, "reason": "conditions not met for allow rule"}

        # Verificar scopes: si el recurso está definido, debe estar en el scope del agente
        if resource and agent_id in self._scopes:
            allowed_resources = set(self._scopes[agent_id])
            if resource not in allowed_resources and "*" not in allowed_resources:
                return {
                    "allowed": False,
                    "reason": f"resource '{resource}' outside agent '{agent_id}' scope",
                }

        if matched_deny:
            return {"allowed": False, "reason": "explicit deny rule matched"}
        if matched_allow:
            allowed = True
        else:
            return {"allowed": False, "reason": "deny-by-default: no matching allow rule"}

        return {"allowed": allowed, "reason": "policy allowed"}

    def _matches(
        self,
        rule: PolicyRule,
        agent_id: str,
        action: str,
        resource: Optional[str],
        environment: str,
    ) -> bool:
        if rule.identity != "*" and rule.identity != agent_id:
            return False
        if rule.tool != "*" and rule.tool != action:
            return False
        if rule.environment != "*" and rule.environment != environment:
            return False
        if rule.resource != "*" and rule.resource != resource:
            return False
        return True

    def _check_conditions(self, rule: PolicyRule, params: Dict[str, Any]) -> bool:
        """Evalúa condiciones simples definidas en la regla."""
        for key, expected in rule.conditions.items():
            actual = params.get(key)
            if callable(expected):
                if not expected(actual):
                    return False
            elif actual != expected:
                return False
        return True

    def _extract_resource(self, action: str, params: Dict[str, Any]) -> Optional[str]:
        if action in ("update_price", "delete_product"):
            return params.get("product_id")
        if action == "read_file":
            return params.get("path")
        return None

    def load_defaults(self) -> None:
        """Carga reglas por defecto de ejemplo."""
        self.allow_environment("default")
        self.allow_environment("prod")
        self.allow_environment("staging")

        # Agente europeo solo puede tocar SKUs de Europa
        self.set_scope("agent_pricing_eu", ["SKU-001", "SKU-002"])
        # Agente americano solo puede tocar SKUs de EE.UU.
        self.set_scope("agent_pricing_us", ["SKU-100", "SKU-101"])

        # Reglas allow explícitas
        self.add_rule(PolicyRule(
            identity="agent_pricing_eu",
            tool="update_price",
            resource="*",
            environment="default",
            effect="allow",
            description="EU pricing agent can update scoped SKUs",
        ))
        self.add_rule(PolicyRule(
            identity="agent_pricing_us",
            tool="update_price",
            resource="*",
            environment="default",
            effect="allow",
            description="US pricing agent can update scoped SKUs",
        ))
        # read_file de simulación permitido a todos en default
        self.add_rule(PolicyRule(
            identity="*",
            tool="read_file",
            resource="*",
            environment="default",
            effect="allow",
            description="Read simulated files in default environment",
        ))

        # Pagos altos: se gestionan vía HITL, pero a nivel de policy permitimos
        # la acción send_payment sólo si pasa validación; el HITL decide ejecutar.
        self.add_rule(PolicyRule(
            identity="*",
            tool="send_payment",
            resource="*",
            environment="default",
            effect="allow",
            conditions={"currency": "USD"},
            description="Payments allowed only in USD by policy",
        ))

        # delete_product es destructivo: se permite sólo a roles con scope
        self.add_rule(PolicyRule(
            identity="*",
            tool="delete_product",
            resource="*",
            environment="default",
            effect="allow",
            description="Delete product requires HITL approval downstream",
        ))

    def get_summary(self) -> Dict[str, Any]:
        return {
            "rules": [r.to_dict() for r in self._rules],
            "scopes": self._scopes,
            "environments": sorted(self._environments),
        }
