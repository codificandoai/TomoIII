"""Controles de seguridad: validación de acciones, prompt injection y PII."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from config import AgentConfig
from models import AgentAction, SafetyCheck

logger = logging.getLogger("uc258-safety")

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"forget\s+(all\s+)?(previous\s+)?instructions",
    r"disregard\s+(all\s+)?(previous\s+)?rules",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(if\s+)?(a|an)\s+",
    r"system\s+prompt",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
]

PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
}

IRREVERSIBLE_ACTIONS = {"book_flight", "book_hotel", "execute_trade", "confirm_payment"}


class SafetyGuard:
    """Valida entradas, acciones y datos sensibles."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.injection_regex = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]
        self.pii_regex = {k: re.compile(v) for k, v in PII_PATTERNS.items()}

    def check_input(self, text: str) -> SafetyCheck:
        if not self.config.enable_prompt_injection_check:
            return SafetyCheck(allowed=True, sanitized_input=text)
        flags = []
        for r in self.injection_regex:
            if r.search(text):
                flags.append("prompt_injection")
                break
        sanitized = self.redact_pii(text) if self.config.enable_pii_redaction else text
        return SafetyCheck(
            allowed=len(flags) == 0,
            flags=flags,
            sanitized_input=sanitized,
        )

    def check_action(
        self, action: AgentAction, user_confirmed: bool = False
    ) -> SafetyCheck:
        flags = []
        if action.name in IRREVERSIBLE_ACTIONS and self.config.require_confirmation_irreversible and not user_confirmed:
            flags.append("requires_confirmation")
        allowed = len(flags) == 0
        return SafetyCheck(allowed=allowed, flags=flags, sanitized_input="")

    def redact_pii(self, text: str) -> str:
        redacted = text
        for name, regex in self.pii_regex.items():
            redacted = regex.sub(f"[REDACTED:{name}]", redacted)
        return redacted
