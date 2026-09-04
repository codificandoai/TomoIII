"""UC-315 — Safety Supervisor parametrizado por dominio.

Valida que una acción de skill cumpla la política del dominio, los permisos del
rol, precondiciones simbólicas y límites operativos antes de ejecutar efectos
externos.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from domain_policy import PolicyRegistry
from skill_contracts import SkillContract


class SafetySupervisor315:
    """Supervisor de seguridad con políticas por dominio."""

    def __init__(self, policy_registry: Optional[PolicyRegistry] = None) -> None:
        self.policies = policy_registry or PolicyRegistry()
        self._audit_log: List[Dict[str, Any]] = []
        self._failure_counts: Dict[str, int] = {}

    def check(
        self,
        skill: SkillContract,
        inputs: Dict[str, Any],
        user_roles: List[str],
        domain_state: Dict[str, Any],
        require_human_approval: bool = False,
    ) -> Dict[str, Any]:
        """Devuelve {"allowed": bool, "issues": [...], "requires_approval": bool}."""
        policy = self.policies.get(skill.domain)
        issues: List[str] = []

        # 1. Dominio y clase de acción permitida
        if not policy.allows_action_class(skill.action_class.value):
            issues.append(f"action_class '{skill.action_class.value}' no permitido en dominio '{skill.domain}'")

        # 2. Rol requerido
        if skill.required_roles and not any(r in user_roles for r in skill.required_roles):
            issues.append(f"rol requerido {skill.required_roles}; roles presentes: {user_roles}")

        # 3. Permisos
        missing_perms = [p for p in skill.permissions if p not in user_roles]
        if missing_perms:
            issues.append(f"permisos faltantes: {missing_perms}")

        # 4. Límites operativos
        if skill.estimated_cost > policy.max_cost_per_action:
            issues.append(f"coste estimado {skill.estimated_cost} excede límite {policy.max_cost_per_action}")
        if skill.estimated_latency_ms > policy.max_latency_ms:
            issues.append(f"latencia estimada {skill.estimated_latency_ms}ms excede límite {policy.max_latency_ms}ms")

        # 5. Precondiciones simbólicas (simplificadas)
        for pre in skill.preconditions:
            if not self._precondition_holds(pre, inputs, domain_state):
                issues.append(f"precondición no satisfecha: {pre}")

        # 6. Circuit breaker por skill
        if self._failure_counts.get(skill.name, 0) >= policy.circuit_breaker_threshold:
            issues.append(f"circuit breaker activado para {skill.name}")

        requires_approval = policy.requires_approval(skill.action_class.value, skill.name)
        if require_human_approval:
            requires_approval = True

        allowed = not issues
        decision = {
            "allowed": allowed,
            "issues": issues,
            "requires_approval": requires_approval,
            "domain": skill.domain,
            "skill": skill.name,
            "policy": policy.domain,
        }
        self._audit_log.append(decision)
        return decision

    @staticmethod
    def _precondition_holds(precondition: str, inputs: Dict[str, Any], domain_state: Dict[str, Any]) -> bool:
        if "autorizado" in precondition.lower() or "aprobada" in precondition.lower():
            return domain_state.get("risk_approved", False) or domain_state.get("user_consent", False)
        if "consentimiento" in precondition.lower():
            return domain_state.get("user_consent", False)
        if "disponibilidad" in precondition.lower():
            return domain_state.get("availability_confirmed", False)
        if "circuit breaker abierto" in precondition.lower():
            return domain_state.get("circuit_breaker_open", True)
        return True

    def record_failure(self, skill_name: str) -> None:
        self._failure_counts[skill_name] = self._failure_counts.get(skill_name, 0) + 1

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return self._audit_log
