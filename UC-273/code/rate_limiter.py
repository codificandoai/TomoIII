"""Rate limiting anti-DoS para UC-273.

Implementa:
- Token Bucket por agente: previene flooding de mensajes.
- Message Size Limiter: limita tamaño y complejidad de payloads.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Tuple

from config import RateLimitConfig, get_config


class TokenBucketRateLimiter:
    """Rate limiter por agente con token bucket."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        cfg = config or get_config().rate_limit
        self.rate = cfg.rate_per_second
        self.capacity = cfg.burst_capacity
        self._buckets: Dict[str, Dict[str, float]] = {}

    def allow(self, agent_id: str, tokens: int = 1) -> bool:
        now = time.time()
        if agent_id not in self._buckets:
            self._buckets[agent_id] = {"tokens": float(self.capacity), "last_refill": now}

        bucket = self._buckets[agent_id]
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(self.capacity, bucket["tokens"] + elapsed * self.rate)
        bucket["last_refill"] = now

        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            return True
        return False

    def get_remaining(self, agent_id: str) -> float:
        return self._buckets.get(agent_id, {}).get("tokens", float(self.capacity))


class MessageSizeLimiter:
    """Limita tamaño y complejidad de payloads para prevenir DoS."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        cfg = config or get_config().rate_limit
        self.max_payload_bytes = cfg.max_payload_bytes
        self.max_fields = cfg.max_payload_fields

    def validate(self, payload: dict) -> Tuple[bool, str]:
        serialized = json.dumps(payload).encode("utf-8")
        if len(serialized) > self.max_payload_bytes:
            return False, f"payload_too_large: {len(serialized)} bytes (max {self.max_payload_bytes})"

        field_count = self._count_fields(payload)
        if field_count > self.max_fields:
            return False, f"too_many_fields: {field_count} (max {self.max_fields})"

        return True, "ok"

    def _count_fields(self, obj: Any) -> int:
        if isinstance(obj, dict):
            return sum(1 + self._count_fields(v) for v in obj.values())
        if isinstance(obj, list):
            return sum(self._count_fields(v) for v in obj)
        return 1
