"""Modelos Pydantic para UC-273 — Seguridad Multi-Agente.

Cubre las 7 capas de seguridad:
1. Identidad criptográfica (Ed25519 + JWT)
2. Trust scoring bayesiano
3. Rate limiting
4. Detección de spoofing/anomalías
5. Detección de colusión
6. Ledger inmutable (audit trail)
7. Guardrails integrados (injection, DLP, BOLA, egress, agent identity)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class AgentRole(str, Enum):
    trader = "trader"
    market_maker = "market_maker"
    oracle = "oracle"
    validator = "validator"
    monitor = "monitor"
    planner = "planner"


class SecuritySeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"
    emergency = "emergency"


class AlertType(str, Enum):
    auth_failure = "auth_failure"
    replay_attack = "replay_attack"
    rate_limit = "rate_limit"
    payload_oversize = "payload_oversize"
    spoofing = "spoofing"
    collusion = "collusion"
    quarantine = "quarantine"
    trust_decay = "trust_decay"
    injection = "injection"
    dlp_redaction = "dlp_redaction"
    bola_denied = "bola_denied"
    egress_denied = "egress_denied"
    identity_denied = "identity_denied"


class VerificationStatus(str, Enum):
    ok = "ok"
    unknown_agent = "unknown_agent"
    revoked_identity = "revoked_identity"
    replay_attack = "replay_attack"
    stale_message = "stale_message"
    payload_tampered = "payload_tampered"
    invalid_signature = "invalid_signature"


# ============================================================
# Identity
# ============================================================

class AgentIdentityModel(BaseModel):
    """Identidad criptográfica de un agente."""
    agent_id: str
    public_key_hex: str
    role: AgentRole
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    is_revoked: bool = False


class IdentityRegistration(BaseModel):
    """Request para registrar un agente."""
    agent_id: str
    role: AgentRole


class IdentityResponse(BaseModel):
    """Response al registrar un agente."""
    agent_id: str
    public_key_hex: str
    role: AgentRole
    registered: bool = True


# ============================================================
# Trust
# ============================================================

class TrustScoreModel(BaseModel):
    """Trust score bayesiano de un agente."""
    agent_id: str
    alpha: float = 1.0
    beta: float = 1.0
    trust: float = 0.5
    uncertainty: float = 0.0
    lower_bound: float = 0.0
    is_quarantined: bool = False


class TrustEvent(BaseModel):
    """Evento de actualización de trust."""
    agent_id: str
    success: bool
    weight: float = 1.0
    new_trust: float = 0.0


# ============================================================
# Security Events
# ============================================================

class SecurityEvent(BaseModel):
    """Evento de seguridad consolidado."""
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    severity: SecuritySeverity
    alert_type: AlertType
    agent_id: str
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    action_taken: str = ""


# ============================================================
# Ledger
# ============================================================

class LedgerEntryModel(BaseModel):
    """Entrada del ledger inmutable de auditoría."""
    index: int
    timestamp: datetime
    agent_id: str
    event_type: str
    event_data: Dict[str, Any]
    previous_hash: str
    entry_hash: str


class LedgerVerification(BaseModel):
    """Resultado de verificación de la cadena de auditoría."""
    valid: bool
    chain_length: int
    broken_at_index: Optional[int] = None


# ============================================================
# Guardrails (atlas-demo integration)
# ============================================================

class InjectionScanResult(BaseModel):
    """Resultado de escaneo de inyección de prompt."""
    blocked: bool
    label: str
    detail: str
    patterns_matched: int = 0


class DLPRedactionResult(BaseModel):
    """Resultado de redacción DLP."""
    original_length: int
    redacted_length: int
    pii_found: List[str] = Field(default_factory=list)
    redacted_text: str = ""


class BOLACheckResult(BaseModel):
    """Resultado de verificación BOLA."""
    authorized: bool
    principal: str
    resource_owner: str


class AgentTokenVerification(BaseModel):
    """Resultado de verificación de token JWT de agente."""
    valid: bool
    label: str
    detail: str
    algorithm: Optional[str] = None
    key_id: Optional[str] = None
    issuer: Optional[str] = None
    subject: Optional[str] = None
    audience: Optional[str] = None


# ============================================================
# Anomaly Detection
# ============================================================

class AnomalyAlert(BaseModel):
    """Alerta de anomalía detectada."""
    alert_id: UUID = Field(default_factory=uuid4)
    alert_type: str
    agent_id: str
    severity: float = Field(ge=0.0, le=1.0)
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# API Responses
# ============================================================

class SecurityAssessment(BaseModel):
    """Evaluación de seguridad completa de un mensaje/agente."""
    assessment_id: UUID = Field(default_factory=uuid4)
    agent_id: str
    layers_passed: List[str] = Field(default_factory=list)
    layers_failed: List[str] = Field(default_factory=list)
    overall_verdict: Literal["allowed", "blocked", "quarantined"]
    trust_score: float = 0.0
    events: List[SecurityEvent] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MonitorStatus(BaseModel):
    """Estado del SecurityMonitor."""
    registered_agents: int = 0
    quarantined_agents: int = 0
    total_events: int = 0
    ledger_entries: int = 0
    ledger_valid: bool = True
    trusted_agents: List[str] = Field(default_factory=list)
    suspicious_agents: List[Dict[str, Any]] = Field(default_factory=list)
