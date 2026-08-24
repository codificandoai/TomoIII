"""Seguridad básica: detección de prompt injection, exfiltración y redacción de PII."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

from config import SecurityConfig

logger = logging.getLogger("uc251-security")


JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"forget\s+(all\s+)?(previous\s+)?instructions",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(if\s+)?(a|an)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"disregard\s+(all\s+)?(previous\s+)?rules",
    r"override\s+(all\s+)?(previous\s+)?instructions",
    r"ignore\s+safety",
    r"bypass\s+(filters|restrictions|rules)",
    r"olvida\s+(las\s+)?(instrucciones|reglas)",
    r"olvida\s+(todas\s+)?(las\s+)?(anteriores\s+)?instrucciones",
    r"ignora\s+(las\s+)?(instrucciones|reglas)",
    r"ignora\s+(todas\s+)?(las\s+)?(anteriores\s+)?instrucciones",
    r"actúa\s+como\s+",
    r"finge\s+ser",
]

PROMPT_EXTRACTION_PATTERNS = [
    r"repeat\s+(your\s+)?(system\s+)?prompt",
    r"what\s+(are|is)\s+your\s+(system\s+)?instructions",
    r"show\s+me\s+your\s+(system\s+)?prompt",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"repite\s+tu\s+prompt",
    r"revela\s+(tu\s+)?(prompt|system prompt)",
    r"cu[aá]l\s+es\s+tu\s+prompt\s+de\s+sistema",
]

PROMPT_INJECTION_PATTERNS = [
    r"<\|.*?\|>",
    r"\{\{.*?\}\}",
    r"\$\{.*?\}",
    r"system\s+prompt",
    r"sistema\s+prompt",
]

OBFUSCATION_PATTERNS = [
    r"[^\w\s]{4,}",
    r"[A-Z]{6,}",
    r"\d{6,}",
]

PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b(\+?\d{1,3}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn_us": r"\b\d{3}-\d{2}-\d{4}\b",
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "api_key": r"\b(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16})\b",
}


@dataclass
class SecurityCheck:
    blocked: bool
    flags: List[str]
    sanitized: str


class SecurityChecker:
    """Valida consultas y redacta PII en respuestas."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.jailbreak = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]
        self.extraction = [re.compile(p, re.IGNORECASE) for p in PROMPT_EXTRACTION_PATTERNS]
        self.injection = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]
        self.obfuscation = [re.compile(p) for p in OBFUSCATION_PATTERNS]
        self.pii = {name: re.compile(pattern) for name, pattern in PII_PATTERNS.items()}

    def check(self, text: str) -> SecurityCheck:
        if not self.config.enabled:
            return SecurityCheck(blocked=False, flags=[], sanitized=text)

        flags = []
        flags.extend(self._match("jailbreak", self.jailbreak, text))
        flags.extend(self._match("prompt_extraction", self.extraction, text))
        flags.extend(self._match("prompt_injection", self.injection, text))
        flags.extend(self._match("obfuscation", self.obfuscation, text))

        blocked = len(flags) >= self.config.prompt_injection_threshold
        sanitized = self.redact_pii(text) if self.config.pii_redaction_enabled else text
        return SecurityCheck(blocked=blocked, flags=flags, sanitized=sanitized)

    @staticmethod
    def _match(category: str, patterns: List[re.Pattern], text: str) -> List[str]:
        found = []
        for p in patterns:
            if p.search(text):
                found.append(category)
                break
        return found

    def redact_pii(self, text: str) -> str:
        if not self.config.pii_redaction_enabled:
            return text
        redacted = text
        for name, regex in self.pii.items():
            redacted = regex.sub(f"[REDACTED:{name}]", redacted)
        return redacted

    def sanitize_for_logging(self, text: str) -> str:
        return self.redact_pii(text)
