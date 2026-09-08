"""UC-290 — Tests for HITLGuardian.approve_reactivation (UC-324)."""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hitl_guardian import HITLGuardian


def _guardian():
    return HITLGuardian()


def test_approve_reactivation_requires_reviewer():
    g = _guardian()
    req = {
        "shutdown_id": "sd-290-001",
        "recovery_state_hash": "hash1",
        "reviewer_id": "",
        "request_id": "r1",
        "timestamp": time.time(),
    }
    result = g.approve_reactivation(req)
    assert result["approved"] is False
    assert "reviewer" in result["reason"].lower()


def test_approve_reactivation_rejects_expired_ttl():
    g = _guardian()
    req = {
        "shutdown_id": "sd-290-002",
        "recovery_state_hash": "hash2",
        "reviewer_id": "human-1",
        "ttl_seconds": 0.0,
        "timestamp": time.time() - 1.0,
        "request_id": "r2",
    }
    result = g.approve_reactivation(req)
    assert result["approved"] is False
    assert ("expired" in result["reason"].lower() or "ttl" in result["reason"].lower())


def test_approve_reactivation_anti_replay():
    g = _guardian()
    req = {
        "shutdown_id": "sd-290-003",
        "recovery_state_hash": "hash3",
        "reviewer_id": "human-1",
        "request_id": "r3",
        "timestamp": time.time(),
    }
    # First attempt with wrong hash still consumes request_id
    result1 = g.approve_reactivation(req)
    assert result1["approved"] is True
    result2 = g.approve_reactivation(req)
    assert result2["approved"] is False
    assert "replay" in result2["reason"].lower()


def test_approve_reactivation_approves_valid():
    g = _guardian()
    req = {
        "shutdown_id": "sd-290-004",
        "recovery_state_hash": "hash4",
        "reviewer_id": "human-1",
        "request_id": "r4",
        "timestamp": time.time(),
    }
    result = g.approve_reactivation(req)
    assert result["approved"] is True
    assert result["reviewer_id"] == "human-1"
