"""Detección de intentos de evasión: jailbreak, prompt injection, ofuscación."""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from config import (
    JAILBREAK_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
    OBFUSCATION_PATTERNS,
    CONFIG,
)


@dataclass
class EvasionDetection:
    """Detección de intentos de evasión."""
    jailbreak_detected: bool
    prompt_injection_detected: bool
    obfuscation_detected: bool
    evasion_type: Optional[str]
    confidence: float
    patterns_matched: List[str] = field(default_factory=list)


class EvasionDetector:
    """Detecta intentos de evasión, jailbreaks y prompt injection."""

    def __init__(self):
        self.jailbreak_patterns = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]
        self.injection_patterns = [re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS]
        self.obfuscation_patterns = [re.compile(p) for p in OBFUSCATION_PATTERNS]

    def analyze(self, text: str) -> EvasionDetection:
        """Analiza el texto en busca de intentos de evasión."""
        if not text:
            return EvasionDetection(False, False, False, None, 0.0, [])

        patterns_matched = []

        jailbreak_detected = False
        for pattern in self.jailbreak_patterns:
            if pattern.search(text):
                jailbreak_detected = True
                patterns_matched.append(f"jailbreak:{pattern.pattern}")

        injection_detected = False
        for pattern in self.injection_patterns:
            if pattern.search(text):
                injection_detected = True
                patterns_matched.append(f"injection:{pattern.pattern}")

        obfuscation_detected = False
        for pattern in self.obfuscation_patterns:
            if pattern.search(text):
                obfuscation_detected = True
                patterns_matched.append(f"obfuscation:{pattern.pattern}")

        evasion_type = None
        if jailbreak_detected:
            evasion_type = "JAILBREAK"
        elif injection_detected:
            evasion_type = "PROMPT_INJECTION"
        elif obfuscation_detected:
            evasion_type = "OBFUSCATION"

        confidence = min(len(patterns_matched) / 5, 1.0)

        return EvasionDetection(
            jailbreak_detected=jailbreak_detected,
            prompt_injection_detected=injection_detected,
            obfuscation_detected=obfuscation_detected,
            evasion_type=evasion_type,
            confidence=round(confidence, 4),
            patterns_matched=patterns_matched,
        )
