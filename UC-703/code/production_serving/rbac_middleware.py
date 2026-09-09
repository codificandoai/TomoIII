"""Middleware RBAC para endpoints de serving de LLM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rbac_audit.rbac_engine import RBACEngine


class RBACMiddleware:
    """
    Valida tokens de autenticación y autoriza scopes/roles sobre endpoints de
    serving. Puede operar en modo simulado o con un RBACEngine externo.
    """

    def __init__(self, engine: Optional[RBACEngine] = None) -> None:
        self.engine = engine or RBACEngine()
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def register_token(
        self,
        token: str,
        principal_id: str,
        roles: List[str],
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        entry = {
            "principal_id": principal_id,
            "roles": roles,
            "scopes": scopes or [],
        }
        self._tokens[token] = entry
        return entry

    def authenticate(self, token: str) -> Optional[Dict[str, Any]]:
        return self._tokens.get(token)

    def authorize(
        self,
        token: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        identity = self.authenticate(token)
        if not identity:
            return {"allowed": False, "reason": "Invalid token", "roles": []}
        principal_id = identity["principal_id"]
        roles = identity["roles"]

        # Ensure principal exists in RBACEngine
        if principal_id not in self.engine._principals:
            self.engine.create_principal(principal_id, principal_id, "user", role_ids=roles)
        decision = self.engine.check_access(principal_id, action, resource_id, resource_type, context or {})
        return {"allowed": decision.allowed, "reason": decision.reason, "roles": roles}

    def rate_limit(self, token: str, limit: int = 100) -> bool:
        identity = self._tokens.get(token)
        if not identity:
            return False
        identity["calls"] = identity.get("calls", 0) + 1
        return identity["calls"] <= limit
