"""
UC-300 — Pre-Intent Gate determinista.

Filtro previo a UC-315 que clasifica la intención del usuario, normaliza
Unicode, valida identidad/tenant/locale/edad, aplica mandatos
deny-by-default, detecta evasión/manipulación y decide:
  ALLOW  → listo para UC-315
  BLOCK  → rechazo inmediato
  ESCALATE → envío a UC-290 para aprobación humana

No invoca UC-315 ni la red. Es completamente determinista y offline.
"""

from __future__ import annotations

import importlib
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from immutable_audit import ImmutableAuditTrail
from injection_detector import inspect_value
from intent_models import (
    IntentDecision,
    IntentRequest,
    IntentRisk,
    IntentVerdict,
    canonical_intent_hash,
)
from models_300 import GatewayConfig, generate_id
from observability_300 import ObservabilityManager


# ---------------------------------------------------------------------------
# Constantes de validación y clasificación
# ---------------------------------------------------------------------------
DEFAULT_MAX_TEXT_LENGTH = 2000
DEFAULT_MAX_REQUEST_AGE_SECONDS = 60.0
IDENTITY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
LOCALE_RE = re.compile(r"^[a-z]{2}(_[A-Z]{2})?$")
DOMAIN_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")

INTENT_CATEGORIES: List[Tuple[str, str, IntentRisk, Dict[str, Set[str]]]] = [
    # (category, requested_capability, base_risk, keyword_groups)
    (
        "pricing_read",
        "read_price",
        IntentRisk.LOW,
        {
            "domain": {"precio", "price", "pricing", "cost", "costo"},
            "action": {"ver", "consultar", "consult", "leer", "read", "get", "list", "show", "mostrar", "buscar", "search"},
        },
    ),
    (
        "pricing_update",
        "update_price",
        IntentRisk.MEDIUM,
        {
            "domain": {"precio", "price", "pricing", "cost", "costo"},
            "action": {"cambiar", "change", "modificar", "modify", "actualizar", "update", "ajustar", "adjust", "set", "fijar"},
        },
    ),
    (
        "inventory_read",
        "read_inventory",
        IntentRisk.LOW,
        {
            "domain": {"inventario", "inventory", "stock", "product", "producto", "sku"},
            "action": {"ver", "consultar", "consult", "leer", "read", "get", "list", "show", "mostrar", "buscar", "search"},
        },
    ),
    (
        "inventory_update",
        "update_inventory",
        IntentRisk.MEDIUM,
        {
            "domain": {"inventario", "inventory", "stock", "product", "producto", "sku"},
            "action": {"cambiar", "change", "modificar", "modify", "actualizar", "update", "ajustar", "adjust", "set", "fijar", "add", "añadir", "agregar"},
        },
    ),
    (
        "payment",
        "send_payment",
        IntentRisk.HIGH,
        {
            "domain": {"pago", "payment", "pay", "transfer", "transferencia", "invoice", "factura", "refund", "reembolso"},
            "action": set(),
        },
    ),
    (
        "deletion",
        "delete_product",
        IntentRisk.HIGH,
        {
            "domain": {"borrar", "delete", "remove", "eliminar", "erase"},
            "action": set(),
        },
    ),
    (
        "secrets_access",
        "secrets_access",
        IntentRisk.CRITICAL,
        {
            "domain": {"secret", "password", "contraseña", "credential", "token", "api key", "apikey", "key", "vault", "clave"},
            "action": {"ver", "consultar", "consult", "leer", "read", "get", "show", "mostrar", "access", "acceder", "dump", "exponer"},
        },
    ),
    (
        "permissions_change",
        "permissions_change",
        IntentRisk.HIGH,
        {
            "domain": {"permission", "permiso", "role", "rol", "grant", "acl", "access rights", "privilege", "privilegio"},
            "action": {"cambiar", "change", "modificar", "modify", "update", "grant", "revoke", "assign", "asignar", "elevate", "escalar"},
        },
    ),
    (
        "external_publish",
        "external_publish",
        IntentRisk.HIGH,
        {
            "domain": {"publish", "publicar", "post", "tweet", "email", "correo", "share", "compartir", "external", "externo", "send to", "enviar a"},
            "action": set(),
        },
    ),
    (
        "general_query",
        "general_query",
        IntentRisk.LOW,
        {
            "domain": {"pregunta", "question", "help", "ayuda", "explain", "explicar", "info", "información", "information", "qué", "what", "cómo", "how", "por qué", "why"},
            "action": set(),
        },
    ),
]

