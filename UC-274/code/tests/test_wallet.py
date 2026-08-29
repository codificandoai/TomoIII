"""Tests de Wallet Ed25519 y DID."""
from __future__ import annotations

from wallet import DID, DIDRegistry, Wallet


def test_wallet_creation():
    w = Wallet()
    assert w.address.startswith("0x")
    assert len(w.address) == 42  # 0x + 40 hex chars


def test_wallet_sign_verify():
    w = Wallet()
    msg = b"test message"
    sig = w.sign(msg)
    assert w.verify(sig, msg) is True


def test_wallet_verify_wrong_message():
    w = Wallet()
    sig = w.sign(b"original")
    assert w.verify(sig, b"tampered") is False


def test_wallet_public_key_b64():
    w = Wallet()
    pk = w.public_key_b64()
    assert len(pk) > 0


def test_wallet_verify_with_pubkey():
    w = Wallet()
    msg = b"verify with address"
    sig = w.sign(msg)
    assert Wallet.verify_with_pubkey(sig, msg, w.public_key_b64(), w.address) is True


def test_did_create():
    w = Wallet()
    did = DID.create(w, {"role": "prosumer"})
    assert did.did.startswith("did:mustiamente:")
    assert did.address == w.address


def test_did_document():
    w = Wallet()
    did = DID.create(w)
    doc = did.document()
    assert doc["@context"] == "https://www.w3.org/ns/did/v1"
    assert doc["id"] == did.did
    assert len(doc["verificationMethod"]) == 1


def test_did_registry_register_resolve():
    reg = DIDRegistry()
    w = Wallet()
    did = DID.create(w)
    reg.register(did)
    assert reg.resolve(did.did) is did
    assert reg.resolve_by_address(w.address) is did


def test_did_registry_duplicate():
    reg = DIDRegistry()
    w = Wallet()
    did = DID.create(w)
    reg.register(did)
    try:
        reg.register(did)
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_did_registry_ens_names():
    reg = DIDRegistry()
    w = Wallet()
    did = DID.create(w)
    reg.register(did)
    reg.register_name("solar_alpha", w.address)
    assert reg.resolve_name("solar_alpha") == w.address
    assert reg.resolve_name("unknown") is None
