"""
UC-328 — Privacidad y Cumplimiento Normativo para ORQUESTA-R.

Detecta datos sensibles (PII simple), aplica políticas de anonimización,
pseudonimización y control de acceso, y audita decisiones de exclusión.
"""

from typing import List, Dict, Any, Optional
import re
import hashlib
import time

from orquesta_models import Source, PrivacyPolicy


class PrivacyComplianceManager:
    """
    Gestiona privacidad y cumplimiento normativo para datos y fuentes.

    Funciones:
    - Detectar PII/PHI básico (emails, teléfonos, SSN simples).
    - Aplicar políticas de anonimización/pseudonimización.
    - Filtrar fuentes según regulación regional.
    - Auditar violaciones bloqueadas.
    """

    def __init__(self, active_policies: Optional[List[PrivacyPolicy]] = None):
        self.active_policies = active_policies or [PrivacyPolicy.GDPR]
        self._audit_log: List[Dict[str, Any]] = []

    def detect_sensitive(self, text: str) -> List[Dict[str, Any]]:
        """
        Detecta patrones básicos de PII en texto.

        No reemplaza a un NER completo; es un stub defensivo.
        """
        findings = []
        patterns = {
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        }
        for label, pattern in patterns.items():
            for match in pattern.finditer(text):
                findings.append({
                    "type": label,
                    "start": match.start(),
                    "end": match.end(),
                    "value": match.group(),
                })
        return findings

    def apply_policy(
        self,
        text: str,
        policy: PrivacyPolicy,
        salt: Optional[str] = None,
    ) -> str:
        """
        Aplica una política de privacidad a un texto.

        - GDPR: hash simple con sal rotativa.
        - HIPAA: tokenización reversible (simulada con cifrado XOR simple).
        - CCPA: reemplazo por token irreversible.
        """
        if policy == PrivacyPolicy.NONE:
            return text

        findings = self.detect_sensitive(text)
        if not findings:
            return text

        anonymized = text
        for finding in findings:
            original = finding["value"]
            if policy == PrivacyPolicy.GDPR:
                replacement = self._hash_with_salt(original, salt or str(int(time.time() / 3600)))
            elif policy == PrivacyPolicy.HIPAA:
                replacement = self._pseudo_encrypt(original, salt or "auditor-key")
            elif policy == PrivacyPolicy.CCPA:
                replacement = f"[REDACTED-{finding['type'].upper()}]"
            else:
                replacement = "[REDACTED]"
            anonymized = anonymized.replace(original, replacement, 1)
        return anonymized

    def _hash_with_salt(self, value: str, salt: str) -> str:
        """Anonimización irreversible con sal."""
        return hashlib.sha256(f"{value}{salt}".encode()).hexdigest()[:16]

    def _pseudo_encrypt(self, value: str, key: str) -> str:
        """Pseudonimización reversible simple (XOR)."""
        encoded = []
        key_cycle = (ord(k) for k in key)
        for char in value:
            try:
                k = next(key_cycle)
            except StopIteration:
                key_cycle = (ord(k) for k in key)
                k = next(key_cycle)
            encoded.append(chr(ord(char) ^ k))
        return "PSEUDO:" + "".join(encoded)

    def filter_sources_by_policy(
        self,
        sources: List[Source],
        user_region: str,
    ) -> List[Source]:
        """
        Filtra fuentes que no cumplen con políticas activas para una región.

        Heurística: si la fuente tiene metadata `regions_blocked` y contiene
        la región del usuario, se excluye.
        """
        allowed = []
        for source in sources:
            blocked_regions = source.metadata.get("regions_blocked", [])
            if user_region in blocked_regions:
                self._log_violation(
                    action="source_excluded",
                    source_id=source.source_id,
                    reason=f"Región {user_region} bloqueada",
                )
                continue
            if source.metadata.get("requires_consent") and not source.metadata.get("consent_given"):
                self._log_violation(
                    action="source_excluded",
                    source_id=source.source_id,
                    reason="Consentimiento no otorgado",
                )
                continue
            allowed.append(source)
        return allowed

    def anonymize_record(
        self,
        record: Dict[str, Any],
        policy: PrivacyPolicy,
        salt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Anonimiza campos de texto en un registro canónico."""
        result = {}
        for k, v in record.items():
            if isinstance(v, str):
                result[k] = self.apply_policy(v, policy, salt)
            else:
                result[k] = v
        return result

    def _log_violation(
        self,
        action: str,
        source_id: str,
        reason: str,
    ) -> None:
        """Registra una violación o exclusión de privacidad."""
        self._audit_log.append({
            "timestamp": time.time(),
            "action": action,
            "source_id": source_id,
            "reason": reason,
        })

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retorna log de auditoría."""
        return self._audit_log[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de privacidad."""
        return {
            "active_policies": [p.value for p in self.active_policies],
            "violations_blocked": len(self._audit_log),
            "recent_violations": self._audit_log[-5:],
        }

    def reset(self) -> None:
        """Limpia log de auditoría."""
        self._audit_log.clear()
