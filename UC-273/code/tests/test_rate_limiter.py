"""Tests del rate limiter y message size limiter."""
from __future__ import annotations

from config import RateLimitConfig
from rate_limiter import MessageSizeLimiter, TokenBucketRateLimiter


def test_allow_within_limit():
    rl = TokenBucketRateLimiter(RateLimitConfig(rate_per_second=10.0, burst_capacity=5))
    for _ in range(5):
        assert rl.allow("agent_a") is True


def test_deny_over_burst():
    rl = TokenBucketRateLimiter(RateLimitConfig(rate_per_second=0.0, burst_capacity=3))
    assert rl.allow("agent_a") is True
    assert rl.allow("agent_a") is True
    assert rl.allow("agent_a") is True
    assert rl.allow("agent_a") is False


def test_remaining_tokens():
    rl = TokenBucketRateLimiter(RateLimitConfig(rate_per_second=10.0, burst_capacity=10))
    rl.allow("agent_a")
    remaining = rl.get_remaining("agent_a")
    assert remaining < 10


def test_size_limiter_ok():
    sl = MessageSizeLimiter(RateLimitConfig(max_payload_bytes=1024, max_payload_fields=50))
    valid, reason = sl.validate({"key": "value"})
    assert valid is True
    assert reason == "ok"


def test_size_limiter_too_large():
    sl = MessageSizeLimiter(RateLimitConfig(max_payload_bytes=10, max_payload_fields=100))
    valid, reason = sl.validate({"key": "x" * 100})
    assert valid is False
    assert "payload_too_large" in reason


def test_size_limiter_too_many_fields():
    sl = MessageSizeLimiter(RateLimitConfig(max_payload_bytes=100000, max_payload_fields=5))
    payload = {f"field_{i}": i for i in range(20)}
    valid, reason = sl.validate(payload)
    assert valid is False
    assert "too_many_fields" in reason
