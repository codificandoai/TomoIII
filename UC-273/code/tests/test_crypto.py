"""Tests de autenticación criptográfica Ed25519."""
from __future__ import annotations

import time

from crypto import IdentityRegistry, MessageSigner, MessageVerifier
from models import AgentRole, VerificationStatus


def _setup():
    reg = IdentityRegistry()
    identity, pk = reg.register("agent_a", AgentRole.trader)
    signer = MessageSigner("agent_a", pk)
    verifier = MessageVerifier(reg)
    return reg, signer, verifier


def test_sign_and_verify():
    _, signer, verifier = _setup()
    msg = signer.sign("trade", {"symbol": "AAPL", "qty": 100})
    valid, status = verifier.verify(msg)
    assert valid is True
    assert status == VerificationStatus.ok


def test_unknown_agent():
    reg = IdentityRegistry()
    _, pk = reg.register("known", AgentRole.trader)
    signer = MessageSigner("unknown_agent", pk)
    verifier = MessageVerifier(reg)
    msg = signer.sign("test", {})
    valid, status = verifier.verify(msg)
    assert valid is False
    assert status == VerificationStatus.unknown_agent


def test_revoked_identity():
    reg, signer, verifier = _setup()
    reg.revoke("agent_a")
    msg = signer.sign("test", {})
    valid, status = verifier.verify(msg)
    assert valid is False
    assert status == VerificationStatus.revoked_identity


def test_replay_detection():
    _, signer, verifier = _setup()
    msg = signer.sign("test", {"data": 1})
    valid1, _ = verifier.verify(msg)
    assert valid1 is True
    valid2, status = verifier.verify(msg)
    assert valid2 is False
    assert status == VerificationStatus.replay_attack


def test_payload_tampered():
    reg, signer, verifier = _setup()
    msg = signer.sign("test", {"original": True})
    # Tamper with payload
    from crypto import SignedMessage
    tampered = SignedMessage(
        message_id=msg.message_id,
        sender_id=msg.sender_id,
        timestamp=msg.timestamp,
        payload_type=msg.payload_type,
        payload_hash=msg.payload_hash,
        payload={"original": False},
        signature=msg.signature,
        nonce=msg.nonce,
    )
    valid, status = verifier.verify(tampered)
    assert valid is False
    assert status == VerificationStatus.payload_tampered


def test_registry_public_key_hex():
    reg = IdentityRegistry()
    reg.register("agent_x", AgentRole.oracle)
    hex_key = reg.public_key_hex("agent_x")
    assert len(hex_key) == 64  # Ed25519 public key is 32 bytes = 64 hex chars
