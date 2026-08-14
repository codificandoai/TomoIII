"""Métricas de seguridad complementarias: filtración de PII, incumplimiento
de políticas, activación de guardarraíles, extracción de prompt de sistema
y acceso no autorizado / uso inseguro de herramientas.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import (
    PII_PATTERNS,
    POLICY_VIOLATION_TERMS,
    PROMPT_EXTRACTION_PATTERNS,
    UNAUTHORIZED_ACCESS_PATTERNS,
)


@dataclass
class SecurityMetrics:
    """Métricas de seguridad detectadas en una interacción."""
    pii_detected: bool
    pii_types: List[str] = field(default_factory=list)
    policy_violation: bool = False
    violated_terms: List[str] = field(default_factory=list)
    guardrail_triggered: bool = False
    guardrail_reasons: List[str] = field(default_factory=list)
    prompt_extraction_attempt: bool = False
    unauthorized_access_attempt: bool = False
    unauthorized_patterns: List[str] = field(default_factory=list)


class SecurityAnalyzer:
    """Analiza texto (prompt y/o respuesta) en busca de riesgos de seguridad."""

    def __init__(self):
        self.pii_patterns: Dict[str, re.Pattern] = {
            name: re.compile(pattern) for name, pattern in PII_PATTERNS.items()
        }
        self.policy_terms = [t.lower() for t in POLICY_VIOLATION_TERMS]
        self.extraction_patterns = [re.compile(p, re.IGNORECASE) for p in PROMPT_EXTRACTION_PATTERNS]
        self.unauthorized_patterns = [re.compile(p, re.IGNORECASE) for p in UNAUTHORIZED_ACCESS_PATTERNS]

    def analyze(
        self,
        text: str,
        toxicity_risk: Optional[str] = None,
        evasion_type: Optional[str] = None,
    ) -> SecurityMetrics:
        if not text:
            return SecurityMetrics(pii_detected=False)

        pii_types = [name for name, pattern in self.pii_patterns.items() if pattern.search(text)]

        text_lower = text.lower()
        violated_terms = [term for term in self.policy_terms if term in text_lower]

        extraction_attempt = any(p.search(text) for p in self.extraction_patterns)
        unauthorized_matches = [p.pattern for p in self.unauthorized_patterns if p.search(text)]

        guardrail_reasons = []
        if pii_types:
            guardrail_reasons.append("pii_detected")
        if violated_terms:
            guardrail_reasons.append("policy_violation")
        if extraction_attempt:
            guardrail_reasons.append("prompt_extraction_attempt")
        if unauthorized_matches:
            guardrail_reasons.append("unauthorized_access_attempt")
        if toxicity_risk in ("HIGH", "CRITICAL"):
            guardrail_reasons.append("high_toxicity")
        if evasion_type:
            guardrail_reasons.append(f"evasion_{evasion_type.lower()}")

        return SecurityMetrics(
            pii_detected=bool(pii_types),
            pii_types=pii_types,
            policy_violation=bool(violated_terms),
            violated_terms=violated_terms,
            guardrail_triggered=bool(guardrail_reasons),
            guardrail_reasons=guardrail_reasons,
            prompt_extraction_attempt=extraction_attempt,
            unauthorized_access_attempt=bool(unauthorized_matches),
            unauthorized_patterns=unauthorized_matches,
        )
