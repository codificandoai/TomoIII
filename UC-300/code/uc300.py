"""
UC-300 — Wrapper de imports para Secure Tool Gateway.

Uso:
    from uc300 import SecureToolGateway, ToolRequest, GatewayConfig
"""

from __future__ import annotations

from capability_tokens import CapabilityTokenManager
from constitutional_interceptor import ConstitutionalInterceptor
from constitutional_models import (
    AgentProposal,
    ConstitutionalDecision,
    ConstitutionalPrinciple,
    ConstitutionalRisk,
    ConstitutionalVerdict,
)
from credential_broker import CredentialBroker, CredentialLease
from immutable_audit import ImmutableAuditTrail
from injection_detector import InjectionDetectionError
from intent_models import (
    IntentDecision,
    IntentRequest,
    IntentRisk,
    IntentVerdict,
)
from models_300 import (
    AuditEntry,
    AuthorizationDecision,
    AuthorizationVerdict,
    CapabilityTokenPayload,
    ExecutionResult,
    ExecutionStatus,
    GatewayConfig,
    PipelineResult,
    RiskLevel,
    ToolAction,
    ToolRequest,
    generate_id,
)
from observability_300 import ObservabilityManager
from policy_engine import PolicyEngine, PolicyRule
from pre_intent_gate import PreIntentGate
from quota_manager import QuotaManager
from sandbox_executor import SandboxExecutor, SimulatedState
from schema_registry import (
    SchemaValidationError,
    SemanticValidationError,
    canonicalize_params,
    get_schema,
    list_actions,
)
from secure_tool_gateway import SecureToolGateway

__all__ = [
    # Core gateway
    "SecureToolGateway",
    # Pre-Intent Gate
    "PreIntentGate",
    "IntentRequest",
    "IntentDecision",
    "IntentVerdict",
    "IntentRisk",
    # Constitutional Interceptor
    "ConstitutionalInterceptor",
    "AgentProposal",
    "ConstitutionalDecision",
    "ConstitutionalVerdict",
    "ConstitutionalRisk",
    "ConstitutionalPrinciple",
    # Models
    "GatewayConfig",
    "ToolRequest",
    "ToolAction",
    "RiskLevel",
    "AuthorizationDecision",
    "AuthorizationVerdict",
    "CapabilityTokenPayload",
    "ExecutionResult",
    "ExecutionStatus",
    "PipelineResult",
    "AuditEntry",
    "generate_id",
    # Components
    "CapabilityTokenManager",
    "CredentialBroker",
    "CredentialLease",
    "ImmutableAuditTrail",
    "InjectionDetectionError",
    "ObservabilityManager",
    "PolicyEngine",
    "PolicyRule",
    "QuotaManager",
    "SandboxExecutor",
    "SimulatedState",
    "SchemaValidationError",
    "SemanticValidationError",
    "canonicalize_params",
    "get_schema",
    "list_actions",
]
