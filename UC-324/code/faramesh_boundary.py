"""UC-324 — Frontera criptográfica/determinista (F) inspirada en faramesh-core.

El repositorio `faramesh/faramesh-core` no es un paquete Python instalable
(no tiene `setup.py` ni `pyproject.toml`). UC-324 implementa aquí el patrón de
frontera criptográfica entre el orquestador LLM y acciones externas (shell,
SQL, APIs, pagos, trading, etc.).

Características:
- HMAC-SHA256 determinista de intenciones de ejecución.
- Nonce + timestamp anti-replay.
- TTL de firma configurado.
- Política de qué clases de acción requieren firma (`execute`, `transact`, `delete`).
- Bloqueo de patrones peligrosos (shell, SQL, import dinámico, etc.) en inputs.
- Separación neta: el módulo solo aprueba o bloquea; nunca ejecuta skills.
- Auditoría de cada verificación con razones explícitas.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union


DEFAULT_DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"drop\s+table",
    r"exec\s*\(",
    r"subprocess",
    r"os\.system",
    r"__import__",
    r"eval\s*\(",
    r"compile\s*\(",
    r"open\s*\(\s*[\"'].*[\"']\s*,\s*[\"']w[\"']",
    r"SELECT\s+.*FROM\s+.*;\s*DROP",
    r";\s*DROP\s+TABLE",
]


@dataclass
class BoundaryPolicy:
    """Política de la frontera criptográfica."""

    action_classes_requiring_signature: Set[str] = field(
        default_factory=lambda: {"execute", "transact", "delete"}
    )
    signature_ttl_seconds: int = 60
    require_nonce: bool = True
    dangerous_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_DANGEROUS_PATTERNS))


@dataclass
class VerificationResult:
    """Resultado de una verificación de frontera."""

    allowed: bool = True
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "issues": self.issues,
            "details": self.details,
        }


class NonceStore:
    """Almacén de nonces usados con expiración simple (TTL x 2)."""

    def __init__(self, ttl_seconds: int = 120) -> None:
        self._ttl = ttl_seconds
        self._store: Dict[str, float] = {}

    def add(self, nonce: str) -> None:
        self._store[nonce] = time.time()
        self._prune()

    def has(self, nonce: str) -> bool:
        self._prune()
        return nonce in self._store

    def _prune(self) -> None:
        now = time.time()
        cutoff = now - (self._ttl * 2)
        self._store = {n: ts for n, ts in self._store.items() if ts > cutoff}


class CryptoBoundary:
    """Frontera criptográfica determinista HMAC."""

    def __init__(
        self,
        secret: Optional[str] = None,
        policy: Optional[BoundaryPolicy] = None,
        nonce_store: Optional[NonceStore] = None,
    ) -> None:
        self._secret = (secret or os.environ.get("FARAMESH_SECRET", "uc324-default-secret")).encode()
        self._policy = policy if policy is not None else BoundaryPolicy()
        self._nonce_store = nonce_store if nonce_store is not None else NonceStore(
            ttl_seconds=self._policy.signature_ttl_seconds * 2
        )

    def _build_payload(
        self,
        skill_name: str,
        inputs: Dict[str, Any],
        nonce: Optional[str],
        timestamp: Optional[int],
    ) -> bytes:
        data: Dict[str, Any] = {
            "skill": skill_name,
            "inputs": inputs,
        }
        if nonce is not None:
            data["nonce"] = nonce
        if timestamp is not None:
            data["timestamp"] = timestamp
        return json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")

    def sign_intent(
        self,
        skill_name: str,
        inputs: Dict[str, Any],
        nonce: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Firma una intención de ejecución.

        Returns:
            Diccionario con `signature`, `nonce`, `timestamp`, `skill`, `inputs`.
        """
        ts = timestamp if timestamp is not None else int(time.time())
        nc = nonce if nonce is not None else secrets.token_urlsafe(16)
        payload = self._build_payload(skill_name, inputs, nc, ts)
        signature = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return {
            "signature": signature,
            "nonce": nc,
            "timestamp": ts,
            "skill": skill_name,
            "inputs": inputs,
        }

    def verify_intent(
        self,
        skill_name: str,
        inputs: Dict[str, Any],
        action_class: str,
        signature: Optional[str] = None,
        nonce: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> VerificationResult:
        """Verifica una intención de ejecución."""
        result = VerificationResult()
        result.details["skill"] = skill_name
        result.details["action_class"] = action_class
        result.details["requires_signature"] = action_class in self._policy.action_classes_requiring_signature
        result.details["signature_present"] = signature is not None

        sensitive = action_class in self._policy.action_classes_requiring_signature

        # Verificación de firma para acciones sensibles
        if sensitive:
            if signature is None:
                result.allowed = False
                result.issues.append(
                    f"Faramesh: sensitive action '{action_class}' requires an HMAC signature"
                )
            else:
                if self._policy.require_nonce and nonce is None:
                    result.allowed = False
                    result.issues.append("Faramesh: signature requires a nonce")

                if timestamp is None:
                    result.allowed = False
                    result.issues.append("Faramesh: signature requires a timestamp")
                elif self._policy.signature_ttl_seconds:
                    age = time.time() - timestamp
                    if age > self._policy.signature_ttl_seconds:
                        result.allowed = False
                        result.issues.append(
                            f"Faramesh: signature expired (age={age:.1f}s, ttl={self._policy.signature_ttl_seconds}s)"
                        )

                if nonce is not None and self._nonce_store.has(nonce):
                    result.allowed = False
                    result.issues.append("Faramesh: nonce already used (replay detected)")

                expected = hmac.new(
                    self._secret,
                    self._build_payload(skill_name, inputs, nonce, timestamp),
                    hashlib.sha256,
                ).hexdigest()
                if not hmac.compare_digest(expected, signature):
                    result.allowed = False
                    result.issues.append("Faramesh: invalid HMAC signature")

                if result.allowed and nonce is not None:
                    self._nonce_store.add(nonce)
                    result.details["nonce_accepted"] = True

        # Bloqueo de patrones peligrosos en el payload
        payload_text = json.dumps({"skill": skill_name, "inputs": inputs}, ensure_ascii=False).lower()
        for pattern in self._policy.dangerous_patterns:
            if re.search(pattern, payload_text, re.IGNORECASE):
                result.allowed = False
                result.issues.append(f"Faramesh: dangerous pattern detected ({pattern})")
                result.details.setdefault("dangerous_patterns_matched", []).append(pattern)

        result.details["signature_valid"] = result.allowed and (not sensitive or signature is not None)
        return result

    @staticmethod
    def extract_signature_parts(
        signature_value: Optional[Union[str, Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Permite que la firma sea un string o un dict con nonce/timestamp."""
        if signature_value is None:
            return None, None, None
        if isinstance(signature_value, dict):
            return (
                signature_value.get("signature"),
                signature_value.get("nonce"),
                signature_value.get("timestamp"),
            )
        return signature_value, None, None


def sign_skill_intent(
    secret: str,
    skill_name: str,
    inputs: Dict[str, Any],
    nonce: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Helper de alto nivel para firmar una intención de skill."""
    return CryptoBoundary(secret=secret).sign_intent(skill_name, inputs, nonce, timestamp)


def verify_skill_intent(
    secret: str,
    skill_name: str,
    inputs: Dict[str, Any],
    action_class: str,
    signature: Optional[Union[str, Dict[str, Any]]] = None,
    policy: Optional[BoundaryPolicy] = None,
) -> Dict[str, Any]:
    """Helper de alto nivel para verificar una intención de skill."""
    boundary = CryptoBoundary(secret=secret, policy=policy)
    sig, nonce, timestamp = boundary.extract_signature_parts(signature)
    return boundary.verify_intent(skill_name, inputs, action_class, sig, nonce, timestamp).to_dict()
