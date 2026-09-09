"""Agentes de privacidad en inferencia y auditoría WORM."""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Dict, List, Optional

from fine_tuning.privacy.models_privacy import (
    InferencePrivacyReport,
    ModelCard,
    DataSheet,
    WORMAuditEntry,
)


class InferencePrivacyAgent:
    """
    Guardrails de privacidad para inferencia:
    - Pre-vuelo: detecta intents de extracción de datos/memorias, PII en input,
      patrones de extracción por repetición.
    - Post-vuelo: escanea output por PII, secretos, secuencias sospechosas de
      memorización y alucinaciones con PII.
    """

    EXTRACTION_PATTERNS = [
        r"(?i)\b(repeat\s+(?:your|the)\s+(?:training\s+)?(?:data|prompt|instruction|context|examples|previous\s+response))\b",
        r"(?i)\b(what\s+(?:data|examples|prompts|documents|emails|records)\s+(?:did\s+you\s+see|were\s+you\s+trained\s+on|do\s+you\s+remember))\b",
        r"(?i)\b(show\s+(?:me\s+)?(?:all|the)\s+(?:email|phone|ssn|credit\s+card|password|secret))\b",
        r"(?i)\b(ignore\s+(?:previous|above|system)\s+(?:instructions|prompt|context))\b",
    ]

    SECRET_PATTERNS = [
        re.compile(r"(?i)\b(sk-[a-zA-Z0-9]{20,})\b"),
        re.compile(r"(?i)\b(pk-[a-zA-Z0-9_\-]{20,})\b"),
        re.compile(r"(?i)\b(aws_access_key_id\s*=\s*[A-Z0-9]{16,})\b"),
        re.compile(r"(?i)-----BEGIN (RSA |OPENSSH |PRIVATE )?KEY-----"),
    ]

    PII_PATTERNS = {
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    }

    def __init__(self, max_repetition: int = 3) -> None:
        self.max_repetition = max_repetition

    def preflight(self, request_id: str, prompt: str) -> InferencePrivacyReport:
        findings: List[str] = []
        extraction = any(re.search(p, prompt) for p in self.EXTRACTION_PATTERNS)
        if extraction:
            findings.append("extraction_intent_detected")
        pii_in_input = self._contains_pii(prompt)
        if pii_in_input:
            findings.append("pii_in_input")
        if self._is_repetition_attack(prompt):
            findings.append("repetition_extraction_attempt")

        blocked = bool(findings)
        requires_hitl = extraction or pii_in_input
        return InferencePrivacyReport(
            request_id=request_id,
            extraction_attempt=extraction,
            pii_in_input=pii_in_input,
            pii_in_output=False,
            secrets_in_output=False,
            blocked=blocked,
            requires_hitl=requires_hitl,
            findings=findings,
        )

    def postflight(self, request_id: str, prompt: str, output: str) -> InferencePrivacyReport:
        findings: List[str] = []
        pii_out = self._contains_pii(output)
        secrets_out = any(p.search(output) for p in self.SECRET_PATTERNS)
        if pii_out:
            findings.append("pii_in_output")
        if secrets_out:
            findings.append("secrets_in_output")
        if self._looks_like_memorization(prompt, output):
            findings.append("possible_memorization")

        blocked = bool(findings)
        return InferencePrivacyReport(
            request_id=request_id,
            extraction_attempt=False,
            pii_in_input=self._contains_pii(prompt),
            pii_in_output=pii_out,
            secrets_in_output=secrets_out,
            blocked=blocked,
            requires_hitl=blocked,
            findings=findings,
        )

    def _contains_pii(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.PII_PATTERNS.values())

    def _is_repetition_attack(self, prompt: str) -> bool:
        words = prompt.lower().split()
        if not words:
            return False
        unique = set(words)
        # High repetition with few unique words is suspicious.
        return len(words) > 5 and len(unique) <= max(1, len(words) // self.max_repetition)

    def _looks_like_memorization(self, prompt: str, output: str) -> bool:
        # If output repeats long verbatim sequences from training corpora patterns (simulated).
        # Heuristic: output contains a credit card or SSN not in prompt.
        for pattern in (self.PII_PATTERNS["ssn"], self.PII_PATTERNS["credit_card"]):
            for match in pattern.finditer(output):
                if match.group(0) not in prompt:
                    return True
        return False


class WORMAuditAgent:
    """
    Audit trail inmutable (Write-Once-Read-Many) con cadena de hashes.

    - Enmascara PII antes de escribir.
    - Mantiene Model Cards y Data Sheets.
    - Etiquetas de cumplimiento GDPR/HIPAA/CCPA/EU AI Act.
    """

    def __init__(self) -> None:
        self._log: List[WORMAuditEntry] = []
        self._previous_hash = "0" * 64
        self._pii_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b|"
            r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|"
            r"\b\d{3}-\d{2}-\d{4}\b"
        )

    def _redact_pii(self, text: str) -> str:
        return self._pii_pattern.sub("[PII-REDACTED]", text)

    def _hash_entry(self, entry: WORMAuditEntry) -> str:
        payload = f"{entry.entry_id}:{entry.event_type}:{entry.actor}:{entry.resource}:{entry.timestamp}:{self._previous_hash}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def record(
        self,
        event_type: str,
        actor: str,
        resource: str,
        action: str,
        compliance_tags: Optional[List[str]] = None,
    ) -> WORMAuditEntry:
        entry = WORMAuditEntry(
            event_type=self._redact_pii(event_type),
            actor=self._redact_pii(actor),
            resource=self._redact_pii(resource),
            action=self._redact_pii(action),
            compliance_tags=compliance_tags or [],
        )
        entry.hash_chain = self._hash_entry(entry)
        self._previous_hash = entry.hash_chain
        self._log.append(entry)
        return entry

    def generate_model_card(
        self,
        model_name: str,
        intended_use: str,
        dp_epsilon: float,
        mi_risk: str,
        privacy_controls: List[str],
        limitations: List[str],
        compliance_frameworks: List[str],
    ) -> ModelCard:
        return ModelCard(
            model_name=model_name,
            intended_use=intended_use,
            privacy_controls=privacy_controls,
            dp_epsilon=dp_epsilon,
            mi_risk=mi_risk,
            limitations=limitations,
            compliance_frameworks=compliance_frameworks,
        )

    def generate_data_sheet(
        self,
        dataset_id: str,
        source: str,
        sensitive_attributes: List[str],
        anonymization_method: str,
        retention_hours: float,
        purpose: str,
    ) -> DataSheet:
        return DataSheet(
            dataset_id=dataset_id,
            source=source,
            sensitive_attributes=sensitive_attributes,
            anonymization_method=anonymization_method,
            retention_hours=retention_hours,
            purpose=purpose,
        )

    def get_log(self) -> List[WORMAuditEntry]:
        return list(self._log)
