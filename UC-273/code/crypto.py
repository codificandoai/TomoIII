"""Autenticación criptográfica Ed25519 para UC-273.

Gestión de identidades, firma y verificación de mensajes con:
- Ed25519 key pairs (alta performance, curvas elípticas).
- Nonce anti-replay con ventana temporal.
- Hash SHA-256 de payload para integridad.
- Registry de identidades con revocación.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

from config import CryptoConfig, get_config
from models import AgentRole, VerificationStatus


@dataclass
class AgentIdentity:
    """Identidad criptográfica de un agente."""
    agent_id: str
    public_key: Ed25519PublicKey
    role: AgentRole
    registered_at: float = field(default_factory=time.time)
    is_revoked: bool = False


@dataclass(frozen=True)
class SignedMessage:
    """Mensaje firmado criptográficamente con Ed25519."""
    message_id: str
    sender_id: str
    timestamp: float
    payload_type: str
    payload_hash: str
    payload: dict
    signature: bytes
    nonce: str

    def canonical_bytes(self) -> bytes:
        return (
            f"{self.message_id}|{self.sender_id}|{self.timestamp}|"
            f"{self.payload_type}|{self.payload_hash}|{self.nonce}"
        ).encode("utf-8")


class IdentityRegistry:
    """Registro de identidades con soporte de revocación."""

    def __init__(self) -> None:
        self._identities: Dict[str, AgentIdentity] = {}
        self._private_keys: Dict[str, Ed25519PrivateKey] = {}

    def register(self, agent_id: str, role: AgentRole) -> Tuple[AgentIdentity, Ed25519PrivateKey]:
        """Registra un nuevo agente y genera keypair."""
        if agent_id in self._identities:
            raise ValueError(f"Agent {agent_id} already registered")
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        identity = AgentIdentity(agent_id=agent_id, public_key=public_key, role=role)
        self._identities[agent_id] = identity
        self._private_keys[agent_id] = private_key
        return identity, private_key

    def revoke(self, agent_id: str) -> bool:
        if agent_id in self._identities:
            self._identities[agent_id].is_revoked = True
            return True
        return False

    def get(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._identities.get(agent_id)

    def get_private_key(self, agent_id: str) -> Optional[Ed25519PrivateKey]:
        return self._private_keys.get(agent_id)

    def is_valid(self, agent_id: str) -> bool:
        identity = self._identities.get(agent_id)
        return identity is not None and not identity.is_revoked

    @property
    def agent_count(self) -> int:
        return len(self._identities)

    def public_key_hex(self, agent_id: str) -> str:
        identity = self._identities.get(agent_id)
        if not identity:
            return ""
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        return identity.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


class MessageSigner:
    """Firma mensajes con la clave privada del agente."""

    def __init__(self, agent_id: str, private_key: Ed25519PrivateKey) -> None:
        self.agent_id = agent_id
        self.private_key = private_key
        self._nonce_counter = 0

    def sign(self, payload_type: str, payload: dict) -> SignedMessage:
        message_id = str(uuid4())
        timestamp = time.time()
        self._nonce_counter += 1
        nonce = f"{self.agent_id}:{timestamp}:{self._nonce_counter}"

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        canonical = (
            f"{message_id}|{self.agent_id}|{timestamp}|"
            f"{payload_type}|{payload_hash}|{nonce}"
        ).encode("utf-8")
        signature = self.private_key.sign(canonical)

        return SignedMessage(
            message_id=message_id,
            sender_id=self.agent_id,
            timestamp=timestamp,
            payload_type=payload_type,
            payload_hash=payload_hash,
            payload=payload,
            signature=signature,
            nonce=nonce,
        )


class MessageVerifier:
    """Verifica firmas, integridad, replay y revocación."""

    def __init__(self, registry: IdentityRegistry, config: CryptoConfig | None = None) -> None:
        self.registry = registry
        self.config = config or get_config().crypto
        self._seen_nonces: Set[str] = set()

    def verify(self, msg: SignedMessage) -> Tuple[bool, VerificationStatus]:
        identity = self.registry.get(msg.sender_id)
        if identity is None:
            return False, VerificationStatus.unknown_agent
        if identity.is_revoked:
            return False, VerificationStatus.revoked_identity

        if msg.nonce in self._seen_nonces:
            return False, VerificationStatus.replay_attack

        age = abs(time.time() - msg.timestamp)
        if age > self.config.nonce_window_seconds:
            return False, VerificationStatus.stale_message

        payload_bytes = json.dumps(msg.payload, sort_keys=True).encode("utf-8")
        computed_hash = hashlib.sha256(payload_bytes).hexdigest()
        if computed_hash != msg.payload_hash:
            return False, VerificationStatus.payload_tampered

        try:
            identity.public_key.verify(msg.signature, msg.canonical_bytes())
        except InvalidSignature:
            return False, VerificationStatus.invalid_signature

        self._seen_nonces.add(msg.nonce)
        if len(self._seen_nonces) > self.config.max_nonce_cache:
            self._seen_nonces.clear()

        return True, VerificationStatus.ok
