"""Capa de seguridad A2A para UC-268.

Implementa:
- Autenticación con OAuth2 Bearer tokens (JWT) y API keys.
- Autorización basada en roles/scopes por skill.
- Verificación de TLS/HTTPS en entornos de producción.
- Decoradores Flask para proteger endpoints A2A.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from config import SecurityConfig, get_config


try:
    import jwt
    _JWT_AVAILABLE = True
except Exception:  # pragma: no cover
    _JWT_AVAILABLE = False


@dataclass(frozen=True)
class SecurityContext:
    """Identidad y permisos de un cliente autenticado."""

    authenticated: bool
    identity: str = "anonymous"
    scopes: tuple[str, ...] = ()
    scheme: str = "none"  # bearer | apiKey | none

    def has_scope(self, scope: str) -> bool:
        # Un scope "admin" concede todos los permisos
        if "admin" in self.scopes:
            return True
        return scope in self.scopes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authenticated": self.authenticated,
            "identity": self.identity,
            "scopes": list(self.scopes),
            "scheme": self.scheme,
        }


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class SecurityManager:
    """Gestiona autenticación y autorización de peticiones A2A."""

    def __init__(self, config: Optional[SecurityConfig] = None) -> None:
        self.config = config or get_config().security

    def authenticate_request(
        self, headers: Dict[str, str], required: bool = True
    ) -> SecurityContext:
        """Extrae y valida credenciales desde headers HTTP."""
        normalized = {k.lower(): v for k, v in headers.items()}
        auth_header = normalized.get("authorization", "")

        # OAuth2 Bearer token
        match = re.match(r"^[Bb]earer\s+(.+)$", auth_header)
        if match:
            token = match.group(1).strip()
            return self._validate_bearer(token)

        # API key
        api_key = normalized.get("x-api-key", "")
        if api_key:
            return self._validate_api_key(api_key)

        if required:
            raise AuthenticationError("Missing or unsupported credentials")
        return SecurityContext(authenticated=False)

    def _validate_bearer(self, token: str) -> SecurityContext:
        if not _JWT_AVAILABLE:
            raise AuthenticationError("JWT support not available")
        try:
            payload = jwt.decode(
                token, self.config.jwt_secret, algorithms=[self.config.jwt_algorithm]
            )
        except Exception as exc:
            raise AuthenticationError(f"Invalid token: {exc}") from exc
        return SecurityContext(
            authenticated=True,
            identity=payload.get("sub", "unknown"),
            scopes=tuple(payload.get("scopes", [])),
            scheme="bearer",
        )

    def _validate_api_key(self, api_key: str) -> SecurityContext:
        if api_key not in self.config.api_keys:
            raise AuthenticationError("Invalid API key")
        return SecurityContext(
            authenticated=True,
            identity=f"apikey:{api_key[:4]}***",
            scopes=("a2a:read", "a2a:write"),
            scheme="apiKey",
        )

    def authorize_skill(
        self, ctx: SecurityContext, skill_scopes: List[str]
    ) -> None:
        """Verifica que el contexto tenga al menos uno de los scopes requeridos."""
        if not ctx.authenticated:
            raise AuthorizationError("Authentication required")
        if not skill_scopes:
            return
        if any(ctx.has_scope(s) for s in skill_scopes):
            return
        raise AuthorizationError(
            f"Insufficient scope. Required one of: {skill_scopes}"
        )

    def generate_token(
        self,
        identity: str,
        scopes: List[str],
        ttl_minutes: Optional[int] = None,
    ) -> str:
        if not _JWT_AVAILABLE:
            raise RuntimeError("JWT support not available")
        ttl = ttl_minutes or self.config.token_ttl_minutes
        now = datetime.now(timezone.utc)
        payload = {
            "sub": identity,
            "scopes": list(scopes),
            "iat": now,
            "exp": now + timedelta(minutes=ttl),
        }
        return jwt.encode(
            payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm
        )

    def check_transport_security(self, url: str) -> None:
        """Verifica que la URL de destino use HTTPS si se exige TLS."""
        if not self.config.require_tls:
            return
        if not url.startswith("https://"):
            raise AuthenticationError(
                f"Insecure transport: {url}. TLS/HTTPS is required."
            )


def require_auth(scopes: Optional[List[str]] = None) -> Callable:
    """Decorador Flask para proteger endpoints A2A."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request

            manager = SecurityManager()
            try:
                ctx = manager.authenticate_request(dict(request.headers))
            except AuthenticationError as exc:
                return _error_response(str(exc), 401)

            required = scopes or []
            try:
                manager.authorize_skill(ctx, required)
            except AuthorizationError as exc:
                return _error_response(str(exc), 403)

            # Inyecta el contexto en request para uso posterior
            request.security_context = ctx  # type: ignore
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _error_response(message: str, status: int) -> tuple:
    from flask import jsonify

    body = {"jsonrpc": "2.0", "error": {"code": status, "message": message}, "id": None}
    headers = {}
    if status == 401:
        headers["WWW-Authenticate"] = 'Bearer realm="a2a"'
    return jsonify(body), status, headers
