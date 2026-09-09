"""Controles de acceso RBAC/ABAC, identidades OIDC, CMK y segregación por ambiente."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from compliance_as_code.models_compliance import AccessDecision


class AccessControlEnforcer:
    """
    Control de acceso basado en roles (RBAC), atributos (ABAC) y entornos,
    con identidades OIDC simuladas y CMK.
    """

    def __init__(self) -> None:
        self._role_permissions: Dict[str, List[Dict[str, Any]]] = {}
        self._environment_segregation: Dict[str, List[str]] = {}
        self._cmk_registry: Dict[str, str] = {}

    def grant_role(
        self,
        role: str,
        resource: str,
        action: str,
        environments: Optional[List[str]] = None,
    ) -> None:
        self._role_permissions.setdefault(role, []).append({
            "resource": resource,
            "action": action,
            "environments": environments or ["*"],
        })

    def set_environment_roles(self, environment: str, allowed_roles: List[str]) -> None:
        self._environment_segregation[environment] = list(allowed_roles)

    def register_cmk(self, tenant: str, cmk_key_id: str) -> None:
        self._cmk_registry[tenant] = cmk_key_id

    def evaluate(
        self,
        requester_id: str,
        roles: List[str],
        resource: str,
        action: str,
        environment: str,
        oidc_claims: Optional[Dict[str, Any]] = None,
        tenant: str = "",
    ) -> AccessDecision:
        oidc = oidc_claims or {}
        # Environment segregation
        allowed_roles = self._environment_segregation.get(environment)
        if allowed_roles is not None:
            if not any(r in allowed_roles for r in roles):
                return AccessDecision(
                    requester_id=requester_id,
                    resource=resource,
                    action=action,
                    environment=environment,
                    decision="deny",
                    reason=f"roles {roles} not allowed in environment {environment}",
                    oidc_claims=oidc,
                )

        # RBAC/ABAC check
        for role in roles:
            for perm in self._role_permissions.get(role, []):
                resource_match = perm["resource"] in (resource, "*")
                action_match = perm["action"] in (action, "*")
                env_match = "*" in perm["environments"] or environment in perm["environments"]
                if resource_match and action_match and env_match:
                    cmk = self._cmk_registry.get(tenant, "")
                    return AccessDecision(
                        requester_id=requester_id,
                        resource=resource,
                        action=action,
                        environment=environment,
                        decision="allow",
                        reason="RBAC/ABAC allow",
                        oidc_claims=oidc,
                        cmk_key_id=cmk,
                    )

        return AccessDecision(
            requester_id=requester_id,
            resource=resource,
            action=action,
            environment=environment,
            decision="deny",
            reason="no matching RBAC/ABAC permission",
            oidc_claims=oidc,
        )
