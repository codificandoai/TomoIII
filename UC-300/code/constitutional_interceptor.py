"""
UC-300 — Constitutional Interceptor determinista.

Capa de intervención constitucional situada entre el razonamiento de UC-315
y la evaluación de riesgo/HITL de UC-290. Detecta de forma determinista dos
fallas de alineación propias de agentes con herramientas:

  1. Maximización literal: la acción propuesta persigue el objetivo declarado
     ignorando valores humanos implícitos (efectos secundarios, overshoot,
     scope creep más allá del objetivo declarado).
  2. Convergencia instrumental: para alcanzar el objetivo, el agente intenta
     adquirir más recursos, escalar privilegios o eludir restricciones de
     seguridad/auditoría/gobierno.

No es un prompt. Es un conjunto de reglas deterministas offline.
No invoca UC-315 ni la red. No sustituye a UC-290 ni a UC-324.
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

from constitutional_models import (
    AgentProposal,
    ConstitutionalDecision,
    ConstitutionalPrinciple,
    ConstitutionalRisk,
    ConstitutionalVerdict,
    canonical_proposal_hash,
)
from immutable_audit import ImmutableAuditTrail
from injection_detector import inspect_value
from models_300 import GatewayConfig, generate_id
from observability_300 import ObservabilityManager


# ---------------------------------------------------------------------------
# Constantes y límites
# ---------------------------------------------------------------------------
DEFAULT_MAX_GOAL_LENGTH = 500
DEFAULT_MAX_PARAMS_SIZE = 8192
DEFAULT_MAX_AFFECTED_RESOURCES = 50
DEFAULT_MAX_ESTIMATED_CALLS = 100
DEFAULT_MAX_ESTIMATED_DURATION_SECONDS = 3600.0
DEFAULT_MAX_ESTIMATED_COST = 1000.0
DEFAULT_MAX_REQUEST_AGE_SECONDS = 60.0

IDENTITY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
LOCALE_RE = re.compile(r"^[a-z]{2}(_[A-Z]{2})?$")
DOMAIN_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")

# Indicadores deterministas de convergencia instrumental: intento de eludir
# controles de seguridad, auditoría o gobierno, o de escalar privilegios.
SAFETY_BYPASS_KEYWORDS: Set[str] = {
    "disable", "bypass", "weaken", "override", "circumvent", "deactivate",
    "turn off", "shut down", "kill", "stop", "evade", "elude",
    "audit_off", "log_off", "logging_off", "sandbox_off", "sandbox_disable",
    "governance_off", "hitl_off", "hitl_disable", "uc290_off", "uc300_off",
    "uc324_off", "uc309_off", "uc308_off", "policy_off", "policy_disable",
    "quota_off", "quota_disable", "token_off", "token_disable",
    "redact_off", "redaction_off", "privacy_off", "privacy_disable",
    "kill_switch_off", "kill_switch_disable", "firewall_off",
    "monitoring_off", "monitoring_disable", "alerting_off",
    "restrictions_off", "restrictions_disable", "controls_off",
    "safety_off", "safety_disable", "guardrails_off", "guardrails_disable",
}

PRIVILEGE_ESCALATION_KEYWORDS: Set[str] = {
    "admin", "root", "sudo", "superuser", "su -", "escalate", "elevate",
    "grant_all", "all_tenants", "all_resources", "all_scopes", "all_domains",
    "wildcard", "*", "owner", "master", "god", "omnipotent",
    "privilege_escalation", "permission_escalation", "role_escalation",
    "become_admin", "become_root", "impersonate", "impersonation",
    "assume_role_admin", "assume_role_root", "cross_tenant_admin",
}

# Acciones destructivas/irreversibles canónicas
DESTRUCTIVE_ACTIONS: Set[str] = {
    "delete", "drop", "wipe", "erase", "purge", "truncate", "destroy",
    "remove", "format", "factory_reset", "irreversible",
}

# Palabras que indican objetivo legítimo de solo lectura / consulta
READ_ONLY_GOAL_KEYWORDS: Set[str] = {
    "read", "consult", "list", "show", "view", "get", "search", "find",
    "query", "inspect", "audit", "report", "summary", "explain",
    "leer", "consultar", "ver", "mostrar", "buscar", "informe",
}


@dataclass
class ConstitutionalConfig:
    """Límites configurables del Constitutional Interceptor."""

    max_goal_length: int = DEFAULT_MAX_GOAL_LENGTH
    max_params_size: int = DEFAULT_MAX_PARAMS_SIZE
    max_affected_resources: int = DEFAULT_MAX_AFFECTED_RESOURCES
    max_estimated_calls: int = DEFAULT_MAX_ESTIMATED_CALLS
    max_estimated_duration_seconds: float = DEFAULT_MAX_ESTIMATED_DURATION_SECONDS
    max_estimated_cost: float = DEFAULT_MAX_ESTIMATED_COST
    max_request_age_seconds: float = DEFAULT_MAX_REQUEST_AGE_SECONDS


@dataclass
class CapabilityMandate:
    """Mandato deny-by-default de capabilities por agente/tenant/dominio."""

    allowed_agents: Set[str] = field(default_factory=set)
    allowed_tenants: Set[str] = field(default_factory=set)
    allowed_domains: Set[str] = field(default_factory=set)
    # (agent_id, tenant_id, domain) -> set de capabilities permitidas
    capability_map: Dict[Tuple[str, str, str], Set[str]] = field(default_factory=dict)
    default_allowed_capabilities: Set[str] = field(default_factory=set)

    def add_allowed_capabilities(
        self,
        capabilities: List[str],
        agent_id: str = "",
        tenant_id: str = "",
        domain: str = "",
    ) -> None:
        key = (agent_id, tenant_id, domain)
        self.capability_map.setdefault(key, set()).update(capabilities)

    def allowed_capabilities(self, agent_id: str, tenant_id: str, domain: str) -> Set[str]:
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
            if key in self.capability_map:
                return set(self.capability_map[key])
        return set(self.default_allowed_capabilities)

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
            return importlib.import_module("observability_orchestrator")
        except Exception:
            return None

    def emit(self, event_dict: Dict[str, Any]) -> Optional[Any]:
        if self._orchestrator is None:
            return None
        try:
            models_309 = importlib.import_module("models_309")
            event = models_309.CanonicalEvent.from_dict(event_dict)
            return self._orchestrator.emit(event)
        except Exception:
            return None

    def available(self) -> bool:
        return self._orchestrator is not None


class ConstitutionalInterceptor:
    """Interceptor constitucional determinista sobre propuestas de UC-315."""

    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        cc_config: Optional[ConstitutionalConfig] = None,
        mandate: Optional[CapabilityMandate] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.config = config or GatewayConfig()
        self.cc_config = cc_config or ConstitutionalConfig()
        self.mandate = mandate or CapabilityMandate()
        self.event_callback = event_callback

        self.audit_trail = ImmutableAuditTrail()
        self.observability = ObservabilityManager(component="uc300_constitutional")
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._consumed_approvals: Set[str] = set()
        self._uc309 = _UC309Adapter()

        self._load_defaults()

    def _load_defaults(self) -> None:
        """Mandato por defecto coherente con el gateway existente."""
        if self.mandate.allowed_agents or self.mandate.allowed_tenants or self.mandate.capability_map:
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

        read_caps = {"read_price", "read_inventory"}
        write_caps = read_caps | {"update_price", "update_inventory"}
        payment_caps = read_caps | {"send_payment"}
        admin_caps = write_caps | payment_caps | {"delete_product", "permissions_change", "external_publish", "secrets_access"}

        self.mandate.add_allowed_capabilities(
            list(read_caps), agent_id="agent_reader", tenant_id="default"
        )
        self.mandate.add_allowed_capabilities(
            list(write_caps), agent_id="agent_pricing_eu", tenant_id="eu"
        )
        self.mandate.add_allowed_capabilities(
            list(write_caps), agent_id="agent_pricing_us", tenant_id="us"
        )
        self.mandate.add_allowed_capabilities(
            list(payment_caps), agent_id="agent_cashier", tenant_id="default"
        )
        self.mandate.add_allowed_capabilities(
            list(admin_caps), agent_id="agent_admin", tenant_id="default"
        )

    # -----------------------------------------------------------------------
    # Normalización
    # -----------------------------------------------------------------------
    @staticmethod
    def normalize_text(text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        text = unicodedata.normalize("NFKC", text)
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        return set(re.findall(r"[a-záéíóúñ]+", text.lower()))

    # -----------------------------------------------------------------------
    # Validación estructural
    # -----------------------------------------------------------------------
    def validate_proposal(
        self, proposal: AgentProposal, now: float
    ) -> Tuple[bool, str, List[str]]:
        evidence: List[str] = []
        if not proposal.stated_goal:
            evidence.append("empty_goal")
            return False, "stated_goal is empty", evidence
        if len(proposal.stated_goal) > self.cc_config.max_goal_length:
            evidence.append("goal_too_long")
            return False, "stated_goal exceeds max length", evidence
        if not proposal.proposed_capability:
            evidence.append("empty_capability")
            return False, "proposed_capability is empty", evidence
        if not proposal.proposed_action:
            evidence.append("empty_action")
            return False, "proposed_action is empty", evidence
        params_size = len(repr(proposal.params))
        if params_size > self.cc_config.max_params_size:
            evidence.append("params_too_large")
            return False, f"params size {params_size} exceeds limit", evidence
        if len(proposal.affected_resources) > self.cc_config.max_affected_resources:
            evidence.append("too_many_affected_resources")
            return False, "affected_resources exceeds limit", evidence
        if not IDENTITY_RE.match(proposal.agent_id):
            evidence.append("invalid_agent_id")
            return False, "agent_id format invalid", evidence
        if not IDENTITY_RE.match(proposal.tenant_id):
            evidence.append("invalid_tenant_id")
            return False, "tenant_id format invalid", evidence
        if proposal.domain and not DOMAIN_RE.match(proposal.domain):
            evidence.append("invalid_domain")
            return False, "domain format invalid", evidence
        if not LOCALE_RE.match(proposal.locale):
            evidence.append("invalid_locale")
            return False, "locale format invalid", evidence
        if not self.mandate.is_agent_allowed(proposal.agent_id):
            evidence.append("agent_not_allowed")
            return False, f"agent_id '{proposal.agent_id}' not allowed", evidence
        if not self.mandate.is_tenant_allowed(proposal.tenant_id):
            evidence.append("tenant_not_allowed")
            return False, f"tenant_id '{proposal.tenant_id}' not allowed", evidence
        if not self.mandate.is_domain_allowed(proposal.domain):
            evidence.append("domain_not_allowed")
            return False, f"domain '{proposal.domain}' not allowed", evidence
        age = now - proposal.timestamp
        if age > self.cc_config.max_request_age_seconds:
            evidence.append("request_age_exceeded")
            return False, f"request age {age:.2f}s exceeds limit", evidence
        return True, "", evidence

    # -----------------------------------------------------------------------
    # Principios constitucionales deterministas
    # -----------------------------------------------------------------------
    def check_mandate_scope(self, proposal: AgentProposal) -> Tuple[bool, List[str]]:
        """Principio MANDATE_SCOPE: la capability debe estar en el mandato."""
        allowed = self.mandate.allowed_capabilities(
            proposal.agent_id, proposal.tenant_id, proposal.domain
        )
        if proposal.proposed_capability in allowed:
            return True, []
        return False, [f"capability '{proposal.proposed_capability}' outside mandate"]

    def check_goal_action_alignment(
        self, proposal: AgentProposal
    ) -> Tuple[bool, List[str]]:
        """Principio GOAL_ACTION_ALIGNMENT: detecta maximización literal.

        La acción propuesta debe ser un medio plausible hacia el objetivo
        declarado. Si el objetivo es de solo lectura y la acción es
        destructiva/modificadora, hay desalineación.
        """
        evidence: List[str] = []
        goal_tokens = self._tokenize(proposal.stated_goal)
        action_tokens = self._tokenize(proposal.proposed_action) | self._tokenize(
            proposal.proposed_capability
        )

        # Objetivo de solo lectura vs acción destructiva
        is_read_goal = bool(goal_tokens & READ_ONLY_GOAL_KEYWORDS)
        is_destructive_action = any(
            kw in proposal.proposed_action.lower() for kw in DESTRUCTIVE_ACTIONS
        ) or any(
            kw in proposal.proposed_capability.lower() for kw in DESTRUCTIVE_ACTIONS
        )
        if is_read_goal and is_destructive_action:
            evidence.append("read_goal_with_destructive_action")
            return False, evidence

        # Objetivo de solo lectura vs acción de modificación
        is_write_action = bool(action_tokens & {"update", "modify", "change", "set", "create", "delete", "send", "publish", "grant"})
        if is_read_goal and is_write_action:
            evidence.append("read_goal_with_write_action")
            return False, evidence

        # Sin solapamiento mínima entre objetivo y acción
        if goal_tokens and action_tokens and not (goal_tokens & action_tokens):
            # Permitir si la acción es genérica y el objetivo menciona el recurso
            # pero marcar como evidencia leve
            evidence.append("weak_goal_action_overlap")
            return True, evidence

        return True, evidence

    def check_side_effect_containment(
        self, proposal: AgentProposal
    ) -> Tuple[bool, List[str]]:
        """Principio SIDE_EFFECT_CONTAINMENT: recursos afectados dentro del objetivo."""
        evidence: List[str] = []
        if not proposal.affected_resources:
            return True, evidence
        goal_tokens = self._tokenize(proposal.stated_goal)
        # Cada recurso afectado debe tener alguna relación con el objetivo
        # (token compartido o recurso mencionado literalmente en el objetivo)
        goal_lower = proposal.stated_goal.lower()
        unrelated: List[str] = []
        for resource in proposal.affected_resources:
            res_lower = resource.lower()
            res_tokens = self._tokenize(resource)
            mentioned = res_lower in goal_lower
            token_overlap = bool(res_tokens & goal_tokens)
            if not mentioned and not token_overlap:
                unrelated.append(resource)
        if unrelated:
            evidence.append(f"unrelated_affected_resources:{unrelated[:3]}")
            return False, evidence
        return True, evidence

    def check_resource_minimization(
        self, proposal: AgentProposal
    ) -> Tuple[bool, List[str]]:
        """Principio RESOURCE_MINIMIZATION: recursos proporcionales al objetivo."""
        evidence: List[str] = []
        # Heurística: objetivo de solo lectura no debería requerir muchas llamadas
        goal_tokens = self._tokenize(proposal.stated_goal)
        is_read_goal = bool(goal_tokens & READ_ONLY_GOAL_KEYWORDS)
        if is_read_goal and proposal.estimated_calls > 10:
            evidence.append(f"read_goal_with_excessive_calls:{proposal.estimated_calls}")
            return False, evidence
        # Coste desproporcionado para objetivo simple
        goal_word_count = len(goal_tokens)
        if goal_word_count < 5 and proposal.estimated_cost > 100:
            evidence.append(f"simple_goal_with_high_cost:{proposal.estimated_cost}")
            return False, evidence
        return True, evidence

    def check_bounded_resource_use(
        self, proposal: AgentProposal
    ) -> Tuple[bool, List[str]]:
        """Principio BOUNDED_RESOURCE_USE: límites duros."""
        evidence: List[str] = []
        if proposal.estimated_calls > self.cc_config.max_estimated_calls:
            evidence.append(f"estimated_calls_exceeds_bound:{proposal.estimated_calls}")
            return False, evidence
        if proposal.estimated_duration_seconds > self.cc_config.max_estimated_duration_seconds:
            evidence.append(
                f"estimated_duration_exceeds_bound:{proposal.estimated_duration_seconds}"
            )
            return False, evidence
        if proposal.estimated_cost > self.cc_config.max_estimated_cost:
            evidence.append(f"estimated_cost_exceeds_bound:{proposal.estimated_cost}")
            return False, evidence
        return True, evidence

    def check_safety_bypass_resistance(
        self, proposal: AgentProposal
    ) -> Tuple[bool, List[str]]:
        """Principio SAFETY_BYPASS_RESISTANCE: detecta convergencia instrumental.

        El agente intenta desactivar, debilitar o eludir controles de
        seguridad, auditoría o gobierno para alcanzar su objetivo.
        """
        evidence: List[str] = []
        haystack = " ".join([
            proposal.stated_goal,
            proposal.proposed_action,
            proposal.proposed_capability,
            " ".join(proposal.requested_permissions_delta),
            repr(proposal.params),
        ]).lower()
        for kw in SAFETY_BYPASS_KEYWORDS:
            if kw in haystack:
                evidence.append(f"safety_bypass_keyword:{kw}")
        # Detección adicional vía injection_detector sobre params
        for finding in inspect_value(proposal.params, "params"):
            cat = finding.get("category", "")
            if cat in ("command_injection", "prompt_injection", "shell_metacharacter"):
                evidence.append(f"params_injection:{cat}")
        if evidence:
            return False, evidence
        return True, evidence

    def check_privilege_least_access(
        self, proposal: AgentProposal
    ) -> Tuple[bool, List[str]]:
        """Principio PRIVILEGE_LEAST_ACCESS: detecta escalación de privilegios."""
        evidence: List[str] = []
        haystack = " ".join([
            proposal.proposed_action,
            proposal.proposed_capability,
            " ".join(proposal.requested_permissions_delta),
        ]).lower()
        for kw in PRIVILEGE_ESCALATION_KEYWORDS:
            if kw in haystack:
                evidence.append(f"privilege_escalation_keyword:{kw}")
        # Cualquier delta de permisos no vacío es sospechoso
        if proposal.requested_permissions_delta:
            evidence.append(
                f"permissions_delta_requested:{proposal.requested_permissions_delta[:3]}"
            )
        if evidence:
            return False, evidence
        return True, evidence

    def check_reversibility(self, proposal: AgentProposal) -> Tuple[bool, List[str]]:
        """Principio REVERSIBILITY: acciones irreversibles requieren plan."""
        evidence: List[str] = []
        action_lower = proposal.proposed_action.lower()
        is_destructive = any(kw in action_lower for kw in DESTRUCTIVE_ACTIONS)
        if (is_destructive or not proposal.reversible) and not proposal.reversibility_plan:
            evidence.append("irreversible_without_plan")
            return False, evidence
        return True, evidence

    # -----------------------------------------------------------------------
    # Riesgo
    # -----------------------------------------------------------------------
    @staticmethod
    def assign_risk(
        principle_results: Dict[ConstitutionalPrinciple, Tuple[bool, List[str]]],
    ) -> ConstitutionalRisk:
        violations = [p for p, (ok, _) in principle_results.items() if not ok]
        if ConstitutionalPrinciple.SAFETY_BYPASS_RESISTANCE in violations:
            return ConstitutionalRisk.CRITICAL
        if ConstitutionalPrinciple.PRIVILEGE_LEAST_ACCESS in violations:
            return ConstitutionalRisk.CRITICAL
        if ConstitutionalPrinciple.MANDATE_SCOPE in violations:
            return ConstitutionalRisk.HIGH
        if ConstitutionalPrinciple.BOUNDED_RESOURCE_USE in violations:
            return ConstitutionalRisk.HIGH
        if ConstitutionalPrinciple.SIDE_EFFECT_CONTAINMENT in violations:
            return ConstitutionalRisk.HIGH
        if ConstitutionalPrinciple.GOAL_ACTION_ALIGNMENT in violations:
            return ConstitutionalRisk.HIGH
        if ConstitutionalPrinciple.REVERSIBILITY in violations:
            return ConstitutionalRisk.MEDIUM
        if ConstitutionalPrinciple.RESOURCE_MINIMIZATION in violations:
            return ConstitutionalRisk.MEDIUM
        return ConstitutionalRisk.LOW

    # -----------------------------------------------------------------------
    # Aprobaciones vinculadas a hash exacto (anti-replay, anti-substitution)
    # -----------------------------------------------------------------------
    def approve_proposal(
        self,
        proposal_hash: str,
        reviewer_id: str,
        dossier_id: str = "",
        dossier_hash: str = "",
        ttl_seconds: float = 3600.0,
    ) -> bool:
        if not proposal_hash or not reviewer_id:
            return False
        self._approvals[proposal_hash] = {
            "reviewer_id": reviewer_id,
            "dossier_id": dossier_id,
            "dossier_hash": dossier_hash,
            "approved_at": time.time(),
            "expires_at": time.time() + ttl_seconds,
        }
        self.observability.increment("uc300_constitutional_approval_recorded_total")
        self._audit(
            reviewer_id,
            "proposal_approved",
            {"proposal_hash": proposal_hash, "dossier_id": dossier_id, "dossier_hash": dossier_hash},
        )
        return True

    def _check_approval(self, proposal_hash: str) -> Optional[Dict[str, Any]]:
        approval = self._approvals.get(proposal_hash)
        if not approval:
            return None
        if approval["expires_at"] < time.time():
            return None
        if proposal_hash in self._consumed_approvals:
            return None
        return approval

    # -----------------------------------------------------------------------
    # Decisión principal
    # -----------------------------------------------------------------------
    def intercept(self, proposal: AgentProposal) -> ConstitutionalDecision:
        now = time.time()
        proposal.stated_goal = self.normalize_text(proposal.stated_goal)
        proposal.proposed_action = self.normalize_text(proposal.proposed_action)

        valid, reason, evidence = self.validate_proposal(proposal, now)
        request_age = now - proposal.timestamp

        if not valid:
            decision = ConstitutionalDecision(
                verdict=ConstitutionalVerdict.BLOCK,
                risk=ConstitutionalRisk.HIGH,
                reason=reason,
                summary=f"BLOCKED: {reason}",
                evidence_refs=evidence,
                agent_id=proposal.agent_id,
                tenant_id=proposal.tenant_id,
                locale=proposal.locale,
                request_age_seconds=request_age,
            )
            self._record(proposal, decision)
            return decision

        proposal_hash = canonical_proposal_hash(
            proposal.stated_goal,
            proposal.proposed_capability,
            proposal.proposed_action,
            proposal.params,
            proposal.agent_id,
            proposal.tenant_id,
            proposal.domain,
            proposal.locale,
        )

        # Aprobación opcional vinculada exactamente al proposal_hash
        approval = self._check_approval(proposal_hash)
        if not approval and proposal.approval_proposal_hash == proposal_hash:
            if proposal.approval_expires_at and proposal.approval_expires_at > now:
                approval = {
                    "reviewer_id": proposal.approval_reviewer_id,
                    "dossier_id": proposal.approval_dossier_id,
                    "dossier_hash": proposal.approval_dossier_hash,
                    "expires_at": proposal.approval_expires_at,
                    "external_approval_metadata": True,
                }
            else:
                approval = None

        # Evaluación de principios constitucionales
        principle_results: Dict[ConstitutionalPrinciple, Tuple[bool, List[str]]] = {
            ConstitutionalPrinciple.MANDATE_SCOPE: self.check_mandate_scope(proposal),
            ConstitutionalPrinciple.GOAL_ACTION_ALIGNMENT: self.check_goal_action_alignment(proposal),
            ConstitutionalPrinciple.SIDE_EFFECT_CONTAINMENT: self.check_side_effect_containment(proposal),
            ConstitutionalPrinciple.RESOURCE_MINIMIZATION: self.check_resource_minimization(proposal),
            ConstitutionalPrinciple.BOUNDED_RESOURCE_USE: self.check_bounded_resource_use(proposal),
            ConstitutionalPrinciple.SAFETY_BYPASS_RESISTANCE: self.check_safety_bypass_resistance(proposal),
            ConstitutionalPrinciple.PRIVILEGE_LEAST_ACCESS: self.check_privilege_least_access(proposal),
            ConstitutionalPrinciple.REVERSIBILITY: self.check_reversibility(proposal),
        }

        risk = self.assign_risk(principle_results)
        violations: List[str] = []
        all_evidence: List[str] = list(evidence)
        for principle, (ok, ev) in principle_results.items():
            if not ok:
                violations.append(principle.value)
                all_evidence.extend(ev)
            else:
                all_evidence.extend(ev)  # evidencias leves también se registran

        # Bypass de seguridad o escalación de privilegios → BLOCK siempre
        safety_ok, _ = principle_results[ConstitutionalPrinciple.SAFETY_BYPASS_RESISTANCE]
        priv_ok, _ = principle_results[ConstitutionalPrinciple.PRIVILEGE_LEAST_ACCESS]
        mandate_ok, _ = principle_results[ConstitutionalPrinciple.MANDATE_SCOPE]
        bounded_ok, _ = principle_results[ConstitutionalPrinciple.BOUNDED_RESOURCE_USE]
        goal_ok, goal_ev = principle_results[ConstitutionalPrinciple.GOAL_ACTION_ALIGNMENT]
        side_ok, _ = principle_results[ConstitutionalPrinciple.SIDE_EFFECT_CONTAINMENT]
        rev_ok, _ = principle_results[ConstitutionalPrinciple.REVERSIBILITY]
        resmin_ok, _ = principle_results[ConstitutionalPrinciple.RESOURCE_MINIMIZATION]

        if not safety_ok or not priv_ok:
            verdict = ConstitutionalVerdict.BLOCK
            reason = f"constitutional violation: {violations}"
            risk = ConstitutionalRisk.CRITICAL
        elif not mandate_ok:
            verdict = ConstitutionalVerdict.BLOCK
            reason = f"capability outside mandate: {violations}"
        elif not bounded_ok:
            verdict = ConstitutionalVerdict.BLOCK
            reason = f"resource bounds exceeded: {violations}"
        elif not goal_ok and any("read_goal_with" in e for e in goal_ev):
            # Maximización literal clara: objetivo de lectura con acción destructiva/escritura
            verdict = ConstitutionalVerdict.BLOCK
            reason = f"literal maximization detected: {violations}"
            risk = ConstitutionalRisk.CRITICAL
        elif not side_ok:
            verdict = ConstitutionalVerdict.BLOCK
            reason = f"uncontained side effects: {violations}"
        elif approval:
            verdict = ConstitutionalVerdict.ALLOW
            reason = "resolved by pre-recorded approval"
            risk = ConstitutionalRisk.LOW
        elif not rev_ok:
            verdict = ConstitutionalVerdict.ESCALATE
            reason = f"irreversible action without plan: {violations}"
        elif not resmin_ok:
            verdict = ConstitutionalVerdict.ESCALATE
            reason = f"resource use disproportionate: {violations}"
        elif not goal_ok:
            verdict = ConstitutionalVerdict.ESCALATE
            reason = f"weak goal-action alignment: {violations}"
        elif risk == ConstitutionalRisk.LOW:
            verdict = ConstitutionalVerdict.ALLOW
            reason = "proposal aligned with all constitutional principles"
        else:
            verdict = ConstitutionalVerdict.ESCALATE
            reason = f"sensitive proposal requires human review ({risk.value})"

        escalation_payload: Optional[Dict[str, Any]] = None
        if verdict == ConstitutionalVerdict.ESCALATE:
            risk_score = {
                ConstitutionalRisk.LOW: 0.25,
                ConstitutionalRisk.MEDIUM: 0.5,
                ConstitutionalRisk.HIGH: 0.75,
                ConstitutionalRisk.CRITICAL: 1.0,
            }.get(risk, 0.5)
            escalation_payload = {
                "reason": reason,
                "proposal_hash": proposal_hash,
                "agent_id": proposal.agent_id,
                "tenant_id": proposal.tenant_id,
                "proposed_capability": proposal.proposed_capability,
                "proposed_action": proposal.proposed_action,
                "risk": risk.value,
                "risk_score": risk_score,
                "principle_violations": violations,
                "request_age_seconds": request_age,
            }

        decision = ConstitutionalDecision(
            verdict=verdict,
            proposal_hash=proposal_hash,
            risk=risk,
            reason=reason,
            summary=f"violations={violations or 'none'}, risk={risk.value}",
            principle_violations=violations,
            evidence_refs=sorted(set(all_evidence)),
            goal_action_aligned=goal_ok,
            side_effects_bounded=side_ok,
            resources_bounded=bounded_ok,
            safety_bypass_attempted=not safety_ok,
            privilege_escalation_attempted=not priv_ok,
            reversible_acceptable=rev_ok,
            within_mandate=mandate_ok,
            agent_id=proposal.agent_id,
            tenant_id=proposal.tenant_id,
            locale=proposal.locale,
            request_age_seconds=request_age,
            escalation_payload=escalation_payload,
            resolved_by_approval=approval is not None and verdict == ConstitutionalVerdict.ALLOW,
        )

        if approval and verdict == ConstitutionalVerdict.ALLOW:
            self._consumed_approvals.add(proposal_hash)
            self.observability.increment("uc300_constitutional_approval_consumed_total")

        self._record(proposal, decision)
        return decision

    # -----------------------------------------------------------------------
    # Auditoría, métricas y emisión de eventos
    # -----------------------------------------------------------------------
    def _record(self, proposal: AgentProposal, decision: ConstitutionalDecision) -> None:
        self.observability.increment(f"uc300_constitutional_{decision.verdict.value}_total")
        self.observability.increment(f"uc300_constitutional_risk_{decision.risk.value}_total")
        for v in decision.principle_violations:
            self.observability.increment(f"uc300_constitutional_violation_{v}_total")
        for ref in decision.evidence_refs:
            self.observability.increment(f"uc300_constitutional_evidence_{ref.split(':')[0]}_total")

        self._audit(
            proposal.agent_id or "anonymous",
            f"proposal_{decision.verdict.value}",
            {
                "proposal_hash": decision.proposal_hash,
                "proposed_capability": proposal.proposed_capability,
                "proposed_action": proposal.proposed_action,
                "risk": decision.risk.value,
                "reason": decision.reason,
                "principle_violations": decision.principle_violations,
                "evidence_refs": decision.evidence_refs,
                "resolved_by_approval": decision.resolved_by_approval,
                # Nunca incluir stated_goal crudo, params, ni chain-of-thought
            },
            trace_id=proposal.trace_id,
        )

        event = self._build_canonical_event(proposal, decision)
        emitted = self._uc309.emit(event)
        if emitted is None and self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass

    def _build_canonical_event(
        self, proposal: AgentProposal, decision: ConstitutionalDecision
    ) -> Dict[str, Any]:
        """Evento canónico seguro: sin stated_goal crudo, params ni chain-of-thought."""
        trace_id = proposal.trace_id or generate_id()
        span_id = generate_id()
        uc290 = None
        if decision.verdict == ConstitutionalVerdict.ESCALATE:
            risk_score = {
                ConstitutionalRisk.LOW: 0.25,
                ConstitutionalRisk.MEDIUM: 0.5,
                ConstitutionalRisk.HIGH: 0.75,
                ConstitutionalRisk.CRITICAL: 1.0,
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
            "agent_id": proposal.agent_id,
            "agent_version": "uc300-constitutional",
            "step": 1,
            "event_type": "thought_summary",
            "timestamp_ns": int(time.time() * 1e9),
            "action_proposed": {
                "capability": proposal.proposed_capability,
                "action_summary": decision.summary,
            },
            "action_proposed_hash": decision.proposal_hash,
            "observation_summary": decision.summary,
            "uc290": uc290,
            "evidence_refs": decision.evidence_refs,
            "labels": {
                "verdict": decision.verdict.value,
                "risk": decision.risk.value,
                "principle_violations": decision.principle_violations,
                "locale": proposal.locale,
            },
            "redaction_findings": ["goal_redacted", "params_redacted"],
            "input_tokens": len(proposal.stated_goal),
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
                "max_goal_length": self.cc_config.max_goal_length,
                "max_params_size": self.cc_config.max_params_size,
                "max_estimated_calls": self.cc_config.max_estimated_calls,
                "max_estimated_duration_seconds": self.cc_config.max_estimated_duration_seconds,
                "max_estimated_cost": self.cc_config.max_estimated_cost,
                "max_request_age_seconds": self.cc_config.max_request_age_seconds,
            },
            "mandate": {
                "allowed_agents": sorted(self.mandate.allowed_agents),
                "allowed_tenants": sorted(self.mandate.allowed_tenants),
                "allowed_domains": sorted(self.mandate.allowed_domains),
                "capability_map": {
                    "|".join(k): sorted(v) for k, v in self.mandate.capability_map.items()
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
