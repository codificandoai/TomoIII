"""Tests de seguridad A2A: autenticación y autorización."""
from __future__ import annotations

import pytest

from security import (
    AuthenticationError,
    AuthorizationError,
    SecurityContext,
    SecurityManager,
)


def test_api_key_authentication_success() -> None:
    mgr = SecurityManager()
    ctx = mgr.authenticate_request({"X-API-Key": "dev-api-key"})
    assert ctx.authenticated is True
    assert ctx.scheme == "apiKey"


def test_api_key_authentication_failure() -> None:
    mgr = SecurityManager()
    with pytest.raises(AuthenticationError):
        mgr.authenticate_request({"X-API-Key": "wrong-key"})


def test_missing_credentials_raises() -> None:
    mgr = SecurityManager()
    with pytest.raises(AuthenticationError):
        mgr.authenticate_request({})


def test_generate_and_validate_jwt() -> None:
    mgr = SecurityManager()
    token = mgr.generate_token("user-1", ["a2a:read"])
    ctx = mgr.authenticate_request({"Authorization": f"Bearer {token}"})
    assert ctx.authenticated is True
    assert ctx.identity == "user-1"
    assert "a2a:read" in ctx.scopes
    assert ctx.scheme == "bearer"


def test_authorize_skill_allowed() -> None:
    ctx = SecurityContext(authenticated=True, scopes=("a2a:read",))
    mgr = SecurityManager()
    mgr.authorize_skill(ctx, ["a2a:read"])


def test_authorize_skill_denied() -> None:
    ctx = SecurityContext(authenticated=True, scopes=("a2a:read",))
    mgr = SecurityManager()
    with pytest.raises(AuthorizationError):
        mgr.authorize_skill(ctx, ["a2a:write"])


def test_admin_scope_grants_all() -> None:
    ctx = SecurityContext(authenticated=True, scopes=("admin",))
    mgr = SecurityManager()
    mgr.authorize_skill(ctx, ["a2a:write", "a2a:admin"])
