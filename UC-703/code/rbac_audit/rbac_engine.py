"""Motor RBAC con mínimo privilegio, segregación de funciones y políticas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rbac_audit.models_rbac import AccessDecision, Action, Permission, Principal, Resource, Role


class RBACEngine:
    """
    Evalúa permisos basados en roles y políticas condicionales.
    Implementa el principio de mínimo privilegio y bloquea acciones críticas
    sin aprobación explícita.
    """

    def __init__(self) -> None:
        self._principals: Dict[str, Principal] = {}
        self._roles: Dict[str, Role] = {}
        self._permissions: Dict[str, Permission] = {}
        self._resources: Dict[str, Resource] = {}
        self._sod_rules: List[List[str]] = []  # pairs of roles that cannot coexist

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def create_role(self, role_id: str, name: str, description: str = "", permission_ids: Optional[List[str]] = None) -> Role:
        role = Role(role_id=role_id, name=name, description=description, permissions=permission_ids or [])
        self._roles[role_id] = role
        return role

    def grant_permission(
        self,
        permission_id: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Permission:
        perm = Permission(
            permission_id=permission_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            conditions=conditions or {},
        )
        self._permissions[permission_id] = perm
        return perm

    def create_principal(self, principal_id: str, name: str, principal_type: str, role_ids: Optional[List[str]] = None) -> Principal:
        principal = Principal(principal_id=principal_id, name=name, principal_type=principal_type, roles=role_ids or [])
        self._principals[principal_id] = principal
        return principal

    def register_resource(
        self,
        resource_id: str,
        resource_type: str,
        owner: str = "",
        version: str = "",
        sensitivity: str = "",
        environment: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Resource:
        resource = Resource(
            resource_id=resource_id,
            resource_type=resource_type,
            owner=owner,
            version=version,
            sensitivity=sensitivity,
            environment=environment,
            metadata=metadata or {},
        )
        self._resources[resource_id] = resource
        return resource

    def add_sod_rule(self, conflicting_roles: List[str]) -> None:
        self._sod_rules.append(conflicting_roles)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def check_access(
        self,
        principal_id: str,
        action: str,
        resource_id: str,
        resource_type: str,
        context: Optional[Dict[str, Any]] = None,
        approved: bool = False,
    ) -> AccessDecision:
        context = context or {}
        principal = self._principals.get(principal_id)
        if not principal:
            return AccessDecision(principal_id=principal_id, action=action, resource_id=resource_id, resource_type=resource_type, allowed=False, reason="Principal not found")

        # Segregation of Duties check
        if self._violates_sod(principal.roles):
            return AccessDecision(principal_id=principal_id, action=action, resource_id=resource_id, resource_type=resource_type, allowed=False, reason="Segregation of duties violation", roles=principal.roles)

        # Critical operations require explicit approval unless marked approved
        if self.is_critical_action(action) and not approved:
            return AccessDecision(
                principal_id=principal_id, action=action, resource_id=resource_id, resource_type=resource_type,
                allowed=False, reason="Critical operation requires approval", roles=principal.roles,
            )

        # Collect permissions from assigned roles
        allowed = False
        reasons: List[str] = []
        for role_id in principal.roles:
            role = self._roles.get(role_id)
            if not role:
                continue
            for perm_id in role.permissions:
                perm = self._permissions.get(perm_id)
                if not perm:
                    continue
                if self._permission_matches(perm, action, resource_type, resource_id, context):
                    allowed = True
                    reasons.append(f"Granted by {role_id} via {perm_id}")

        if allowed:
            return AccessDecision(principal_id=principal_id, action=action, resource_id=resource_id, resource_type=resource_type, allowed=True, reason="; ".join(reasons), roles=principal.roles)
        return AccessDecision(principal_id=principal_id, action=action, resource_id=resource_id, resource_type=resource_type, allowed=False, reason="No matching permission", roles=principal.roles)

    def _permission_matches(self, perm: Permission, action: str, resource_type: str, resource_id: str, context: Dict[str, Any]) -> bool:
        if perm.action != action and perm.action != Action.ADMIN.value:
            return False
        if perm.resource_type != resource_type and perm.resource_type != "*":
            return False
        if perm.resource_id and perm.resource_id != resource_id:
            return False
        # Simple condition checks
        for key, expected in perm.conditions.items():
            if key == "environment" and context.get("environment") != expected:
                return False
            if key == "sensitivity" and self._resources.get(resource_id, Resource()).sensitivity != expected:
                return False
        return True

    def _violates_sod(self, roles: List[str]) -> bool:
        role_set = set(roles)
        for conflict in self._sod_rules:
            if len(set(conflict) & role_set) > 1:
                return True
        return False

    def is_critical_action(self, action: str) -> bool:
        return action in {Action.DEPLOY.value, Action.DELETE.value, Action.ADMIN.value, Action.APPROVE.value}

    def list_principals(self) -> List[Principal]:
        return list(self._principals.values())

    def list_roles(self) -> List[Role]:
        return list(self._roles.values())

    def list_resources(self) -> List[Resource]:
        return list(self._resources.values())
