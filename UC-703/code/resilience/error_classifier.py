"""Clasificación de errores de invocación de herramientas."""
from __future__ import annotations

from typing import Any, Optional

from resilience.models_resilience import ErrorClassification


class ErrorClassifier:
    """
    Clasifica excepciones/mensajes de error en categorías accionables.
    """

    def classify(self, exception: Optional[Exception] = None, error_message: str = "") -> ErrorClassification:
        msg = error_message.lower()
        if exception is not None:
            msg = f"{str(exception).lower()} {msg}"

        if "timeout" in msg or "timed out" in msg:
            return ErrorClassification(
                category="timeout",
                retryable=True,
                severity="medium",
                root_cause_hint="tool did not respond within deadline",
            )
        if "context" in msg and ("limit" in msg or "length" in msg):
            return ErrorClassification(
                category="context_limit",
                retryable=False,
                severity="high",
                root_cause_hint="prompt/context exceeds model token limit",
            )
        if "invalid" in msg or "schema" in msg or "validation" in msg or "malformed" in msg:
            return ErrorClassification(
                category="invalid_response",
                retryable=True,
                severity="medium",
                root_cause_hint="tool returned unexpected or malformed output",
            )
        if "auth" in msg or "unauthorized" in msg or "forbidden" in msg or "permission" in msg:
            return ErrorClassification(
                category="auth",
                retryable=False,
                severity="critical",
                root_cause_hint="authentication/authorization failure",
            )
        if "rate" in msg or "throttle" in msg:
            return ErrorClassification(
                category="rate_limit",
                retryable=True,
                severity="medium",
                root_cause_hint="rate limit exceeded",
            )
        return ErrorClassification(
            category="exception",
            retryable=True,
            severity="medium",
            root_cause_hint="tool raised exception",
        )
