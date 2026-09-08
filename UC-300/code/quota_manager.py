"""
UC-300 — Gestor de cuotas: rate limit, presupuesto e idempotencia.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RateBucket:
    """Cubeta de rate limit tipo token bucket simple."""
    tokens: float = 0.0
    last_update: float = field(default_factory=time.time)


class QuotaManager:
    """Rate limit por agent, presupuesto diario e idempotencia."""

    def __init__(
        self,
        rate_limit_per_minute: int = 60,
        budget_daily: float = 100000.0,
        idempotency_ttl_seconds: float = 3600.0,
    ):
        self.rate_limit_per_minute = rate_limit_per_minute
        self.budget_daily = budget_daily
        self.idempotency_ttl_seconds = idempotency_ttl_seconds

        self._rate_buckets: Dict[str, RateBucket] = {}
        self._budget_spent_today: float = 0.0
        self._budget_day_start: float = time.time()
        self._idempotency_keys: Dict[str, float] = {}
        self._results_cache: Dict[str, Any] = {}

    def _reset_budget_if_needed(self) -> None:
        now = time.time()
        if now - self._budget_day_start >= 86400:
            self._budget_spent_today = 0.0
            self._budget_day_start = now

    def check_rate(self, agent_id: str) -> Dict[str, Any]:
        now = time.time()
        bucket = self._rate_buckets.setdefault(
            agent_id,
            RateBucket(tokens=float(self.rate_limit_per_minute), last_update=now),
        )
        elapsed = now - bucket.last_update
        bucket.tokens = min(self.rate_limit_per_minute, bucket.tokens + elapsed * (self.rate_limit_per_minute / 60.0))
        bucket.last_update = now
        if bucket.tokens < 1.0:
            return {"allowed": False, "reason": "rate limit exceeded", "retry_after_seconds": max(1.0, (1.0 - bucket.tokens) / (self.rate_limit_per_minute / 60.0))}
        return {"allowed": True, "reason": "rate ok", "remaining": int(bucket.tokens)}

    def consume_rate(self, agent_id: str) -> None:
        bucket = self._rate_buckets.get(agent_id)
        if bucket and bucket.tokens >= 1.0:
            bucket.tokens -= 1.0

    def check_budget(self, amount: float) -> Dict[str, Any]:
        self._reset_budget_if_needed()
        if amount < 0:
            return {"allowed": False, "reason": "negative amount not allowed"}
        if self._budget_spent_today + amount > self.budget_daily:
            return {
                "allowed": False,
                "reason": "daily budget exceeded",
                "spent": self._budget_spent_today,
                "limit": self.budget_daily,
            }
        return {"allowed": True, "reason": "budget ok", "remaining": self.budget_daily - self._budget_spent_today}

    def consume_budget(self, amount: float) -> None:
        self._reset_budget_if_needed()
        self._budget_spent_today += max(0.0, amount)

    def check_idempotency(self, key: str) -> Optional[Any]:
        """Devuelve el resultado cacheado si la clave ya fue usada y no expiró."""
        now = time.time()
        expires = self._idempotency_keys.get(key)
        if expires and expires > now:
            return self._results_cache.get(key)
        return None

    def register_idempotency(self, key: str, result: Any) -> None:
        self._idempotency_keys[key] = time.time() + self.idempotency_ttl_seconds
        self._results_cache[key] = result

    def cleanup(self) -> int:
        """Elimina claves de idempotencia expiradas."""
        now = time.time()
        expired = [k for k, v in self._idempotency_keys.items() if v <= now]
        for k in expired:
            del self._idempotency_keys[k]
            self._results_cache.pop(k, None)
        return len(expired)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "budget_daily": self.budget_daily,
            "budget_spent_today": self._budget_spent_today,
            "budget_remaining": self.budget_daily - self._budget_spent_today,
            "idempotency_keys_active": len(self._idempotency_keys),
            "rate_buckets_active": len(self._rate_buckets),
        }

    def reset(self) -> None:
        self._rate_buckets.clear()
        self._budget_spent_today = 0.0
        self._budget_day_start = time.time()
        self._idempotency_keys.clear()
        self._results_cache.clear()
