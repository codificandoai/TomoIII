"""
UC-300 — Modelos del Pre-Intent Gate.

Define enumeraciones y dataclasses serializables para la fase de
pre-filtrado de intenciones de usuario antes de UC-315.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Dict, List, Optional


class IntentVerdict(str, Enum):
    """Veredicto del Pre-Intent Gate."""

    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


class IntentRisk(str, Enum):
    """Nivel de riesgo asignado a una intención."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IntentRequest:
    """Solicitud de intención de usuario entrante al Pre-Intent Gate."""

    raw_text: str = ""
    agent_id: str = ""
    tenant_id: str = ""
    locale: str = "en"
    domain: str = ""
    request_id: str = ""
    timestamp: float = field(default_factory=time.time)
    # Metadatos opcionales de aprobación vinculados al intent_hash
    approval_intent_hash: str = ""
    approval_reviewer_id: str = ""
    approval_dossier_id: str = ""
    approval_dossier_hash: str = ""
    approval_expires_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "locale": self.locale,
            "domain": self.domain,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "approval_intent_hash": self.approval_intent_hash,
            "approval_reviewer_id": self.approval_reviewer_id,
            "approval_dossier_id": self.approval_dossier_id,
            "approval_dossier_hash": self.approval_dossier_hash,
            "approval_expires_at": self.approval_expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentRequest":
        return cls(**{k: v for k, v in data.items() if k in {f.name for f in fields(cls)}})


@dataclass
class IntentDecision:
    """Decisión determinista del Pre-Intent Gate."""

    verdict: IntentVerdict = IntentVerdict.BLOCK
    intent_hash: str = ""
    risk: IntentRisk = IntentRisk.LOW
    reason: str = ""
    summary: str = ""
    requested_capability: str = "unknown"
    category: str = "unknown"
    normalized_text: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    agent_id: str = ""
    tenant_id: str = ""
    locale: str = "en"
    request_age_seconds: float = 0.0
    escalation_payload: Optional[Dict[str, Any]] = None
    resolved_by_approval: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value if isinstance(self.verdict, IntentVerdict) else self.verdict,
            "intent_hash": self.intent_hash,
            "risk": self.risk.value if isinstance(self.risk, IntentRisk) else self.risk,
            "reason": self.reason,
            "summary": self.summary,
            "requested_capability": self.requested_capability,
            "category": self.category,
            "normalized_text": self.normalized_text,
            "evidence_refs": self.evidence_refs,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "locale": self.locale,
            "request_age_seconds": self.request_age_seconds,
            "escalation_payload": self.escalation_payload,
            "resolved_by_approval": self.resolved_by_approval,
            "timestamp": self.timestamp,
        }


def canonical_intent_hash(
    normalized_text: str,
    agent_id: str,
    tenant_id: str,
    locale: str,
    domain: str,
    requested_capability: str,
) -> str:
    """Hash canónico determinista de una intención normalizada."""
    payload = json.dumps({
        "normalized_text": normalized_text,
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "locale": locale,
        "domain": domain,
        "requested_capability": requested_capability,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
