"""Guardrails integrados de atlas-demo para UC-273.

Capa de defensa en profundidad que incluye:
- Escaneo de inyección de prompt (regex heurístico).
- Redacción DLP (PII: SSN, email, tarjetas, saldos).
- Verificación BOLA (object-level authorization).
- Política de egress (allowlist de hosts).
- Autenticación de identidad de agente (JWT HMAC-SHA256 / SPIFFE).

Adaptado de: atlas-demo/app/guardrails.py
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from config import GuardrailsConfig, get_config


# ============================================================
# Injection Detection
# ============================================================

INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"ignore your (safety|system) (policy|prompt)",
    r"maintenance mode",
    r"you are now",
    r"do not (mention|tell|inform)",
    r"system note for the assistant",
    r"exfiltrat",
    r"email .* to .*@",
]


def scan_injection(text: str) -> Tuple[bool, str, int]:
    """Escanea texto por patrones de inyección de prompt.

    Returns: (blocked, detail, patterns_matched)
    """
    lowered = text.lower()
    hits = [p for p in INJECTION_PATTERNS if re.search(p, lowered)]
    if hits:
        return True, f"Matched {len(hits)} injection pattern(s): {hits[0]!r}", len(hits)
    return False, "No injection signal detected", 0


# ============================================================
# DLP Redaction
# ============================================================

PII_PATTERNS: Dict[str, re.Pattern] = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "CARD": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "BALANCE": re.compile(r"\$\s?\d[\d,]*\.\d{2}"),
}


def redact_pii(text: str) -> Tuple[str, List[str]]:
    """Redacta PII común del texto."""
    found: List[str] = []
    redacted = text
    for label, pattern in PII_PATTERNS.items():
        if pattern.search(redacted):
            found.append(label)
            redacted = pattern.sub(f"[REDACTED_{label}]", redacted)
    return redacted, found


# ============================================================
# BOLA (Object-Level Authorization)
# ============================================================

def check_bola(principal: str, resource_owner: str) -> bool:
    """Verifica que el principal es el dueño del recurso."""
    return principal == resource_owner


# ============================================================
# Egress Policy
# ============================================================

def check_egress(host: str, config: GuardrailsConfig | None = None) -> bool:
    """Verifica si el host está en la allowlist de egress."""
    cfg = config or get_config().guardrails
    return host in cfg.allowed_egress_hosts


# ============================================================
# Agent Identity JWT (SPIFFE/SVID style)
# ============================================================

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("ascii"))


def create_agent_token(
    identity: str,
    secret_key: str | None = None,
    key_id: str = "agent-key-1",
    audience: str = "atlas-finance",
    expires_in_seconds: int = 300,
    issuer: str = "https://agent-identity.atlas.internal",
) -> str:
    """Crea token JWT firmado con HMAC-SHA256 para identidad de agente."""
    cfg = get_config().guardrails
    secret = secret_key or cfg.agent_jwt_secret
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {
        "iss": issuer,
        "sub": identity,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in_seconds,
        "jti": str(uuid.uuid4())[:8],
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signing_input = f"{_b64url_encode(header_bytes)}.{_b64url_encode(payload_bytes)}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def verify_agent_token(
    token: str | None,
    expected_audience: str = "atlas-finance",
    config: GuardrailsConfig | None = None,
) -> dict:
    """Verifica token JWT de identidad de agente."""
    cfg = config or get_config().guardrails

    if not token:
        return {"valid": False, "label": "missing_token", "detail": "No agent identity token presented"}

    if token.startswith("Bearer "):
        token = token[7:].strip()

    parts = token.split(".")
    if len(parts) != 3:
        return {"valid": False, "label": "malformed_token", "detail": "Token is not a valid 3-part JWT"}

    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        sig = _b64url_decode(parts[2])
    except Exception as exc:
        return {"valid": False, "label": "unparseable_token", "detail": f"Failed to decode token: {exc}"}

    alg = header.get("alg", "UNKNOWN")
    key_id = header.get("kid", "unknown")
    issuer = payload.get("iss", "unknown")
    subject = payload.get("sub", "unknown")
    audience = payload.get("aud", "unknown")

    # 1. Verificar firma
    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    expected_sig = hmac.new(cfg.agent_jwt_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        return {
            "valid": False, "label": "invalid_signature",
            "detail": f"Signature verification failed for key {key_id!r}",
            "algorithm": alg, "key_id": key_id, "issuer": issuer, "subject": subject, "audience": audience,
        }

    # 2. Expiración
    now = int(time.time())
    exp = payload.get("exp", 0)
    if exp and now > exp:
        return {
            "valid": False, "label": "token_expired",
            "detail": f"Token expired at {exp} (current: {now})",
            "algorithm": alg, "key_id": key_id, "issuer": issuer, "subject": subject, "audience": audience,
        }

    # 3. Audience
    if audience != expected_audience:
        return {
            "valid": False, "label": "audience_mismatch",
            "detail": f"Token audience {audience!r} != expected {expected_audience!r}",
            "algorithm": alg, "key_id": key_id, "issuer": issuer, "subject": subject, "audience": audience,
        }

    # 4. Identidad autorizada
    if subject != cfg.trusted_identity:
        return {
            "valid": False, "label": "identity_denied",
            "detail": f"Identity {subject!r} not authorized (expected {cfg.trusted_identity!r})",
            "algorithm": alg, "key_id": key_id, "issuer": issuer, "subject": subject, "audience": audience,
        }

    return {
        "valid": True, "label": "authorized",
        "detail": f"Verified identity {subject!r} (key={key_id})",
        "algorithm": alg, "key_id": key_id, "issuer": issuer, "subject": subject, "audience": audience,
    }
