"""UC-317 — Access Manager: roles, permisos y trust scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Permission(str, Enum):
    LLM_CALL = "llm:call"
    TOOL_USE = "tool:use"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    STORAGE_READ = "storage:read"
    STORAGE_WRITE = "storage:write"
    AGENT_RUN = "agent:run"
    AGENT_SCHEDULE = "agent:schedule"


@dataclass
class Role:
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    max_risk: str = "medium"  # low, medium, high, critical
    trust: float = 1.0


class AccessManager:
    """Control de acceso basado en roles y trust score."""

    RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

    def __init__(self) -> None:
        self._roles: Dict[str, Role] = {
            "guest": Role("guest", {Permission.LLM_CALL, Permission.MEMORY_READ}, "low"),
            "user": Role("user", {Permission.LLM_CALL, Permission.TOOL_USE, Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.AGENT_RUN}, "medium"),
            "developer": Role("developer", {Permission.LLM_CALL, Permission.TOOL_USE, Permission.MEMORY_READ, Permission.MEMORY_WRITE, Permission.STORAGE_READ, Permission.STORAGE_WRITE, Permission.AGENT_RUN, Permission.AGENT_SCHEDULE}, "high"),
            "admin": Role("admin", set(Permission), "critical"),
        }

    def add_role(self, role: Role) -> None:
        self._roles[role.name] = role

    def has_permission(self, roles: List[str], permission: Permission) -> bool:
        return any(permission in self._roles[r].permissions for r in roles if r in self._roles)

    def allowed_risk(self, roles: List[str], risk: str) -> bool:
        role_max = max((self.RISK_ORDER.get(self._roles[r].max_risk, 0) for r in roles if r in self._roles), default=0)
        return self.RISK_ORDER.get(risk, 0) <= role_max

    def list_roles(self) -> List[Dict[str, Any]]:
        return [{"name": r.name, "permissions": [p.value for p in r.permissions], "max_risk": r.max_risk} for r in self._roles.values()]
