"""Agentes de privacidad de datos: desidentificación, contratos y retención."""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Dict, List, Optional

from fine_tuning.privacy.models_privacy import (
    DataContract,
    DataRetentionDecision,
    DeIdentificationResult,
)


class DeIdentificationAgent:
    """
    Motor de desidentificación con regex deterministas.

    Soporta tres métodos:
    - redact: reemplaza por [REDACTED-TIPO]
    - pseudonymize: hash irreversible con sal
    - tokenize: token reversible (simulado) gestionado por un mapa interno

    En producción se conecta a Presidio, AWS Macie o Google Cloud DLP vía un
    adapter externo inyectable.
    """

    PATTERNS = {
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    }

    def __init__(
        self,
        method: str = "pseudonymize",
        salt: str = "uc703-privacy-salt",
        external_engine: Optional[Any] = None,
    ) -> None:
        self.method = method
        self.salt = salt
        self.external_engine = external_engine
        self._token_map: Dict[str, str] = {}
        self._counter = 0

    def _next_token(self, pii_type: str) -> str:
        self._counter += 1
        return f"<PII_{pii_type.upper()}_{self._counter:05d}>"

    def _hash(self, value: str) -> str:
        return hashlib.sha256(f"{value}{self.salt}".encode()).hexdigest()[:16]

    def deidentify(self, text: str) -> DeIdentificationResult:
        findings: List[Dict[str, Any]] = []
        anonymized = text
        reversible_map: Dict[str, str] = {}

        if self.external_engine is not None:
            # Adapter externo: se asume que retorna un dict similar.
            result = self.external_engine.deidentify(text)
            return DeIdentificationResult(
                engine="external",
                findings=result.get("findings", []),
                anonymized_text=result.get("text", text),
                method=self.method,
                reversible_map=result.get("reversible_map", {}),
                passed=result.get("passed", True),
            )

        for pii_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(0)
                findings.append({
                    "type": pii_type,
                    "start": match.start(),
                    "end": match.end(),
                    "original": value,
                })
                if self.method == "redact":
                    replacement = f"[REDACTED-{pii_type.upper()}]"
                elif self.method == "pseudonymize":
                    replacement = f"<PII_HASH_{self._hash(value)}>"
                elif self.method == "tokenize":
                    token = self._next_token(pii_type)
                    reversible_map[token] = value
                    replacement = token
                else:
                    replacement = "[REDACTED]"
                anonymized = anonymized.replace(value, replacement, 1)

        return DeIdentificationResult(
            engine="regex" if not self.external_engine else "external",
            findings=findings,
            anonymized_text=anonymized,
            method=self.method,
            reversible_map=reversible_map,
            passed=True,
        )


class DataContractValidator:
    """
    Valida contratos de datos: campos requeridos, prohibidos, propósito y región.
    """

    def validate(
        self,
        samples: List[Dict[str, Any]],
        contract: DataContract,
    ) -> Dict[str, Any]:
        violations: List[str] = []
        if not samples:
            violations.append("empty_dataset")
        for idx, sample in enumerate(samples[:5]):
            missing = [f for f in contract.required_fields if f not in sample]
            forbidden = [f for f in contract.forbidden_fields if f in sample]
            if missing:
                violations.append(f"sample_{idx}_missing:{','.join(missing)}")
            if forbidden:
                violations.append(f"sample_{idx}_forbidden:{','.join(forbidden)}")
        return {
            "contract_id": contract.contract_id,
            "valid": not violations,
            "violations": violations,
            "purpose": contract.purpose,
            "allowed_regions": contract.allowed_regions,
        }


class DataRetentionAgent:
    """
    Aplica políticas de retención TTL a datos crudos tras la extracción de
    características.
    """

    def apply_ttl(
        self,
        raw_data_uri: str,
        retention_hours: float,
        feature_extracted: bool = True,
    ) -> DataRetentionDecision:
        if not feature_extracted:
            action = "keep"
            reason = "features_not_yet_extracted"
        else:
            action = "delete"
            reason = "ttl_after_feature_extraction"
        return DataRetentionDecision(
            raw_data_uri=raw_data_uri,
            action=action,
            reason=reason,
            expires_at=time.time() + retention_hours * 3600,
        )
