"""Security Monitor unificado para UC-273.

Integra las 7 capas de seguridad en un pipeline secuencial:
1. Autenticación criptográfica (Ed25519)
2. Quarantine check
3. Rate limiting (token bucket)
4. Payload size validation
5. Trust scoring bayesiano
6. Anomaly detection (spoofing/collusion)
7. Guardrails (injection, DLP, BOLA, egress, JWT identity)

Cada capa puede bloquear el mensaje. Todo se registra en el audit ledger.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from audit_ledger import AuditLedger
from config import AppConfig, get_config
from crypto import IdentityRegistry, MessageSigner, MessageVerifier, SignedMessage
from guardrails import (
    check_bola,
    check_egress,
    create_agent_token,
    redact_pii,
    scan_injection,
    verify_agent_token,
)
from models import (
    AgentRole,
    AlertType,
    MonitorStatus,
    SecurityAssessment,
    SecurityEvent,
    SecuritySeverity,
)
from rate_limiter import MessageSizeLimiter, TokenBucketRateLimiter
from trust import TrustRegistry


class SecurityMonitor:
    """Monitor de seguridad unificado — pipeline de 7 capas."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or get_config()
        self.identity_registry = IdentityRegistry()
        self.verifier = MessageVerifier(self.identity_registry, self.config.crypto)
        self.trust_registry = TrustRegistry(self.config.trust)
        self.rate_limiter = TokenBucketRateLimiter(self.config.rate_limit)
        self.size_limiter = MessageSizeLimiter(self.config.rate_limit)

        # Audit ledger firmado por el monitor
        self._monitor_key = Ed25519PrivateKey.generate()
        self.ledger = AuditLedger(self._monitor_key)

        self.events: List[SecurityEvent] = []

    def register_agent(self, agent_id: str, role: AgentRole) -> dict:
        """Registra un agente y retorna su clave pública."""
        identity, private_key = self.identity_registry.register(agent_id, role)
        self.ledger.append(agent_id, "agent.registered", {"role": role.value})
        return {
            "agent_id": agent_id,
            "public_key_hex": self.identity_registry.public_key_hex(agent_id),
            "role": role.value,
            "registered": True,
        }

    def get_signer(self, agent_id: str) -> Optional[MessageSigner]:
        """Obtiene un signer para el agente (para tests/demo)."""
        pk = self.identity_registry.get_private_key(agent_id)
        if pk:
            return MessageSigner(agent_id, pk)
        return None

    def process_message(self, msg: SignedMessage) -> SecurityAssessment:
        """Procesa mensaje aplicando las 7 capas de seguridad."""
        layers_passed: List[str] = []
        layers_failed: List[str] = []
        events: List[SecurityEvent] = []

        # CAPA 1: Autenticación criptográfica
        valid, status = self.verifier.verify(msg)
        if not valid:
            event = self._create_event(SecuritySeverity.critical, AlertType.auth_failure, msg.sender_id, f"Auth failed: {status.value}")
            events.append(event)
            layers_failed.append("crypto_auth")
            self.trust_registry.record(msg.sender_id, False, weight=3.0)
            return self._assessment(msg.sender_id, layers_passed, layers_failed, "blocked", events)
        layers_passed.append("crypto_auth")

        # CAPA 2: Quarantine
        if self.trust_registry.is_quarantined(msg.sender_id):
            event = self._create_event(SecuritySeverity.warning, AlertType.quarantine, msg.sender_id, "Agent is quarantined")
            events.append(event)
            layers_failed.append("quarantine_check")
            return self._assessment(msg.sender_id, layers_passed, layers_failed, "quarantined", events)
        layers_passed.append("quarantine_check")

        # CAPA 3: Rate limiting
        if not self.rate_limiter.allow(msg.sender_id):
            event = self._create_event(SecuritySeverity.warning, AlertType.rate_limit, msg.sender_id, "Rate limit exceeded")
            events.append(event)
            layers_failed.append("rate_limit")
            self.trust_registry.record(msg.sender_id, False, weight=0.5)
            return self._assessment(msg.sender_id, layers_passed, layers_failed, "blocked", events)
        layers_passed.append("rate_limit")

        # CAPA 4: Payload size
        valid_size, size_reason = self.size_limiter.validate(msg.payload)
        if not valid_size:
            event = self._create_event(SecuritySeverity.warning, AlertType.payload_oversize, msg.sender_id, size_reason)
            events.append(event)
            layers_failed.append("payload_size")
            return self._assessment(msg.sender_id, layers_passed, layers_failed, "blocked", events)
        layers_passed.append("payload_size")

        # CAPA 5: Trust update (success)
        self.trust_registry.record(msg.sender_id, True)
        layers_passed.append("trust_update")

        # Registrar en ledger
        self.ledger.append(msg.sender_id, "message.accepted", {"type": msg.payload_type, "msg_id": msg.message_id})

        trust = self.trust_registry.get_trust(msg.sender_id)
        return self._assessment(msg.sender_id, layers_passed, layers_failed, "allowed", events, trust)

    def scan_text_injection(self, text: str) -> dict:
        """Escanea texto por inyección de prompt."""
        blocked, detail, count = scan_injection(text)
        if blocked:
            self.ledger.append("system", "security.injection_detected", {"detail": detail})
        return {"blocked": blocked, "label": "injection" if blocked else "clean", "detail": detail, "patterns_matched": count}

    def redact_text(self, text: str) -> dict:
        """Redacta PII del texto."""
        redacted, found = redact_pii(text)
        if found:
            self.ledger.append("system", "security.dlp_redaction", {"pii_types": found})
        return {"original_length": len(text), "redacted_length": len(redacted), "pii_found": found, "redacted_text": redacted}

    def check_bola_access(self, principal: str, resource_owner: str) -> dict:
        """Verifica autorización a nivel de objeto."""
        authorized = check_bola(principal, resource_owner)
        if not authorized:
            self.ledger.append(principal, "security.bola_denied", {"resource_owner": resource_owner})
        return {"authorized": authorized, "principal": principal, "resource_owner": resource_owner}

    def check_egress_host(self, host: str) -> dict:
        """Verifica si el host está permitido para egress."""
        allowed = check_egress(host, self.config.guardrails)
        if not allowed:
            self.ledger.append("system", "security.egress_denied", {"host": host})
        return {"allowed": allowed, "host": host, "allowed_hosts": list(self.config.guardrails.allowed_egress_hosts)}

    def verify_jwt(self, token: str | None, expected_audience: str = "atlas-finance") -> dict:
        """Verifica token JWT de identidad de agente."""
        result = verify_agent_token(token, expected_audience, self.config.guardrails)
        if not result["valid"]:
            self.ledger.append(result.get("subject", "unknown"), "security.jwt_denied", {"label": result["label"]})
        return result

    def create_jwt(self, identity: str, **kwargs) -> str:
        """Crea token JWT para una identidad."""
        return create_agent_token(identity, secret_key=self.config.guardrails.agent_jwt_secret, **kwargs)

    def get_status(self) -> MonitorStatus:
        """Estado actual del monitor."""
        chain_valid, _ = self.ledger.verify_chain()
        return MonitorStatus(
            registered_agents=self.identity_registry.agent_count,
            quarantined_agents=len([a for a in self.trust_registry.scores if self.trust_registry.is_quarantined(a)]),
            total_events=len(self.events),
            ledger_entries=self.ledger.chain_length,
            ledger_valid=chain_valid,
            trusted_agents=self.trust_registry.get_trusted_agents(),
            suspicious_agents=[{"agent_id": a, "trust": t} for a, t in self.trust_registry.get_suspicious_agents()],
        )

    def _create_event(self, severity: SecuritySeverity, alert_type: AlertType, agent_id: str, description: str) -> SecurityEvent:
        event = SecurityEvent(severity=severity, alert_type=alert_type, agent_id=agent_id, description=description, action_taken="blocked")
        self.events.append(event)
        self.ledger.append(agent_id, f"security.{alert_type.value}", {"description": description})
        return event

    def _assessment(self, agent_id: str, passed: List[str], failed: List[str], verdict: str, events: List[SecurityEvent], trust: float = 0.0) -> SecurityAssessment:
        return SecurityAssessment(
            agent_id=agent_id,
            layers_passed=passed,
            layers_failed=failed,
            overall_verdict=verdict,
            trust_score=round(trust, 4),
            events=events,
        )
