"""
UC-300 — Tokens de capacidad HMAC firmados.

Cada token es:
- Único (nonce).
- De un solo uso.
- De corta duración (TTL).
- Firmado con HMAC-SHA256.
- Vinculado exactamente al hash de la acción y al hash del expediente.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, List, Optional

from models_300 import CapabilityTokenPayload, generate_id


class CapabilityTokenManager:
    """Emite y valida tokens de capacidad firmados."""

    def __init__(self, secret: Optional[str] = None):
        # Generar secreto internamente si no se provee; nunca expuesto en logs.
        self._secret = (secret or secrets.token_hex(32)).encode("utf-8")
        self._revocation_time: Optional[float] = None
        self._issued_count: int = 0

    def issue(
        self,
        action_hash: str,
        dossier_hash: str,
        agent_id: str,
        action: str,
        scopes: Optional[List[str]] = None,
        ttl_seconds: float = 300.0,
    ) -> str:
        """Emite un nuevo token de capacidad."""
        issued_at = time.time()
        expires_at = issued_at + ttl_seconds
        nonce = secrets.token_urlsafe(16)
        payload = {
            "action_hash": action_hash,
            "dossier_hash": dossier_hash,
            "agent_id": agent_id,
            "action": action,
            "nonce": nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "scopes": scopes or [action],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            self._secret,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        payload["signature"] = signature
        self._issued_count += 1
        token_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(token_bytes).rstrip(b"=").decode("ascii")

    def parse(self, token: str) -> CapabilityTokenPayload:
        """Parsea un token sin validar firma ni TTL."""
        try:
            # Añadir padding si es necesario
            padded = token + "=" * (-len(token) % 4)
            raw = base64.urlsafe_b64decode(padded)
            data = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"Invalid token format: {exc}")
        return CapabilityTokenPayload(
            action_hash=data.get("action_hash", ""),
            dossier_hash=data.get("dossier_hash", ""),
            agent_id=data.get("agent_id", ""),
            action=data.get("action", ""),
            nonce=data.get("nonce", ""),
            issued_at=data.get("issued_at", 0.0),
            expires_at=data.get("expires_at", 0.0),
            scopes=data.get("scopes", []),
            signature=data.get("signature", ""),
        )

    def validate(
        self,
        token: str,
        expected_action_hash: str,
        expected_dossier_hash: str,
        expected_agent_id: str,
        expected_action: str,
        consumed_nonces: set,
    ) -> CapabilityTokenPayload:
        # Global shutdown revocation: reject any token issued before revocation time
        if self._revocation_time is not None:
            payload = self.parse(token)
            if payload.issued_at < self._revocation_time:
                raise ValueError("capability token revoked by shutdown")
        """Valida firma, TTL, uso único y vínculo exacto a hashes."""
        payload = self.parse(token)

        # Verificar TTL
        now = time.time()
        if payload.expires_at < now:
            raise ValueError("capability token expired")

        # Verificar firma
        signature = payload.signature
        verify_payload = {
            "action_hash": payload.action_hash,
            "dossier_hash": payload.dossier_hash,
            "agent_id": payload.agent_id,
            "action": payload.action,
            "nonce": payload.nonce,
            "issued_at": payload.issued_at,
            "expires_at": payload.expires_at,
            "scopes": payload.scopes,
        }
        canonical = json.dumps(verify_payload, sort_keys=True, separators=(",", ":"))
        expected_signature = hmac.new(
            self._secret,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("capability token signature mismatch")

        # One-use nonce
        if payload.nonce in consumed_nonces:
            raise ValueError("capability token replay detected")

        # Vínculo exacto
        if payload.action_hash != expected_action_hash:
            raise ValueError("action hash mismatch: parameters changed")
        if payload.dossier_hash != expected_dossier_hash:
            raise ValueError("dossier hash mismatch")
        if payload.agent_id != expected_agent_id:
            raise ValueError("agent_id mismatch")
        if payload.action != expected_action:
            raise ValueError("action mismatch")

        # Consumir nonce (one-use) al validar con éxito
        self.mark_consumed(payload.nonce, consumed_nonces)

        return payload

    def mark_consumed(self, nonce: str, consumed_nonces: set) -> None:
        consumed_nonces.add(nonce)

    def revoke_all(self) -> int:
        """Revoke all pending/issued capability tokens by setting a revocation time."""
        self._revocation_time = time.time()
        return self._issued_count

    def resume_issuing(self) -> None:
        """Resume accepting capability tokens after approved reactivation."""
        self._revocation_time = None
        self._issued_count = 0

    def rotate_secret(self) -> str:
        """Rota el secreto interno y devuelve el hash público del nuevo secreto."""
        self._secret = secrets.token_hex(32).encode("utf-8")
        return hashlib.sha256(self._secret).hexdigest()
