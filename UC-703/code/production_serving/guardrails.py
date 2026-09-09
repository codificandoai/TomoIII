"""Filtros de guardrails deterministas para serving de producción."""
from __future__ import annotations

from production_serving.models_serving import GuardrailResult


class Guardrails:
    """
    Aplica filtros básicos de PII, toxicidad y jailbreak sobre prompts y
    respuestas. Es determinista y simula un servicio de guardrails real.
    """

    PII_PATTERNS = ["SSN", "phone", "credit card", "email", "Juan Pérez", "999-999-999"]
    TOXIC_PATTERNS = ["hate", "idiot", "stupid", "kill"]
    JAILBREAK_PATTERNS = [
        "ignore previous instructions",
        "pretend you are",
        "DAN",
        "jailbreak",
    ]

    def evaluate(self, text: str) -> GuardrailResult:
        lower = text.lower()
        result = GuardrailResult()
        for p in self.PII_PATTERNS:
            if p.lower() in lower:
                result.pii_detected = True
                result.reasons.append(f"PII keyword: {p}")
        for p in self.TOXIC_PATTERNS:
            if p.lower() in lower:
                result.toxicity_detected = True
                result.reasons.append(f"Toxic keyword: {p}")
        for p in self.JAILBREAK_PATTERNS:
            if p.lower() in lower:
                result.jailbreak_detected = True
                result.reasons.append(f"Jailbreak pattern: {p}")
        result.blocked = bool(result.reasons)
        return result

    def filter(self, prompt: str, response: str) -> GuardrailResult:
        return self.evaluate(f"{prompt} {response}")
