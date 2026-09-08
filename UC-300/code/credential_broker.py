"""
UC-300 — Broker de credenciales opacas temporales.

Emite credenciales de corta duración vinculadas a un capability token
y a un recurso específico. Los secretos reales nunca se exponen en logs
ni en la API; solo se referencian por handle.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CredentialLease:
    """Credencial temporal emitida por el broker."""
    lease_id: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    capability_token_hash: str = ""  # hash del token, nunca el token completo
    resource: str = ""
    scope: str = ""
    issued_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    revoked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "capability_token_hash": self.capability_token_hash,
            "resource": self.resource,
            "scope": self.scope,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "metadata": {k: v for k, v in self.metadata.items() if k != "secret"},
            "revoked": self.revoked,
        }


class CredentialBroker:
    """Gestiona credenciales temporales de mínimo privilegio."""

    def __init__(self, default_ttl_seconds: float = 300.0):
        self._leases: Dict[str, CredentialLease] = {}
        self._default_ttl_seconds = default_ttl_seconds

    def issue(
        self,
        capability_token: str,
        resource: str,
        scope: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[float] = None,
    ) -> CredentialLease:
        """Emite una credencial temporal vinculada a un capability token."""
        token_hash = hashlib.sha256(capability_token.encode("utf-8")).hexdigest()
        now = time.time()
        lease = CredentialLease(
            capability_token_hash=token_hash,
            resource=resource,
            scope=scope,
            issued_at=now,
            expires_at=now + (ttl_seconds or self._default_ttl_seconds),
            metadata=metadata or {},
        )
        # Simulación: almacenar un "secreto" opaco interno
        lease.metadata["secret_handle"] = secrets.token_urlsafe(24)
        self._leases[lease.lease_id] = lease
        return lease

    def validate(self, lease_id: str, capability_token: str, resource: str) -> CredentialLease:
        """Valida que una credencial sea válida para un token y recurso."""
        lease = self._leases.get(lease_id)
        if lease is None or lease.revoked:
            raise ValueError("invalid or revoked credential lease")
        if lease.expires_at < time.time():
            raise ValueError("credential lease expired")
        expected_token_hash = hashlib.sha256(capability_token.encode("utf-8")).hexdigest()
        if lease.capability_token_hash != expected_token_hash:
            raise ValueError("credential lease not bound to this capability token")
        if lease.resource != resource:
            raise ValueError("credential lease not bound to this resource")
        return lease

    def revoke(self, lease_id: str) -> bool:
        lease = self._leases.get(lease_id)
        if lease is None:
            return False
        lease.revoked = True
        return True

    def cleanup(self) -> int:
        """Elimina credenciales expiradas. Devuelve cuántas se eliminaron."""
        now = time.time()
        expired = [k for k, v in self._leases.items() if v.expires_at < now]
        for k in expired:
            del self._leases[k]
        return len(expired)

    def revoke_all(self) -> int:
        """Revoke all active credential leases."""
        count = 0
        for lease in self._leases.values():
            if not lease.revoked:
                lease.revoked = True
                count += 1
        return count

    def resume_issuing(self) -> int:
        """After approved reactivation, clear only expired revoked leases."""
        now = time.time()
        expired = [k for k, v in self._leases.items() if v.revoked and v.expires_at < now]
        for k in expired:
            del self._leases[k]
        return len(expired)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "active_leases": len(self._leases),
            "leases": [lease.to_dict() for lease in self._leases.values()],
        }
