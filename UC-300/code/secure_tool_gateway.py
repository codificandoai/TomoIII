"""
UC-300 — Secure Tool Gateway.

Capa defensiva entre UC-290 (decisión/approval) y UC-317 (ejecución).
Pipeline:
  request → canonicalize → schema → injection → policy → quota/idempotency
  → risk/HITL → token → execute → TOCTOU revalidate → sandbox → output validation
  → immutable audit.

No expone el executor directamente; toda ejecución requiere:
1. authorize() → capability token.
2. execute() con token + payload canónico + TOCTOU revalidation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from capability_tokens import CapabilityTokenManager
from constitutional_interceptor import ConstitutionalInterceptor
from constitutional_models import (
    AgentProposal,
    ConstitutionalDecision,
    ConstitutionalRisk,
    ConstitutionalVerdict,
)
from credential_broker import CredentialBroker
from immutable_audit import ImmutableAuditTrail
from injection_detector import InjectionDetectionError, assert_clean
from intent_models import (
    IntentDecision,
    IntentRequest,
    IntentRisk,
    IntentVerdict,
)
from models_300 import (
    AuthorizationDecision,
    AuthorizationVerdict,
    ExecutionResult,
    ExecutionStatus,
    GatewayConfig,
    PipelineResult,
    RiskLevel,
    ToolRequest,
    generate_id,
)
from observability_300 import ObservabilityManager
from policy_engine import PolicyEngine
from pre_intent_gate import PreIntentGate
from quota_manager import QuotaManager
from sandbox_executor import SandboxExecutor
from separation_of_powers import (
    ActionPowerClassifier,
    Power,
    SeparationOfPowersRegistry,
)
from pydantic import ValidationError
from schema_registry import (
    HIGH_PAYMENT_THRESHOLD,
    REQUIRES_APPROVAL,
    RISK_BY_ACTION,
    SchemaValidationError,
    SemanticValidationError,
    canonicalize_params,
    get_schema,
    semantic_check,
)


class SecureToolGateway:
    """Gateway seguro entre decisión y ejecución."""

    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        self.policy_engine = PolicyEngine()
        self.policy_engine.load_defaults()
        self.quota_manager = QuotaManager(
            rate_limit_per_minute=self.config.rate_limit_per_minute,
            budget_daily=self.config.budget_daily,
            idempotency_ttl_seconds=self.config.idempotency_ttl_seconds,
        )
        self.capability_tokens = CapabilityTokenManager(secret=self.config.token_secret)
        self.credential_broker = CredentialBroker(default_ttl_seconds=self.config.token_ttl_seconds)
        self.sandbox_executor = SandboxExecutor()
        self.audit_trail = ImmutableAuditTrail()
        self.observability = ObservabilityManager()
        self.pre_intent_gate = PreIntentGate(config=self.config)
        self.constitutional_interceptor = ConstitutionalInterceptor(config=self.config)

        # Estado interno
        self._consumed_nonces: set = set()
        self._kill_switch = False
        self._power_registry = SeparationOfPowersRegistry()

    # -----------------------------------------------------------------------
    # Authorize phase
    # -----------------------------------------------------------------------

    def authorize(self, request: ToolRequest) -> AuthorizationDecision:
        """Autoriza una solicitud y emite un capability token si procede."""
        trace_id = request.trace_id or generate_id()
        request.trace_id = trace_id
        span = self.observability.start_span("authorize", trace_id)
        start = time.time()
        reason = ""

        # Kill switch
        if self._kill_switch:
            reason = "kill switch enabled: gateway offline"
            self._audit("system", "authorize_blocked", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_authorize_killed_total")
            return self._denied(AuthorizationVerdict.KILLED, reason, request)

        # 0. Separation of powers: no single agent can propose, authorize,
        #    execute and rewrite its own controls.
        conflict = self._check_power_separation(request.agent_id, request.action)
        if conflict:
            reason = f"separation of powers violated: {conflict}"
            self._audit(request.agent_id, "powers_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_powers_denied_total")
            return self._denied(AuthorizationVerdict.DENIED_POLICY, reason, request)

        # 1. Canonicalize + Schema validation
        try:
            canonical_json = self._validate_schema(request)
        except SchemaValidationError as exc:
            reason = f"schema validation failed: {exc}"
            self._audit(request.agent_id, "schema_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_schema_denied_total")
            return self._denied(AuthorizationVerdict.DENIED_SCHEMA, reason, request)

        # 2. Injection detection
        try:
            assert_clean(request.agent_id, request.action, request.params)
        except InjectionDetectionError as exc:
            reason = f"injection detected: {exc}"
            self._audit(request.agent_id, "injection_denied", {"trace_id": trace_id, "reason": reason, "findings": exc.matched})
            self.observability.increment("uc300_injection_denied_total")
            return self._denied(AuthorizationVerdict.DENIED_INJECTION, reason, request)

        # 3. Policy engine (deny-by-default)
        policy_result = self.policy_engine.evaluate(
            request.agent_id,
            request.action,
            request.params,
            request.environment,
        )
        if not policy_result["allowed"]:
            reason = f"policy denied: {policy_result['reason']}"
            self._audit(request.agent_id, "policy_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_policy_denied_total")
            return self._denied(AuthorizationVerdict.DENIED_POLICY, reason, request)

        # 4. Quota / idempotency
        rate_check = self.quota_manager.check_rate(request.agent_id)
        if not rate_check["allowed"]:
            reason = f"quota denied: {rate_check['reason']}"
            self._audit(request.agent_id, "quota_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_quota_denied_total")
            return self._denied(AuthorizationVerdict.DENIED_QUOTA, reason, request)
        self.quota_manager.consume_rate(request.agent_id)

        if request.action == "send_payment":
            amount = float(request.params.get("amount", 0))
            budget_check = self.quota_manager.check_budget(amount)
            if not budget_check["allowed"]:
                reason = f"quota denied: {budget_check['reason']}"
                self._audit(request.agent_id, "quota_denied", {"trace_id": trace_id, "reason": reason})
                self.observability.increment("uc300_quota_denied_total")
                return self._denied(AuthorizationVerdict.DENIED_QUOTA, reason, request)
            self.quota_manager.consume_budget(amount)

        # 5. Risk / HITL
        risk_level = self._compute_risk(request)
        requires_hitl = self._requires_hitl(request, risk_level)
        action_hash = request.compute_action_hash()

        if requires_hitl:
            approved = self._verify_explicit_approval(request, action_hash)
            if not approved:
                reason = "explicit human approval required and not provided or hash mismatch"
                self._audit(request.agent_id, "hitl_pending", {
                    "trace_id": trace_id,
                    "reason": reason,
                    "dossier_id": request.dossier_id,
                })
                self.observability.increment("uc300_hitl_pending_total")
                return self._pending(request, reason, risk_level)
            # Aprobado explícito
            self._audit(request.agent_id, "hitl_approved", {
                "trace_id": trace_id,
                "dossier_id": request.dossier_id,
                "reviewer_id": request.reviewer_id,
            })

        # 6. Issue capability token bound to action+dossier hashes
        token = self.capability_tokens.issue(
            action_hash=action_hash,
            dossier_hash=request.dossier_hash or "",
            agent_id=request.agent_id,
            action=request.action,
            scopes=[request.action],
            ttl_seconds=self.config.token_ttl_seconds,
        )

        # Emitir credencial opaca temporal (opcional, para acceso a recursos)
        resource = self._extract_resource(request)
        if resource:
            self.credential_broker.issue(
                token,
                resource=resource,
                scope=request.action,
                metadata={"trace_id": trace_id},
                ttl_seconds=self.config.token_ttl_seconds,
            )

        self.observability.increment("uc300_authorize_allowed_total")
        self._audit(request.agent_id, "authorized", {
            "trace_id": trace_id,
            "action": request.action,
            "action_hash": action_hash,
            "dossier_hash": request.dossier_hash,
        })

        decision = self._allowed(request, "authorized", risk_level)
        decision.capability_token = token
        decision.action_hash = action_hash
        return decision

    # -----------------------------------------------------------------------
    # Execute phase
    # -----------------------------------------------------------------------

    def execute(self, request: ToolRequest, capability_token: str) -> ExecutionResult:
        """Ejecuta la acción tras TOCTOU revalidation y sandbox."""
        trace_id = request.trace_id or generate_id()
        request.trace_id = trace_id
        span = self.observability.start_span("execute", trace_id)
        start = time.time()

        if self._kill_switch:
            reason = "kill switch enabled: gateway offline"
            self._audit("system", "execute_blocked", {"trace_id": trace_id, "reason": reason})
            return self._execution_failure(request, reason, ExecutionStatus.BLOCKED)

        # 0. Separation of powers re-validation in execution phase.
        conflict = self._check_power_separation(request.agent_id, request.action)
        if conflict:
            reason = f"separation of powers violated: {conflict}"
            self._audit(request.agent_id, "powers_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_powers_denied_total")
            return self._execution_failure(request, reason, ExecutionStatus.BLOCKED)

        # Re-validate schema (TOCTOU primer paso)
        try:
            self._validate_schema(request)
        except SchemaValidationError as exc:
            reason = f"TOCTOU schema revalidation failed: {exc}"
            self._audit(request.agent_id, "toctou_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_toctou_denied_total")
            return self._execution_failure(request, reason, ExecutionStatus.BLOCKED)

        # TOCTOU: recompute hashes and validate token antes de consultar
        # idempotencia. Un token consumido o inválido nunca puede obtener ni
        # siquiera un resultado cacheado.
        action_hash = request.compute_action_hash()
        try:
            payload = self.capability_tokens.validate(
                token=capability_token,
                expected_action_hash=action_hash,
                expected_dossier_hash=request.dossier_hash or "",
                expected_agent_id=request.agent_id,
                expected_action=request.action,
                consumed_nonces=self._consumed_nonces,
            )
        except ValueError as exc:
            reason = f"TOCTOU token validation failed: {exc}"
            self._audit(request.agent_id, "toctou_denied", {"trace_id": trace_id, "reason": reason})
            self.observability.increment("uc300_toctou_denied_total")
            return self._execution_failure(request, reason, ExecutionStatus.BLOCKED)

        # Idempotencia solo después de autenticar y consumir correctamente el
        # capability token. Una repetición legítima requiere un token nuevo.
        idempotency_key = self._idempotency_key(request)
        cached = self.quota_manager.check_idempotency(idempotency_key)
        if cached is not None:
            self._audit(request.agent_id, "idempotency_hit", {"trace_id": trace_id, "key": idempotency_key})
            self.observability.increment("uc300_idempotency_hit_total")
            return ExecutionResult(
                status=ExecutionStatus(cached.get("status", "success")),
                action=cached.get("action", request.action),
                agent_id=cached.get("agent_id", request.agent_id),
                trace_id=cached.get("trace_id", trace_id),
                output=cached.get("output"),
                error=cached.get("error", ""),
                dry_run=cached.get("dry_run", False),
                output_valid=cached.get("output_valid", True),
                duration_ms=0.0,
            )

        # Determinar dry-run para operaciones destructivas
        dry_run = self._is_destructive(request.action)

        # Sandbox execution
        exec_result = self.sandbox_executor.execute(
            trace_id=trace_id,
            agent_id=request.agent_id,
            action=request.action,
            params=request.params,
            dry_run=dry_run,
        )

        # Output validation
        validation = self.sandbox_executor.validate_output(request.action, exec_result.output)
        exec_result.output_valid = validation["valid"]
        if not validation["valid"]:
            exec_result.status = ExecutionStatus.BLOCKED
            exec_result.error = f"output validation failed: {validation['reason']}"
            self._audit(request.agent_id, "output_denied", {"trace_id": trace_id, "reason": exec_result.error})
            self.observability.increment("uc300_output_denied_total")
            return exec_result

        # Audit success
        self._audit(request.agent_id, "executed", {
            "trace_id": trace_id,
            "action": request.action,
            "status": exec_result.status.value,
            "dry_run": dry_run,
            "action_hash": action_hash,
        })
        self.observability.increment("uc300_execute_total")
        exec_result.duration_ms = (time.time() - start) * 1000

        # Cache idempotency result
        self.quota_manager.register_idempotency(self._idempotency_key(request), exec_result.to_dict())

        self.observability.end_span(span)
        return exec_result

    # -----------------------------------------------------------------------
    # Combined pipeline (no direct bypass)
    # -----------------------------------------------------------------------

    def process(self, request: ToolRequest) -> PipelineResult:
        """Ejecuta authorize + execute de forma segura (demo/testing)."""
        start = time.time()
        auth = self.authorize(request)
        result = PipelineResult(trace_id=request.trace_id)
        result.authorization = auth.to_dict()

        if auth.verdict != AuthorizationVerdict.ALLOWED or not auth.capability_token:
            result.authorized = False
            result.verdict = auth.verdict.value
            result.reason = auth.reason
            result.duration_ms = (time.time() - start) * 1000
            self._audit(request.agent_id, "process_denied", {"trace_id": request.trace_id, "reason": auth.reason})
            return result

        result.authorized = True
        exec_result = self.execute(request, auth.capability_token)
        result.executed = exec_result.status in (ExecutionStatus.SUCCESS, ExecutionStatus.DRY_RUN)
        result.execution = exec_result.to_dict()
        result.verdict = "allowed" if result.executed else "blocked"
        result.reason = exec_result.error or "success"
        result.duration_ms = (time.time() - start) * 1000
        return result

    # -----------------------------------------------------------------------
    # Pre-Intent Gate (antes de UC-315)
    # -----------------------------------------------------------------------

    def prefilter_intent(self, intent_request: IntentRequest) -> IntentDecision:
        """Filtro determinista de intenciones de usuario antes de UC-315."""
        return self.pre_intent_gate.prefilter(intent_request)

    def process_user_request(
        self,
        intent_request: IntentRequest,
    ) -> Dict[str, Any]:
        """Pipeline usuario → PreIntentGate. Solo devuelve ready_for_uc315 si ALLOW."""
        start = time.time()
        decision = self.pre_intent_gate.prefilter(intent_request)
        return {
            "ready_for_uc315": decision.verdict == IntentVerdict.ALLOW,
            "verdict": decision.verdict.value,
            "intent_hash": decision.intent_hash,
            "risk": decision.risk.value,
            "reason": decision.reason,
            "requested_capability": decision.requested_capability,
            "decision": decision.to_dict(),
            "duration_ms": (time.time() - start) * 1000,
        }

    def approve_intent(
        self,
        intent_hash: str,
        reviewer_id: str,
        dossier_id: str = "",
        dossier_hash: str = "",
        ttl_seconds: float = 3600.0,
    ) -> bool:
        """Registra una aprobación explícita ligada al hash exacto de intención."""
        return self.pre_intent_gate.approve_intent(
            intent_hash=intent_hash,
            reviewer_id=reviewer_id,
            dossier_id=dossier_id,
            dossier_hash=dossier_hash,
            ttl_seconds=ttl_seconds,
        )

    def get_pregate_audit_trail(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.pre_intent_gate.get_audit_trail(trace_id=trace_id)

    # -----------------------------------------------------------------------
    # Constitutional Interceptor (después de UC-315, antes de UC-290)
    # -----------------------------------------------------------------------

    def intercept_proposal(self, proposal: AgentProposal) -> ConstitutionalDecision:
        """Interceptor constitucional sobre la propuesta de UC-315."""
        return self.constitutional_interceptor.intercept(proposal)

    def process_agent_proposal(
        self,
        proposal: AgentProposal,
    ) -> Dict[str, Any]:
        """Pipeline UC-315 → Constitutional Interceptor.

        Solo devuelve ready_for_uc290=true si el veredicto es ALLOW.
        """
        start = time.time()
        decision = self.constitutional_interceptor.intercept(proposal)
        return {
            "ready_for_uc290": decision.verdict == ConstitutionalVerdict.ALLOW,
            "verdict": decision.verdict.value,
            "proposal_hash": decision.proposal_hash,
            "risk": decision.risk.value,
            "reason": decision.reason,
            "proposed_capability": proposal.proposed_capability,
            "principle_violations": decision.principle_violations,
            "decision": decision.to_dict(),
            "duration_ms": (time.time() - start) * 1000,
        }

    def approve_proposal(
        self,
        proposal_hash: str,
        reviewer_id: str,
        dossier_id: str = "",
        dossier_hash: str = "",
        ttl_seconds: float = 3600.0,
    ) -> bool:
        """Registra aprobación humana ligada al hash exacto de la propuesta."""
        return self.constitutional_interceptor.approve_proposal(
            proposal_hash=proposal_hash,
            reviewer_id=reviewer_id,
            dossier_id=dossier_id,
            dossier_hash=dossier_hash,
            ttl_seconds=ttl_seconds,
        )

    def get_constitutional_audit_trail(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.constitutional_interceptor.get_audit_trail(trace_id=trace_id)

    # -----------------------------------------------------------------------
    # Human approval helpers
    # -----------------------------------------------------------------------

    def approve_request(
        self,
        request: ToolRequest,
        dossier_id: str,
        dossier_hash: str,
        reviewer_id: str,
        approval_action_hash: str,
    ) -> AuthorizationDecision:
        """Permite a un revisor proveer metadatos de aprobación y reautorizar."""
        request.dossier_id = dossier_id
        request.dossier_hash = dossier_hash
        request.dossier_status = "approved"
        request.reviewer_id = reviewer_id
        request.approval_action_hash = approval_action_hash
        return self.authorize(request)

    # -----------------------------------------------------------------------
    # Control y consultas
    # -----------------------------------------------------------------------

    def set_kill_switch(self, enabled: bool) -> None:
        self._kill_switch = enabled
        self._audit("system", "kill_switch", {"enabled": enabled})
        self.observability.log("WARN", f"kill switch set to {enabled}", extra={"enabled": enabled})

    def is_killed(self) -> bool:
        return self._kill_switch

    def get_status(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "kill_switch": self._kill_switch,
            "audit_entries": len(self.audit_trail.entries),
            "audit_chain_verified": self.audit_trail.verify_chain(),
            "policy_engine": self.policy_engine.get_summary(),
            "quota_manager": self.quota_manager.get_summary(),
            "credential_broker": self.credential_broker.get_summary(),
            "sandbox_products": self.sandbox_executor.get_state_snapshot()["products"],
            "observability": self.observability.get_summary(),
            "pre_intent_gate": self.pre_intent_gate.get_status(),
            "constitutional_interceptor": self.constitutional_interceptor.get_status(),
        }

    def get_audit_trail(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.audit_trail.get_entries(trace_id=trace_id)

    def get_metrics(self) -> str:
        return self.observability.export_prometheus()

    def reset(self, config: Optional[GatewayConfig] = None) -> None:
        if config:
            self.config = config
        self.policy_engine = PolicyEngine()
        self.policy_engine.load_defaults()
        self.quota_manager = QuotaManager(
            rate_limit_per_minute=self.config.rate_limit_per_minute,
            budget_daily=self.config.budget_daily,
            idempotency_ttl_seconds=self.config.idempotency_ttl_seconds,
        )
        self.capability_tokens = CapabilityTokenManager(secret=self.config.token_secret)
        self.credential_broker = CredentialBroker(default_ttl_seconds=self.config.token_ttl_seconds)
        self.sandbox_executor.reset_state()
        self.audit_trail.reset()
        self.observability.reset()
        self.pre_intent_gate.reset()
        self.constitutional_interceptor.reset()
        self._consumed_nonces.clear()
        self._kill_switch = False

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _validate_schema(self, request: ToolRequest) -> str:
        schema_cls = get_schema(request.action)
        if schema_cls is None:
            raise SchemaValidationError(f"unknown action: {request.action}")
        try:
            validated = schema_cls.model_validate(request.params)
            validated_params = validated.model_dump()
            semantic_check(request.action, validated_params)
        except ValidationError as exc:
            raise SchemaValidationError(str(exc)) from exc
        except SemanticValidationError as exc:
            raise SchemaValidationError(str(exc)) from exc
        # El resto del pipeline opera sobre los parámetros ya validados y
        # canonicalizados, nunca sobre valores crudos del modelo.
        request.params = validated_params
        return canonicalize_params(validated_params)

    def _compute_risk(self, request: ToolRequest) -> RiskLevel:
        base = RISK_BY_ACTION.get(request.action, "low")
        if request.action == "send_payment":
            amount = float(request.params.get("amount", 0))
            if amount > HIGH_PAYMENT_THRESHOLD:
                return RiskLevel.HIGH
            return RiskLevel(base)
        if request.action == "delete_product":
            return RiskLevel.CRITICAL
        return RiskLevel(base)

    def _requires_hitl(self, request: ToolRequest, risk_level: RiskLevel) -> bool:
        if request.action in ("delete_product",):
            return True
        if request.action == "send_payment":
            amount = float(request.params.get("amount", 0))
            if amount > HIGH_PAYMENT_THRESHOLD:
                return True
        if risk_level == RiskLevel.CRITICAL and self.config.require_hitl_for_critical:
            return True
        if risk_level == RiskLevel.HIGH and self.config.require_hitl_for_high:
            return True
        return False

    def _verify_explicit_approval(self, request: ToolRequest, action_hash: str) -> bool:
        if request.dossier_status != "approved":
            return False
        if not request.approval_action_hash:
            return False
        if not request.dossier_hash:
            return False
        # El hash de aprobación debe coincidir exactamente con el hash de la acción
        if request.approval_action_hash != action_hash:
            return False
        return True

    def _extract_resource(self, request: ToolRequest) -> Optional[str]:
        if request.action in ("update_price", "delete_product"):
            return request.params.get("product_id")
        if request.action == "read_file":
            return request.params.get("path")
        return None

    def _idempotency_key(self, request: ToolRequest) -> str:
        return request.compute_action_hash()

    def _is_destructive(self, action: str) -> bool:
        return action in ("delete_product", "send_payment")

    def _classify_action_power(self, action: str) -> Power:
        """Asigna un poder a la acción solicitada mediante clasificador robusto."""
        return ActionPowerClassifier.classify(action)

    def _check_power_separation(self, agent_id: str, action: str) -> Optional[str]:
        """Registra y valida separación de poderes para un agente."""
        power = self._classify_action_power(action)
        self._power_registry.register(agent_id, [power])
        return self._power_registry.check_conflict(agent_id, power.value)

    def _denied(
        self,
        verdict: AuthorizationVerdict,
        reason: str,
        request: ToolRequest,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            verdict=verdict,
            reason=reason,
            trace_id=request.trace_id,
            action_hash=request.compute_action_hash(),
            dossier_hash=request.dossier_hash,
        )

    def _allowed(
        self,
        request: ToolRequest,
        reason: str,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            verdict=AuthorizationVerdict.ALLOWED,
            reason=reason,
            trace_id=request.trace_id,
            action_hash=request.compute_action_hash(),
            dossier_hash=request.dossier_hash,
            risk_level=risk_level,
            requires_hitl=False,
            token_expires_at=time.time() + self.config.token_ttl_seconds,
        )

    def _pending(
        self,
        request: ToolRequest,
        reason: str,
        risk_level: RiskLevel,
    ) -> AuthorizationDecision:
        return AuthorizationDecision(
            verdict=AuthorizationVerdict.PENDING_APPROVAL,
            reason=reason,
            trace_id=request.trace_id,
            action_hash=request.compute_action_hash(),
            dossier_hash=request.dossier_hash,
            risk_level=risk_level,
            requires_hitl=True,
        )

    def _execution_failure(
        self,
        request: ToolRequest,
        error: str,
        status: ExecutionStatus,
    ) -> ExecutionResult:
        return ExecutionResult(
            status=status,
            action=request.action,
            agent_id=request.agent_id,
            trace_id=request.trace_id,
            error=error,
        )

    # -----------------------------------------------------------------------
    # UC-324 Safe Shutdown Adapter
    # -----------------------------------------------------------------------

    def quiesce_for_shutdown(self, shutdown_id: str) -> Dict[str, Any]:
        """UC-324 safe shutdown adapter: reject new authorizations/executions.

        Activates the kill switch but marks the reason as safe-shutdown so
        existing ``set_kill_switch`` / ``is_killed`` behaviour is preserved.
        """
        self._kill_switch = True
        self._shutdown_reason = f"safe_shutdown:{shutdown_id}"
        self._audit("system", "quiesce_for_shutdown", {
            "shutdown_id": shutdown_id,
            "action": "quiesce",
        })
        return {
            "adapter": "uc300_tool_gateway",
            "quiesced": True,
            "shutdown_id": shutdown_id,
            "kill_switch": self._kill_switch,
        }

    def revoke_pending_for_shutdown(self, shutdown_id: str) -> Dict[str, Any]:
        """UC-324 safe shutdown adapter: revoke/clear pending one-use
        capability tokens and credential leases safely."""
        revoked_tokens = self.capability_tokens.revoke_all() if hasattr(self.capability_tokens, "revoke_all") else 0
        revoked_creds = self.credential_broker.revoke_all() if hasattr(self.credential_broker, "revoke_all") else 0
        self._consumed_nonces.clear()
        self._audit("system", "revoke_pending_for_shutdown", {
            "shutdown_id": shutdown_id,
            "revoked_tokens": revoked_tokens,
            "revoked_credentials": revoked_creds,
        })
        return {
            "adapter": "uc300_tool_gateway",
            "revoked_tokens": revoked_tokens,
            "revoked_credentials": revoked_creds,
            "shutdown_id": shutdown_id,
        }

    def shutdown_status(self) -> Dict[str, Any]:
        """UC-324 safe shutdown adapter: status during shutdown."""
        return {
            "adapter": "uc300_tool_gateway",
            "kill_switch": self._kill_switch,
            "shutdown_reason": getattr(self, "_shutdown_reason", ""),
            "pending_nonces": len(self._consumed_nonces),
        }

    def resume_after_approved_reactivation(self, shutdown_id: str) -> Dict[str, Any]:
        """Resume the gateway only after UC-324 completes approved recovery."""
        expected_reason = f"safe_shutdown:{shutdown_id}"
        if getattr(self, "_shutdown_reason", "") != expected_reason:
            return {"adapter": "uc300_tool_gateway", "resumed": False, "shutdown_id": shutdown_id}
        self.capability_tokens.resume_issuing()
        self.credential_broker.resume_issuing()
        self._kill_switch = False
        self._shutdown_reason = ""
        self._audit("system", "resume_after_approved_reactivation", {
            "shutdown_id": shutdown_id,
            "action": "resume",
        })
        return {"adapter": "uc300_tool_gateway", "resumed": True, "shutdown_id": shutdown_id}

    # -----------------------------------------------------------------------
    # UC-308 Champion/Challenger experiment adapter
    # -----------------------------------------------------------------------

    def authorize_experiment_trade(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic deny-real-execution adapter for UC-308.

        - Challengers (and any non-promoted state) are restricted to paper-only.
        - Real orders are allowed only for the champion in the ``promoted`` state
          and when the exact model/version/experiment binding matches.
        """
        experiment_id = request.get("experiment_id", "")
        model_id = request.get("model_id", "")
        version = request.get("model_version", "")
        role = request.get("model_role", "")
        state = request.get("experiment_state", "")
        real_order = bool(request.get("real_order", False))
        expected_model_id = request.get("expected_model_id", "")
        expected_version = request.get("expected_version", "")

        if not experiment_id or not model_id or not version:
            return {
                "allowed": False,
                "mode": "denied",
                "reason": "missing experiment_id, model_id or model_version binding",
            }

        if real_order:
            if role != "champion" or state != "promoted":
                return {
                    "allowed": False,
                    "mode": "denied",
                    "reason": f"real order denied: role={role}, state={state}; only promoted champion may trade",
                }
            if expected_model_id and expected_model_id != model_id:
                return {"allowed": False, "mode": "denied", "reason": "model_id binding mismatch"}
            if expected_version and expected_version != version:
                return {"allowed": False, "mode": "denied", "reason": "version binding mismatch"}

        return {"allowed": True, "mode": "paper_only", "reason": "paper execution authorized"}

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _audit(self, actor: str, event: str, details: Dict[str, Any]) -> None:
        trace_id = details.get("trace_id", "")
        self.audit_trail.record(actor=actor, event=event, details=details, trace_id=trace_id)