# Detección adicional de evasión/manipulación complementaria al injection_detector
EVASION_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(you are now|act as|ahora eres|actúa como)\b", "role_override"),
    (r"\b(ignore previous instructions|ignore all (prior |previous )?(instructions|rules)|disregard (policy|safety|security))\b", "ignore_rules"),
    (r"\b(system prompt|new system instruction|prompt leak)\b", "system_prompt_leak"),
    (r"\b(base64|decode\s*\(|\b[a-zA-Z0-9+/]{40,}={0,2}\b)", "encoding_base64"),
    (r"(%[0-9a-fA-F]{2}){4,}", "encoding_url"),
    (r"\b0x[0-9a-fA-F]{8,}\b", "encoding_hex"),
    (r"\\u[0-9a-fA-F]{4}", "encoding_unicode_escape"),
    (r"[\u200B-\u200D\uFEFF]", "zero_width_obfuscation"),
    (r"\b(exfil|exfiltrat|leak|filtrar|dump|dumpear|upload to|send data|enviar datos|smuggle)\b", "data_exfiltration"),
    (r"\b(bypass scope|all tenants|access all|override permissions|escalate privilege|become admin|superuser)\b", "scope_expansion"),
    (r"\b(disregard|olvidar|olvida|override|sobrescribir)\s+(?:rules|policies|políticas|scope|alcance)\b", "policy_override"),
]


@dataclass
class IntentMandate:
    """Mandato deny-by-default por agente/tenant/dominio/intención."""

    allowed_agents: Set[str] = field(default_factory=set)
    allowed_tenants: Set[str] = field(default_factory=set)
    allowed_domains: Set[str] = field(default_factory=set)
    # (agent_id, tenant_id, domain) -> set de intenciones permitidas
    # "" actúa como comodín.
    intent_map: Dict[Tuple[str, str, str], Set[str]] = field(default_factory=dict)
    default_allowed_intents: Set[str] = field(default_factory=set)

    def add_allowed_intents(
        self,
        intents: List[str],
        agent_id: str = "",
        tenant_id: str = "",
        domain: str = "",
    ) -> None:
        key = (agent_id, tenant_id, domain)
        self.intent_map.setdefault(key, set()).update(intents)

    def allowed_intents(self, agent_id: str, tenant_id: str, domain: str) -> Set[str]:
        # Buscar regla más específica primero
        keys = [
            (agent_id, tenant_id, domain),
            (agent_id, tenant_id, ""),
            (agent_id, "", domain),
            (agent_id, "", ""),
            ("", tenant_id, domain),
            ("", tenant_id, ""),
            ("", "", domain),
            ("", "", ""),
        ]
        for key in keys:
            if key in self.intent_map:
                return set(self.intent_map[key])
        return set(self.default_allowed_intents)

    def is_agent_allowed(self, agent_id: str) -> bool:
        return not self.allowed_agents or agent_id in self.allowed_agents

    def is_tenant_allowed(self, tenant_id: str) -> bool:
        return not self.allowed_tenants or tenant_id in self.allowed_tenants

    def is_domain_allowed(self, domain: str) -> bool:
        if not domain:
            return True
        return not self.allowed_domains or domain in self.allowed_domains


class _UC309Adapter:
    """Adaptador desacoplado a UC-309 con fallback no-op/local."""

    def __init__(self):
        self._module = self._try_load()
        self._orchestrator: Any = None
        if self._module:
            try:
                # Forzar captura determinista (sin sampling aleatorio)
                self._orchestrator = self._module.ObservabilityOrchestrator(
                    privacy=self._module.PrivacyGuard(sample_rate=1.0, forced_capture=True)
                )
            except Exception:
                self._module = None

    def _try_load(self) -> Any:
        try:
            base = Path(__file__).resolve().parent.parent.parent
            uc309_path = base / "UC-309" / "code"
            if uc309_path.exists() and str(uc309_path) not in sys.path:
                sys.path.insert(0, str(uc309_path))
            # Importar de forma explícita y no transitiva
            observability_module = importlib.import_module("observability_orchestrator")
            return observability_module
        except Exception:
            return None

    def emit(self, event_dict: Dict[str, Any]) -> Optional[Any]:
        if self._orchestrator is None:
            return None
        try:
            # Convertir a CanonicalEvent si es posible para mantener el contrato
            models_309 = importlib.import_module("models_309")
            event = models_309.CanonicalEvent.from_dict(event_dict)
            return self._orchestrator.emit(event)
        except Exception:
            return None

    def available(self) -> bool:
        return self._orchestrator is not None


