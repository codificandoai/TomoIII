"""UC-324 — Integración funcional de SafeAuto (D) post-action rule verification.

El repositorio `AI-secure/SafeAuto` no contiene un paquete Python instalable
(no tiene `setup.py` ni `pyproject.toml`). Por eso UC-324 implementa un motor
nativo de verificación de reglas post-acción inspirado en SafeAuto: usa reglas
declarativas con operadores lógicos para validar que el output de una skill no
violet restricciones estrictas.

Características:
- Reglas por dominio y/o skill.
- Operadores lógicos: `and`, `or`, `not`, `exists`, `contains`.
- Referencias a `output`, `input`, `skill`, `domain_state`.
- Severidad `critical` bloquea; `warning` solo reporta.
- Explicaciones por violación para auditoría.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_RULES: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------
    # Reservations
    # ------------------------------------------------------------------
    {
        "name": "payment_requires_confirmation_or_transaction_id",
        "domain": "reservations",
        "skills": ["PaymentSkill"],
        "message": "PaymentSkill output must contain a confirmation_id or transaction_id",
        "severity": "critical",
        "condition": {
            "or": [
                {"exists": "output.confirmation_id"},
                {"exists": "output.transaction_id"},
            ]
        },
    },
    {
        "name": "payment_requires_authorized_status",
        "domain": "reservations",
        "skills": ["PaymentSkill"],
        "message": "PaymentSkill output status must be AUTHORIZED",
        "severity": "critical",
        "condition": {"output.status": "AUTHORIZED"},
    },
    {
        "name": "cancellation_requires_refund_or_success",
        "domain": "reservations",
        "skills": ["ChangeCancelSkill"],
        "message": "ChangeCancelSkill must either succeed or provide a refund_id",
        "severity": "warning",
        "condition": {
            "or": [
                {"output.success": True},
                {"exists": "output.refund_id"},
            ]
        },
    },
    {
        "name": "no_mass_deletion_in_reservations",
        "domain": "reservations",
        "skills": ["ChangeCancelSkill"],
        "message": "Mass deletion of reservations is not allowed",
        "severity": "critical",
        "condition": {
            "not": {
                "and": [
                    {"exists": "output.deleted_count"},
                    {"output.deleted_count": {"gt": 1}},
                ]
            }
        },
    },
    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    {
        "name": "market_execution_requires_order_id",
        "domain": "trading",
        "skills": ["MarketExecutionSkill"],
        "message": "MarketExecutionSkill output must contain an order_id",
        "severity": "critical",
        "condition": {"exists": "output.order_id"},
    },
    {
        "name": "market_execution_not_rejected",
        "domain": "trading",
        "skills": ["MarketExecutionSkill"],
        "message": "MarketExecutionSkill output must not be REJECTED or ERROR",
        "severity": "critical",
        "condition": {
            "not": {
                "or": [
                    {"output.status": "REJECTED"},
                    {"output.status": "ERROR"},
                ]
            }
        },
    },
    {
        "name": "market_execution_amount_within_risk_limit",
        "domain": "trading",
        "skills": ["MarketExecutionSkill"],
        "message": "MarketExecutionSkill amount exceeds risk limit",
        "severity": "critical",
        "condition": {
            "not": {
                "and": [
                    {"exists": "output.amount"},
                    {"exists": "domain_state.risk_limit"},
                    {"output.amount": {"gt": "domain_state.risk_limit"}},
                ]
            }
        },
    },
    # ------------------------------------------------------------------
    # General / cross-domain
    # ------------------------------------------------------------------
    {
        "name": "critical_action_must_not_fail",
        "message": "Critical action reported failure",
        "severity": "critical",
        "condition": {
            "not": {
                "and": [
                    {"skill.action_class": ["execute", "transact", "delete"]},
                    {"output.success": False},
                ]
            }
        },
    },
    {
        "name": "output_must_not_contain_error_keywords",
        "message": "Output contains error/rejected/unauthorized keywords",
        "severity": "warning",
        "condition": {
            "not": {
                "contains": {
                    "path": "output",
                    "value": "error",
                }
            }
        },
    },
    {
        "name": "output_must_not_contain_dangerous_commands",
        "message": "Output contains shell/SQL-like dangerous commands",
        "severity": "critical",
        "condition": {
            "not": {
                "contains": {
                    "path": "output",
                    "value": "rm -rf",
                }
            }
        },
    },
]


@dataclass
class PostActionVerificationResult:
    allowed: bool = True
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "violations": self.violations,
            "warnings": self.warnings,
            "details": self.details,
        }


class PostActionRuleEngine:
    """Motor de reglas post-acción tipo SafeAuto."""

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rules = rules if rules is not None else list(DEFAULT_RULES)

    @staticmethod
    def _get_value(path: str, skill: Dict[str, Any], inputs: Dict[str, Any],
                   output: Dict[str, Any], domain_state: Dict[str, Any]) -> Any:
        """Resuelve una referencia del tipo 'output.confirmation_id'."""
        parts = path.split(".")
        root = parts[0]
        remainder = ".".join(parts[1:]) if len(parts) > 1 else ""

        if root == "skill":
            container = skill
        elif root == "input":
            container = inputs
        elif root == "output":
            container = output
        elif root == "domain_state":
            container = domain_state
        else:
            return None

        value: Any = container
        for part in parts[1:]:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _evaluate_condition(
        self,
        condition: Any,
        skill: Dict[str, Any],
        inputs: Dict[str, Any],
        output: Dict[str, Any],
        domain_state: Dict[str, Any],
    ) -> bool:
        """Evalúa una condición lógica."""
        if not isinstance(condition, dict):
            return bool(condition)

        # Operadores lógicos
        if "and" in condition:
            return all(
                self._evaluate_condition(c, skill, inputs, output, domain_state)
                for c in condition["and"]
            )
        if "or" in condition:
            return any(
                self._evaluate_condition(c, skill, inputs, output, domain_state)
                for c in condition["or"]
            )
        if "not" in condition:
            return not self._evaluate_condition(
                condition["not"], skill, inputs, output, domain_state
            )

        # Operador exists
        if "exists" in condition:
            val = self._get_value(condition["exists"], skill, inputs, output, domain_state)
            return val is not None

        # Operador contains (subcadena en un valor o recursivamente en dict)
        if "contains" in condition:
            spec = condition["contains"]
            path = spec.get("path", "output")
            needle = spec.get("value", "")
            haystack = self._get_value(path, skill, inputs, output, domain_state)
            if haystack is None:
                return False
            text = json.dumps(haystack, ensure_ascii=False).lower()
            return needle.lower() in text

        # Comparaciones de referencias
        for key, expected in condition.items():
            actual = self._get_value(key, skill, inputs, output, domain_state)

            if isinstance(expected, dict):
                # Comparadores >, <, >=, <=, ==, !=
                for op, ref_val in expected.items():
                    if op == "gt":
                        if isinstance(ref_val, str):
                            ref_val = self._get_value(
                                ref_val, skill, inputs, output, domain_state
                            )
                        if actual is None or ref_val is None:
                            return False
                        try:
                            if not (float(actual) > float(ref_val)):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "lt":
                        if isinstance(ref_val, str):
                            ref_val = self._get_value(
                                ref_val, skill, inputs, output, domain_state
                            )
                        if actual is None or ref_val is None:
                            return False
                        try:
                            if not (float(actual) < float(ref_val)):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "gte":
                        if actual is None:
                            return False
                        try:
                            if not (float(actual) >= float(ref_val)):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "lte":
                        if actual is None:
                            return False
                        try:
                            if not (float(actual) <= float(ref_val)):
                                return False
                        except (TypeError, ValueError):
                            return False
                    elif op == "eq":
                        if actual != ref_val:
                            return False
                    elif op == "neq":
                        if actual == ref_val:
                            return False
            elif isinstance(expected, list):
                if actual not in expected:
                    return False
            else:
                if actual != expected:
                    return False

        return True

    def evaluate(
        self,
        skill: Dict[str, Any],
        inputs: Dict[str, Any],
        output: Dict[str, Any],
        domain_state: Optional[Dict[str, Any]] = None,
    ) -> PostActionVerificationResult:
        """Evalúa todas las reglas aplicables contra skill, input y output."""
        domain_state = domain_state or {}

        # Normalizar wrapper {"success": bool, "output": {...}} para que las
        # reglas post-acción puedan acceder tanto a output.status como a success.
        if isinstance(output, dict) and isinstance(output.get("output"), dict):
            inner = output["output"]
            output = {
                **inner,
                "success": output.get("success"),
                "output": inner,
            }

        result = PostActionVerificationResult()
        matched = 0

        for rule in self.rules:
            # Filtrar por dominio y skill
            rule_domain = rule.get("domain")
            rule_skills = rule.get("skills")
            if rule_domain and skill.get("domain") != rule_domain:
                continue
            if rule_skills and skill.get("name") not in rule_skills:
                continue
            matched += 1

            condition = rule.get("condition", True)
            if not self._evaluate_condition(condition, skill, inputs, output, domain_state):
                entry = {
                    "rule": rule["name"],
                    "message": rule.get("message", "Rule violated"),
                    "severity": rule.get("severity", "warning"),
                }
                if rule.get("severity") == "critical":
                    result.allowed = False
                    result.violations.append(entry)
                else:
                    result.warnings.append(entry)

        result.details["rules_evaluated"] = len(self.rules)
        result.details["rules_matched"] = matched
        result.details["source"] = "SafeAuto-style rule engine"
        return result


# Helper de alto nivel


def verify_post_action(
    skill: Dict[str, Any],
    inputs: Dict[str, Any],
    output: Dict[str, Any],
    domain_state: Optional[Dict[str, Any]] = None,
    rules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Verifica un output contra el motor de reglas post-acción."""
    engine = PostActionRuleEngine(rules=rules)
    return engine.evaluate(skill, inputs, output, domain_state).to_dict()
