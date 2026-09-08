"""
UC-300 — Modelos de datos para Secure Tool Gateway.

Define enumeraciones, configuración, solicitudes de herramienta,
decisiones de autorización, tokens de capacidad, resultados de ejecución
y entradas de auditoría.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolAction(str, Enum):
    """Acciones soportadas por el gateway."""
    UPDATE_PRICE = "update_price"
    DELETE_PRODUCT = "delete_product"
    SEND_PAYMENT = "send_payment"
    READ_FILE = "read_file"


class RiskLevel(str, Enum):
    """Nivel de riesgo de una acción."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthorizationVerdict(str, Enum):
    """Veredicto de autorización."""
    ALLOWED = "allowed"
    DENIED_SCHEMA = "denied_schema"
    DENIED_INJECTION = "denied_injection"
    DENIED_POLICY = "denied_policy"
    DENIED_QUOTA = "denied_quota"
    DENIED_RISK = "denied_risk"
    PENDING_APPROVAL = "pending_approval"
    DENIED_TOKEN = "denied_token"
    DENIED_TOCTOU = "denied_toctou"
    DENIED_OUTPUT = "denied_output"
    KILLED = "killed"


class ExecutionStatus(str, Enum):
    """Estado de ejecución."""
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    DRY_RUN = "dry_run"
    ESCALATED = "escalated"


@dataclass
class GatewayConfig:
    """Configuración del Secure Tool Gateway."""
    # Seguridad
    token_ttl_seconds: float = 300.0
    token_secret: Optional[str] = None  # Si no se provee, se genera internamente
    require_hitl_for_high: bool = True
    require_hitl_for_critical: bool = True
    max_request_age_seconds: float = 60.0

    # Cuotas
    rate_limit_per_minute: int = 60
    budget_daily: float = 100000.0
    idempotency_ttl_seconds: float = 3600.0

    # Auditoría
    audit_hash_algorithm: str = "sha256"

    # Scopes por defecto
    default_agent_scopes: Dict[str, List[str]] = field(default_factory=dict)

    # Kill switch
    kill_switch_enabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_ttl_seconds": self.token_ttl_seconds,
            "require_hitl_for_high": self.require_hitl_for_high,
            "require_hitl_for_critical": self.require_hitl_for_critical,
            "max_request_age_seconds": self.max_request_age_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "budget_daily": self.budget_daily,
            "idempotency_ttl_seconds": self.idempotency_ttl_seconds,
            "audit_hash_algorithm": self.audit_hash_algorithm,
            "default_agent_scopes": self.default_agent_scopes,
            "kill_switch_enabled": self.kill_switch_enabled,
        }


@dataclass
class ToolRequest:
    """Solicitud de ejecución de herramienta."""
    trace_id: str = ""
    agent_id: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    environment: str = "default"
    dossier_id: str = ""
    dossier_hash: str = ""
    dossier_status: str = ""  # approved | rejected | pending | auto_executed
    reviewer_id: str = ""
    approval_action_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def canonicalize_params(self) -> str:
        """JSON canónico ordenado para hashing determinista."""
        return json.dumps(self.params, sort_keys=True, separators=(",", ":"), default=str)

    def compute_action_hash(self) -> str:
        """Hash SHA-256 de los parámetros canónicos (independiente del expediente)."""
        payload = json.dumps({
            "agent_id": self.agent_id,
            "action": self.action,
            "params": self.canonicalize_params(),
            "environment": self.environment,
        }, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "params": self.params,
            "environment": self.environment,
            "dossier_id": self.dossier_id,
            "dossier_hash": self.dossier_hash,
            "dossier_status": self.dossier_status,
            "reviewer_id": self.reviewer_id,
            "approval_action_hash": self.approval_action_hash,
            "timestamp": self.timestamp,
        }


@dataclass
class AuthorizationDecision:
    """Resultado de la fase de autorización."""
    verdict: AuthorizationVerdict = AuthorizationVerdict.DENIED_POLICY
    reason: str = ""
    trace_id: str = ""
    action_hash: str = ""
    dossier_hash: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    requires_hitl: bool = False
    capability_token: Optional[str] = None
    token_expires_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value if isinstance(self.verdict, AuthorizationVerdict) else self.verdict,
            "reason": self.reason,
            "trace_id": self.trace_id,
            "action_hash": self.action_hash,
            "dossier_hash": self.dossier_hash,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "requires_hitl": self.requires_hitl,
            "capability_token": self.capability_token,
            "token_expires_at": self.token_expires_at,
        }


@dataclass
class CapabilityTokenPayload:
    """Contenido deserializado de un capability token."""
    action_hash: str = ""
    dossier_hash: str = ""
    agent_id: str = ""
    action: str = ""
    nonce: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0
    scopes: List[str] = field(default_factory=list)
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_hash": self.action_hash,
            "dossier_hash": self.dossier_hash,
            "agent_id": self.agent_id,
            "action": self.action,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "scopes": self.scopes,
            "signature": self.signature,
        }


@dataclass
class ExecutionResult:
    """Resultado de ejecución de una herramienta."""
    status: ExecutionStatus = ExecutionStatus.FAILURE
    action: str = ""
    agent_id: str = ""
    trace_id: str = ""
    output: Any = None
    error: str = ""
    dry_run: bool = False
    output_valid: bool = False
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value if isinstance(self.status, ExecutionStatus) else self.status,
            "action": self.action,
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
            "output": self.output,
            "error": self.error,
            "dry_run": self.dry_run,
            "output_valid": self.output_valid,
            "duration_ms": self.duration_ms,
        }


@dataclass
class PipelineResult:
    """Resultado completo del pipeline authorize → execute."""
    trace_id: str = ""
    authorized: bool = False
    executed: bool = False
    verdict: str = ""
    reason: str = ""
    authorization: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    audit_entry_id: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "authorized": self.authorized,
            "executed": self.executed,
            "verdict": self.verdict,
            "reason": self.reason,
            "authorization": self.authorization,
            "execution": self.execution,
            "audit_entry_id": self.audit_entry_id,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AuditEntry:
    """Entrada inmutable de auditoría."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    timestamp: float = field(default_factory=time.time)
    actor: str = ""  # agent_id o reviewer_id
    event: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    content_hash: str = ""

    def compute_hash(self) -> str:
        payload = json.dumps({
            "entry_id": self.entry_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "event": self.event,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }, sort_keys=True, separators=(",", ":"), default=str)
        self.content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.content_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "event": self.event,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "content_hash": self.content_hash,
        }


def generate_id() -> str:
    """Genera un UUID único."""
    return str(uuid.uuid4())
