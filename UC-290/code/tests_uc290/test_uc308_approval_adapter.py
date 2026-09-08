"""UC-290 adapter tests for UC-308 Champion/Challenger promotion approval."""

import time

import pytest

from hitl_guardian import HITLGuardian


@pytest.fixture
def guardian():
    return HITLGuardian()


def _valid_request(guardian, overrides=None):
    base = {
        "experiment_id": "exp-1",
        "report_hash": "a" * 64,
        "reviewer_id": "operator-1",
        "request_id": "req-1",
        "timestamp": time.time(),
        "ttl_seconds": 3600.0,
        "champion_version": "1.0.0",
        "challenger_version": "2.0.0",
    }
    if overrides:
        base.update(overrides)
    return base


def test_approve_experiment_promotion_requires_reviewer(guardian):
    req = _valid_request(guardian, {"reviewer_id": ""})
    result = guardian.approve_experiment_promotion(req)
    assert not result["approved"]
    assert "reviewer_id" in result["reason"]


def test_approve_experiment_promotion_requires_experiment_and_hash(guardian):
    req = _valid_request(guardian, {"experiment_id": "", "report_hash": ""})
    result = guardian.approve_experiment_promotion(req)
    assert not result["approved"]
    assert "experiment_id and report_hash required" in result["reason"]


def test_approve_experiment_promotion_ttl(guardian):
    req = _valid_request(guardian, {
        "ttl_seconds": 0.001,
        "timestamp": time.time() - 10.0,
    })
    result = guardian.approve_experiment_promotion(req)
    assert not result["approved"]
    assert "expired" in result["reason"]


def test_approve_experiment_promotion_anti_replay(guardian):
    req = _valid_request(guardian, {"request_id": "req-2"})
    result1 = guardian.approve_experiment_promotion(req)
    assert result1["approved"]
    result2 = guardian.approve_experiment_promotion(req)
    assert not result2["approved"]
    assert "anti-replay" in result2["reason"]


def test_approve_experiment_promotion_future_timestamp(guardian):
    req = _valid_request(guardian, {"timestamp": time.time() + 120.0})
    result = guardian.approve_experiment_promotion(req)
    assert not result["approved"]
    assert "future" in result["reason"]
