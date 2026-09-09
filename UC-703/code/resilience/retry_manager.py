"""Gestor de reintentos con backoff exponencial + jitter."""
from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from resilience.error_classifier import ErrorClassifier
from resilience.models_resilience import ErrorClassification, RetryPolicy, ToolResult


class RetryManager:
    """
    Aplica políticas de reintento por tipo de error con backoff exponencial
    y jitter opcional. No invalida pasos previos.
    """

    def __init__(self, policy: Optional[RetryPolicy] = None) -> None:
        self.policy = policy or RetryPolicy()
        self.classifier = ErrorClassifier()
        self._attempt_log: List[Dict[str, Any]] = []

    def execute(
        self,
        step_id: str,
        tool_name: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> ToolResult:
        last_error = ""
        last_category = ""
        attempts = 0
        for attempt in range(1, self.policy.max_retries + 2):  # initial + retries
            attempts += 1
            start = time.time()
            try:
                output = fn(*args, **kwargs)
                return ToolResult(
                    step_id=step_id,
                    status="succeeded",
                    output=output,
                    duration_ms=(time.time() - start) * 1000,
                    attempts=attempts,
                    backend=tool_name,
                )
            except Exception as exc:  # noqa: BLE001
                classification = self.classifier.classify(exc)
                last_error = str(exc)
                last_category = classification.category
                self._attempt_log.append({
                    "step_id": step_id,
                    "attempt": attempt,
                    "category": classification.category,
                    "retryable": classification.retryable,
                    "error": last_error,
                })
                if not classification.retryable or classification.category not in self.policy.retryable_categories:
                    break
                if attempt <= self.policy.max_retries:
                    delay = self._compute_delay(attempt)
                    time.sleep(delay)
        return ToolResult(
            step_id=step_id,
            status="failed",
            error=last_error,
            error_category=last_category,
            attempts=attempts,
            backend=tool_name,
        )

    def _compute_delay(self, attempt: int) -> float:
        delay = min(
            self.policy.base_delay_seconds * (2 ** (attempt - 1)),
            self.policy.max_delay_seconds,
        )
        if self.policy.jitter:
            delay = delay * (0.5 + random.random())
        return delay

    def get_attempt_log(self) -> List[Dict[str, Any]]:
        return list(self._attempt_log)
