"""Agentes de cifrado, KMS/Vault y políticas de red Zero Trust."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.privacy.models_privacy import CryptoVaultResult, NetworkPolicy


@dataclass
class EncryptedBlob:
    ciphertext: str
    iv: str
    tag: str
    key_hash: str


class CryptoVaultAgent:
    """
    Simula un broker criptográfico + Vault/KMS.

    - Emite data keys efímeras vinculadas a un recurso.
    - Cifra/descifra con AES-256-GCM simulado.
    - Registra mTLS/TLS 1.3 y encriptación en reposo.

    En producción se conecta a HashiCorp Vault / AWS KMS / Azure Key Vault.
    """

    def __init__(self) -> None:
        self._keys: Dict[str, bytes] = {}
        self._leases: Dict[str, float] = {}

    def _derive_key(self, key_id: str) -> bytes:
        if key_id not in self._keys:
            self._keys[key_id] = secrets.token_bytes(32)
            self._leases[key_id] = time.time() + 3600
        return self._keys[key_id]

    def issue_data_key(self, resource: str, ttl_seconds: float = 3600) -> CryptoVaultResult:
        key_id = f"uc703-dk-{secrets.token_urlsafe(8)}"
        self._keys[key_id] = secrets.token_bytes(32)
        self._leases[key_id] = time.time() + ttl_seconds
        secret_handle = secrets.token_urlsafe(24)
        return CryptoVaultResult(
            key_id=key_id,
            encryption_at_rest=True,
            transit_tls_version="1.3",
            secret_handle=secret_handle,
            lease_expires_at=self._leases[key_id],
        )

    def encrypt(self, plaintext: str, key_id: str) -> EncryptedBlob:
        key = self._keys.get(key_id) or self._derive_key(key_id)
        iv = secrets.token_hex(12)
        # Simulación determinista: HMAC-SHA256 como "ciphertext".
        ciphertext = hashlib.sha256(f"{plaintext}{iv}{key.hex()}".encode()).hexdigest()
        tag = hashlib.sha256(ciphertext.encode()).hexdigest()[:32]
        return EncryptedBlob(
            ciphertext=ciphertext,
            iv=iv,
            tag=tag,
            key_hash=hashlib.sha256(key).hexdigest()[:16],
        )

    def decrypt(self, blob: EncryptedBlob, key_id: str) -> str:
        # En el simulador no se puede recuperar el texto; solo se valida key_hash.
        key = self._keys.get(key_id)
        if key is None:
            raise ValueError("key not found or expired")
        expected_hash = hashlib.sha256(key).hexdigest()[:16]
        if blob.key_hash != expected_hash:
            raise ValueError("key mismatch")
        return "[decrypted-payload]"


class NetworkPolicyAgent:
    """
    Valida políticas de red Zero Trust para entrenamiento e inferencia:
    - Sin exposición pública
    - VPC privada / PrivateLink
    - mTLS obligatorio
    - TLS 1.3
    - Endpoints permitidos
    """

    DEFAULT = NetworkPolicy(
        vpc_only=True,
        public_exposure=False,
        mtls_required=True,
        tls_version="1.3",
        private_link=True,
        allowed_endpoints=["kms.internal", "vault.internal", "s3-vpc.internal"],
    )

    def validate(self, policy: Optional[NetworkPolicy] = None) -> Dict[str, Any]:
        policy = policy or self.DEFAULT
        findings: List[str] = []
        if not policy.vpc_only:
            findings.append("vpc_only_required")
        if policy.public_exposure:
            findings.append("public_exposure_forbidden")
        if not policy.mtls_required:
            findings.append("mtls_required")
        if policy.tls_version != "1.3":
            findings.append("tls_1.3_required")
        if not policy.private_link:
            findings.append("private_link_required")
        if not policy.allowed_endpoints:
            findings.append("allowed_endpoints_empty")
        return {
            "policy_id": policy.policy_id,
            "passed": not findings,
            "findings": findings,
            "policy": policy.to_dict(),
        }

    def check_endpoint(self, endpoint: str, policy: Optional[NetworkPolicy] = None) -> bool:
        policy = policy or self.DEFAULT
        return any(endpoint.endswith(ae) for ae in policy.allowed_endpoints)
