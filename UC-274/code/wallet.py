"""Wallets Web3 e Identidades Descentralizadas (DID) para UC-274.

Implementa:
- Wallet Ed25519: keypair, dirección derivada (SHA-256), firma y verificación.
- DID (Decentralized Identifier): W3C DID Core v1, formato did:mustiamente:<address>.
- DIDRegistry: registro/resolución de DIDs.
- ENS-like naming: @alias.mustiamente → address.
"""
from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class Wallet:
    """Wallet Web3: par de claves Ed25519 + dirección derivada SHA-256."""

    def __init__(self, private_key: Optional[Ed25519PrivateKey] = None) -> None:
        self.private_key = private_key or Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.address = "0x" + hashlib.sha256(pub_bytes).hexdigest()[:40]

    def sign(self, message: bytes) -> bytes:
        return self.private_key.sign(message)

    def verify(self, signature: bytes, message: bytes) -> bool:
        try:
            self.public_key.verify(signature, message)
            return True
        except InvalidSignature:
            return False

    def public_key_b64(self) -> str:
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(pub_bytes).decode()

    @staticmethod
    def verify_with_pubkey(signature: bytes, message: bytes,
                           public_key_b64: str, address: str) -> bool:
        """Verifica firma y que la clave pública corresponde a la dirección."""
        try:
            pub_bytes = base64.b64decode(public_key_b64)
            pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(signature, message)
            derived = "0x" + hashlib.sha256(pub_bytes).hexdigest()[:40]
            return derived == address
        except Exception:
            return False


@dataclass(frozen=True)
class DID:
    """Identidad Descentralizada (W3C DID Core v1). Formato: did:mustiamente:<address>."""
    did: str
    address: str
    public_key_b64: str
    created_at: float
    controller: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, wallet: Wallet, metadata: Optional[dict] = None) -> DID:
        return cls(
            did=f"did:mustiamente:{wallet.address}",
            address=wallet.address,
            public_key_b64=wallet.public_key_b64(),
            created_at=time.time(),
            controller=wallet.address,
            metadata=metadata or {},
        )

    def document(self) -> dict:
        """DID Document según W3C."""
        return {
            "@context": "https://www.w3.org/ns/did/v1",
            "id": self.did,
            "controller": self.controller,
            "verificationMethod": [{
                "id": f"{self.did}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": self.controller,
                "publicKeyMultibase": self.public_key_b64,
            }],
            "authentication": [f"{self.did}#key-1"],
            "created": datetime.fromtimestamp(self.created_at).isoformat(),
            "metadata": self.metadata,
        }


class DIDRegistry:
    """Registro descentralizado de DIDs (simula on-chain registry)."""

    def __init__(self) -> None:
        self._dids: Dict[str, DID] = {}
        self._address_to_did: Dict[str, str] = {}
        self._names: Dict[str, str] = {}  # ENS-like: name → address

    def register(self, did: DID) -> None:
        if did.did in self._dids:
            raise ValueError(f"DID {did.did} already registered")
        self._dids[did.did] = did
        self._address_to_did[did.address] = did.did

    def resolve(self, did_str: str) -> Optional[DID]:
        return self._dids.get(did_str)

    def resolve_by_address(self, address: str) -> Optional[DID]:
        did_str = self._address_to_did.get(address)
        return self._dids.get(did_str) if did_str else None

    def register_name(self, name: str, address: str) -> None:
        """Registra nombre ENS-like (@name.mustiamente → address)."""
        if name in self._names:
            raise ValueError(f"Name {name} already taken")
        self._names[name] = address

    def resolve_name(self, name: str) -> Optional[str]:
        return self._names.get(name)

    @property
    def count(self) -> int:
        return len(self._dids)
