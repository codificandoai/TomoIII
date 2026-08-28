"""Tests del audit ledger inmutable."""
from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from audit_ledger import AuditLedger


def _ledger():
    pk = Ed25519PrivateKey.generate()
    return AuditLedger(pk)


def test_append_entry():
    ledger = _ledger()
    entry = ledger.append("agent_a", "trade.executed", {"symbol": "AAPL"})
    assert entry.index == 0
    assert entry.agent_id == "agent_a"
    assert ledger.chain_length == 1


def test_chain_integrity():
    ledger = _ledger()
    ledger.append("a", "event.1", {"data": 1})
    ledger.append("b", "event.2", {"data": 2})
    ledger.append("c", "event.3", {"data": 3})
    valid, broken = ledger.verify_chain()
    assert valid is True
    assert broken is None


def test_genesis_hash():
    ledger = _ledger()
    entry = ledger.append("a", "test", {})
    assert entry.previous_hash == "0" * 64


def test_hash_chain():
    ledger = _ledger()
    e1 = ledger.append("a", "e1", {})
    e2 = ledger.append("b", "e2", {})
    assert e2.previous_hash == e1.entry_hash


def test_agent_history():
    ledger = _ledger()
    ledger.append("agent_a", "e1", {})
    ledger.append("agent_b", "e2", {})
    ledger.append("agent_a", "e3", {})
    history = ledger.get_agent_history("agent_a")
    assert len(history) == 2


def test_security_events():
    ledger = _ledger()
    ledger.append("a", "security.auth_failure", {})
    ledger.append("b", "trade.executed", {})
    ledger.append("c", "security.rate_limit", {})
    sec = ledger.get_security_events()
    assert len(sec) == 2