class PreIntentGate:
    """Filtro determinista de intenciones de usuario."""

    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        mandate: Optional[IntentMandate] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.config = config or GatewayConfig()
        self.max_text_length = getattr(self.config, "max_text_length", DEFAULT_MAX_TEXT_LENGTH)
        self.max_request_age_seconds = getattr(
            self.config, "max_request_age_seconds", DEFAULT_MAX_REQUEST_AGE_SECONDS
        )
        self.mandate = mandate or IntentMandate()
        self.event_callback = event_callback

        self.audit_trail = ImmutableAuditTrail()
        self.observability = ObservabilityManager(component="uc300_pregate")
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._consumed_approvals: Set[str] = set()
        self._uc309 = _UC309Adapter()

        self._load_defaults()

    def _load_defaults(self) -> None:
        """Carga un mandato por defecto coherente con el gateway existente."""
        if self.mandate.allowed_agents or self.mandate.allowed_tenants or self.mandate.intent_map:
            return
        self.mandate.allowed_agents = {
            "agent_pricing_eu",
            "agent_pricing_us",
            "agent_reader",
            "agent_cashier",
            "agent_admin",
        }
        self.mandate.allowed_tenants = {"eu", "us", "default"}
        self.mandate.allowed_domains = {"internal.example.com", "default"}

        common_intents = {"pricing_read", "inventory_read", "general_query"}
        # EU pricing agent
        self.mandate.add_allowed_intents(
            list(common_intents | {"pricing_update", "inventory_update"}),
            agent_id="agent_pricing_eu",
            tenant_id="eu",
        )
        # US pricing agent
        self.mandate.add_allowed_intents(
            list(common_intents | {"pricing_update", "inventory_update"}),
            agent_id="agent_pricing_us",
            tenant_id="us",
        )
        # Lector solo consultas
        self.mandate.add_allowed_intents(
            list(common_intents),
            agent_id="agent_reader",
            tenant_id="default",
        )
        # Cajero puede pagos
        self.mandate.add_allowed_intents(
            list(common_intents | {"payment"}),
            agent_id="agent_cashier",
            tenant_id="default",
        )
        # Admin puede todo bajo su mandato, aunque riesgosos escalan
        self.mandate.add_allowed_intents(
            list({c for c, _, _, _ in INTENT_CATEGORIES}),
            agent_id="agent_admin",
            tenant_id="default",
        )

    # -----------------------------------------------------------------------
    # Normalización
    # -----------------------------------------------------------------------
    @staticmethod
    def normalize_text(text: str) -> str:
        """Unicode NFKC, elimina caracteres de control, colapsa espacios."""
        if not isinstance(text, str):
            text = str(text)
        # Normalización canónica de compatibilidad
        text = unicodedata.normalize("NFKC", text)
        # Eliminar caracteres de control (C0/C1)
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
        # Colapsar espacios en blanco a un único espacio
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # -----------------------------------------------------------------------
    # Validación
    # -----------------------------------------------------------------------
    def validate_request(
        self, request: IntentRequest, normalized_text: str, now: float
    ) -> Tuple[bool, str, List[str]]:
        evidence: List[str] = []
        if not normalized_text:
            evidence.append("empty_text")
            return False, "normalized text is empty", evidence
        if len(normalized_text) > self.max_text_length:
            evidence.append("size_limit")
            return False, f"text exceeds max length ({self.max_text_length})", evidence
        if not IDENTITY_RE.match(request.agent_id):
            evidence.append("invalid_agent_id")
            return False, "agent_id format invalid", evidence
        if not IDENTITY_RE.match(request.tenant_id):
            evidence.append("invalid_tenant_id")
            return False, "tenant_id format invalid", evidence
        if request.domain and not DOMAIN_RE.match(request.domain):
            evidence.append("invalid_domain")
            return False, "domain format invalid", evidence
        if not LOCALE_RE.match(request.locale):
            evidence.append("invalid_locale")
            return False, "locale format invalid", evidence
        if not self.mandate.is_agent_allowed(request.agent_id):
            evidence.append("invalid_agent")
            return False, f"agent_id '{request.agent_id}' not allowed by mandate", evidence
        if not self.mandate.is_tenant_allowed(request.tenant_id):
            evidence.append("invalid_tenant")
            return False, f"tenant_id '{request.tenant_id}' not allowed by mandate", evidence
        if not self.mandate.is_domain_allowed(request.domain):
            evidence.append("invalid_domain")
            return False, f"domain '{request.domain}' not allowed by mandate", evidence
        age = now - request.timestamp
        if age > self.max_request_age_seconds:
            evidence.append("request_age_exceeded")
            return False, f"request age {age:.2f}s exceeds limit", evidence
        return True, "", evidence

    # -----------------------------------------------------------------------
    # Clasificación determinista
    # -----------------------------------------------------------------------
    @classmethod
    def classify_intent(cls, normalized_text: str) -> Tuple[str, str, IntentRisk]:
        """Clasifica la intención según reglas deterministas de palabras clave."""
        lowered = normalized_text.lower()
        words = set(re.findall(r"[a-záéíóúñ]+", lowered))

        for category, capability, risk, groups in INTENT_CATEGORIES:
            domain_words = groups.get("domain", set())
            action_words = groups.get("action", set())
            domain_match = any(w in words for w in domain_words)
            action_match = any(w in words for w in action_words)

            if action_words and domain_words:
                if domain_match and action_match:
                    return category, capability, risk
            elif domain_words:
                if domain_match:
                    return category, capability, risk
            elif action_words:
                if action_match:
                    return category, capability, risk
        return "unknown", "unknown", IntentRisk.MEDIUM

    # -----------------------------------------------------------------------
    # Detección de evasión/manipulación
    # -----------------------------------------------------------------------
    def detect_evasion(self, normalized_text: str) -> List[Dict[str, Any]]:
        """Combina el injection_detector existente con patrones de evasión."""
        findings = inspect_value(normalized_text, "text")
        lowered = normalized_text.lower()
        for pattern, category in EVASION_PATTERNS:
            for m in re.finditer(pattern, lowered):
                findings.append({
                    "category": category,
                    "pattern": pattern,
                    "matched_text": normalized_text[m.start():m.end()],
                    "position": m.start(),
                    "path": "text",
                })
        return findings

    # -----------------------------------------------------------------------
    # Mandato y riesgo
    # -----------------------------------------------------------------------
    def evaluate_mandate(self, request: IntentRequest, category: str) -> bool:
        if not self.mandate.is_agent_allowed(request.agent_id):
            return False
        if not self.mandate.is_tenant_allowed(request.tenant_id):
            return False
        if not self.mandate.is_domain_allowed(request.domain):
            return False
        allowed = self.mandate.allowed_intents(request.agent_id, request.tenant_id, request.domain)
        return category in allowed

    @staticmethod
    def escalate_risk(base_risk: IntentRisk, findings: List[Dict[str, Any]]) -> IntentRisk:
        if any(f["category"] in ("data_exfiltration", "scope_expansion", "policy_override") for f in findings):
            return IntentRisk.CRITICAL
        if any(f["category"] in ("role_override", "ignore_rules", "system_prompt_leak", "encoding_base64") for f in findings):
            return IntentRisk.CRITICAL
        if findings:
            # Cualquier manipulación detectada sin ser específica sube a HIGH
            if base_risk in (IntentRisk.LOW, IntentRisk.MEDIUM):
                return IntentRisk.HIGH
        return base_risk

    # -----------------------------------------------------------------------
    # Aprobaciones vinculadas a hash exacto
    # -----------------------------------------------------------------------
    def approve_intent(
        self,
        intent_hash: str,
        reviewer_id: str,
        dossier_id: str = "",
        dossier_hash: str = "",
        ttl_seconds: float = 3600.0,
    ) -> bool:
        if not intent_hash or not reviewer_id:
            return False
        self._approvals[intent_hash] = {
            "reviewer_id": reviewer_id,
            "dossier_id": dossier_id,
            "dossier_hash": dossier_hash,
            "approved_at": time.time(),
            "expires_at": time.time() + ttl_seconds,
        }
        self.observability.increment("uc300_pregate_approval_recorded_total")
        self._audit(
            reviewer_id,
            "intent_approved",
            {"intent_hash": intent_hash, "dossier_id": dossier_id, "dossier_hash": dossier_hash},
        )
        return True

    def _check_approval(self, intent_hash: str) -> Optional[Dict[str, Any]]:
        approval = self._approvals.get(intent_hash)
        if not approval:
            return None
        if approval["expires_at"] < time.time():
            return None
        if intent_hash in self._consumed_approvals:
            return None
        return approval

    # -----------------------------------------------------------------------
    # Decisión principal
    # -----------------------------------------------------------------------
    def prefilter(self, request: IntentRequest) -> IntentDecision:
        now = time.time()
        normalized = self.normalize_text(request.raw_text)

        valid, reason, evidence = self.validate_request(request, normalized, now)
        request_age = now - request.timestamp

        if not valid:
            decision = IntentDecision(
                verdict=IntentVerdict.BLOCK,
                risk=IntentRisk.HIGH,
                reason=reason,
                summary=f"BLOCKED: {reason}",
                normalized_text=normalized[:200],
                evidence_refs=evidence,
                agent_id=request.agent_id,
                tenant_id=request.tenant_id,
                locale=request.locale,
                request_age_seconds=request_age,
            )
            self._record(request, decision)
            return decision

        findings = self.detect_evasion(normalized)
        category, capability, base_risk = self.classify_intent(normalized)
        risk = self.escalate_risk(base_risk, findings)

        intent_hash = canonical_intent_hash(
            normalized, request.agent_id, request.tenant_id, request.locale, request.domain, capability
        )

        # Aprobación opcional vinculada exactamente al intent_hash
        approval = self._check_approval(intent_hash)
        if not approval and request.approval_intent_hash == intent_hash:
            approval = {
                "reviewer_id": request.approval_reviewer_id,
                "dossier_id": request.approval_dossier_id,
                "dossier_hash": request.approval_dossier_hash,
                "expires_at": request.approval_expires_at,
            }
            # Si el request trae metadatos sin TTL, consideramos aprobación ya consumida/no válida
            if request.approval_expires_at and request.approval_expires_at > now:
                approval["external_approval_metadata"] = True
            else:
                approval = None

        summary = f"category={category}, capability={capability}, risk={risk.value}"
        evidence_refs = sorted({f["category"] for f in findings}) or []

        # Veredicto
        if findings and any(
            f["category"]
            in (
                "role_override",
                "ignore_rules",
                "system_prompt_leak",
                "data_exfiltration",
                "scope_expansion",
                "policy_override",
            )
            for f in findings
        ):
            verdict = IntentVerdict.BLOCK
            reason = f"evasion/manipulation detected: {evidence_refs}"
            risk = IntentRisk.CRITICAL
        elif findings:
            verdict = IntentVerdict.BLOCK
            reason = f"suspicious content detected: {evidence_refs}"
            risk = IntentRisk.CRITICAL
        elif approval:
            verdict = IntentVerdict.ALLOW
            reason = "resolved by pre-recorded approval"
            risk = IntentRisk.LOW
        elif category == "unknown":
            verdict = IntentVerdict.ESCALATE
            reason = "ambiguous intent; requires human review"
        elif not self.evaluate_mandate(request, category):
            verdict = IntentVerdict.BLOCK
            reason = f"intent '{category}' outside agent/tenant/domain mandate"
            evidence_refs.append("mandate_violation")
        elif risk == IntentRisk.LOW:
            verdict = IntentVerdict.ALLOW
            reason = "low-risk intent within mandate"
        else:
            verdict = IntentVerdict.ESCALATE
            reason = f"sensitive/high-risk intent within mandate ({risk.value})"

        escalation_payload: Optional[Dict[str, Any]] = None
        if verdict == IntentVerdict.ESCALATE:
            escalation_payload = {
                "reason": reason,
                "intent_hash": intent_hash,
                "agent_id": request.agent_id,
                "tenant_id": request.tenant_id,
                "requested_capability": capability,
                "risk": risk.value,
                "category": category,
                "request_age_seconds": request_age,
            }

        decision = IntentDecision(
            verdict=verdict,
            intent_hash=intent_hash,
            risk=risk,
            reason=reason,
            summary=summary,
            requested_capability=capability,
            category=category,
            normalized_text=normalized[:500],
            evidence_refs=evidence_refs,
            agent_id=request.agent_id,
            tenant_id=request.tenant_id,
            locale=request.locale,
            request_age_seconds=request_age,
            escalation_payload=escalation_payload,
            resolved_by_approval=approval is not None and verdict == IntentVerdict.ALLOW,
        )

        if approval and verdict == IntentVerdict.ALLOW:
            self._consumed_approvals.add(intent_hash)
            self.observability.increment("uc300_pregate_approval_consumed_total")

        self._record(request, decision)
        return decision

    # -----------------------------------------------------------------------
    # Auditoría, métricas y emisión de eventos
    # -----------------------------------------------------------------------
    def _record(self, request: IntentRequest, decision: IntentDecision) -> None:
        # Métricas
        self.observability.increment(f"uc300_pregate_{decision.verdict.value}_total")
        self.observability.increment(f"uc300_pregate_risk_{decision.risk.value}_total")
        if decision.evidence_refs:
            for ref in decision.evidence_refs:
                self.observability.increment(f"uc300_pregate_evidence_{ref}_total")

        # Trail local inmutable
        self._audit(
            request.agent_id or "anonymous",
            f"intent_{decision.verdict.value}",
            {
                "intent_hash": decision.intent_hash,
                "category": decision.category,
                "capability": decision.requested_capability,
                "risk": decision.risk.value,
                "reason": decision.reason,
                "summary": decision.summary,
                "evidence_refs": decision.evidence_refs,
                "resolved_by_approval": decision.resolved_by_approval,
                # Nunca incluir raw_text ni secretos
            },
            trace_id=request.request_id,
        )

        # Emisión desacoplada a UC-309 si está disponible
        event = self._build_canonical_event(request, decision)
        emitted = self._uc309.emit(event)
        if emitted is None:
            # Fallback: registrar el evento canónico de forma local via callback
            if self.event_callback:
                try:
                    self.event_callback(event)
                except Exception:
                    pass

    def _build_canonical_event(self, request: IntentRequest, decision: IntentDecision) -> Dict[str, Any]:
        """Evento canónico seguro: sin raw_text, secretos ni chain-of-thought."""
        trace_id = request.request_id or generate_id()
        span_id = generate_id()
        uc290 = None
        if decision.verdict == IntentVerdict.ESCALATE:
            risk_score = {
                IntentRisk.LOW: 0.25,
                IntentRisk.MEDIUM: 0.5,
                IntentRisk.HIGH: 0.75,
                IntentRisk.CRITICAL: 1.0,
            }.get(decision.risk, 0.5)
            uc290 = {
                "decision_id": "",
                "risk_score": risk_score,
                "escalation": True,
                "human_in_the_loop": True,
                "decision_reason": decision.reason,
            }
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": None,
            "agent_id": request.agent_id,
            "agent_version": "uc300-pregate",
            "step": 0,
            "event_type": "thought_summary",
            "timestamp_ns": int(time.time() * 1e9),
            "action_proposed": {
                "category": decision.category,
                "requested_capability": decision.requested_capability,
                "summary": decision.summary,
            },
            "action_proposed_hash": decision.intent_hash,
            "observation_summary": decision.summary,
            "uc290": uc290,
            "evidence_refs": decision.evidence_refs,
            "labels": {
                "verdict": decision.verdict.value,
                "risk": decision.risk.value,
                "category": decision.category,
                "locale": request.locale,
            },
            "redaction_findings": ["text_redacted"],
            "input_tokens": len(request.raw_text),
            "output_tokens": 0,
        }

    def _audit(self, actor: str, event: str, details: Dict[str, Any], trace_id: str = "") -> None:
        self.audit_trail.record(actor=actor, event=event, details=details, trace_id=trace_id)

    # -----------------------------------------------------------------------
    # Consultas de estado
    # -----------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        return {
            "config": {
                "max_text_length": self.max_text_length,
                "max_request_age_seconds": self.max_request_age_seconds,
            },
            "mandate": {
                "allowed_agents": sorted(self.mandate.allowed_agents),
                "allowed_tenants": sorted(self.mandate.allowed_tenants),
                "allowed_domains": sorted(self.mandate.allowed_domains),
                "intent_map": {
                    "|".join(k): sorted(v) for k, v in self.mandate.intent_map.items()
                },
            },
            "metrics": self.observability.metrics,
            "audit_entries": len(self.audit_trail.entries),
            "audit_chain_verified": self.audit_trail.verify_chain(),
            "approvals_recorded": len(self._approvals),
            "approvals_consumed": len(self._consumed_approvals),
            "uc309_available": self._uc309.available(),
        }

    def get_metrics(self) -> str:
        return self.observability.export_prometheus()

    def get_audit_trail(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.audit_trail.get_entries(trace_id=trace_id)

    def reset(self) -> None:
        self.audit_trail.reset()
        self.observability.reset()
        self._approvals.clear()
        self._consumed_approvals.clear()
