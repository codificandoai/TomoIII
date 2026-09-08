"""
UC-300 — Validación operacional del Secure Tool Gateway.

Ejecuta checks funcionales de todos los componentes sin necesidad de pytest.
"""

from __future__ import annotations

import sys

from models_300 import AuthorizationVerdict, ExecutionStatus, GatewayConfig, ToolRequest
from secure_tool_gateway import SecureToolGateway


def _pass(name: str):
    print(f"[PASS] {name}")


def _fail(name: str, exc: Exception):
    print(f"[FAIL] {name}: {exc}")
    return False


def validate_schema_registry():
    from schema_registry import validate_and_canonicalize
    canonical = validate_and_canonicalize("update_price", {
        "product_id": "SKU-001", "new_price": 120.5, "reason": "Ajuste"
    })
    assert isinstance(canonical, str)
    try:
        validate_and_canonicalize("update_price", {
            "product_id": "SKU-001", "new_price": "bad", "reason": "Ajuste"
        })
        raise AssertionError("Expected schema validation to fail")
    except Exception:
        pass
    _pass("schema_registry")


def validate_injection_detector():
    from injection_detector import assert_clean, InjectionDetectionError
    assert_clean("agent", "update_price", {"reason": "Ajuste mensual"})
    try:
        assert_clean("agent", "update_price", {"reason": "ok; DROP TABLE"})
        raise AssertionError("Expected injection detection")
    except InjectionDetectionError:
        pass
    _pass("injection_detector")


def validate_policy_engine():
    from policy_engine import PolicyEngine
    engine = PolicyEngine()
    engine.load_defaults()
    allowed = engine.evaluate("agent_pricing_eu", "update_price", {"product_id": "SKU-001"}, "default")
    assert allowed["allowed"] is True
    denied = engine.evaluate("agent_pricing_eu", "update_price", {"product_id": "SKU-100"}, "default")
    assert denied["allowed"] is False
    _pass("policy_engine")


def validate_capability_tokens():
    from capability_tokens import CapabilityTokenManager
    mgr = CapabilityTokenManager(secret="secret")
    token = mgr.issue("ahash", "dhash", "agent", "update_price")
    consumed = set()
    payload = mgr.validate(token, "ahash", "dhash", "agent", "update_price", consumed)
    assert payload.action_hash == "ahash"
    # Replay
    try:
        mgr.validate(token, "ahash", "dhash", "agent", "update_price", consumed)
        raise AssertionError("Expected replay error")
    except ValueError as exc:
        assert "replay" in str(exc).lower()
    _pass("capability_tokens")


def validate_credential_broker():
    from credential_broker import CredentialBroker
    broker = CredentialBroker(default_ttl_seconds=60)
    lease = broker.issue("cap_token", "SKU-001", "update_price")
    assert "secret" not in lease.to_dict()
    broker.validate(lease.lease_id, "cap_token", "SKU-001")
    _pass("credential_broker")


def validate_quota_manager():
    from quota_manager import QuotaManager
    qm = QuotaManager(rate_limit_per_minute=2, budget_daily=100)
    assert qm.check_rate("a")["allowed"] is True, "first rate check should be allowed"
    qm.consume_rate("a")
    assert qm.check_rate("a")["allowed"] is True, "second rate check should be allowed"
    qm.consume_rate("a")
    assert qm.check_rate("a")["allowed"] is False, "third rate check should be denied"
    assert qm.check_budget(80)["allowed"] is True, "first budget check should be allowed"
    qm.consume_budget(80)
    assert qm.check_budget(30)["allowed"] is False, "over-budget request should be denied"
    _pass("quota_manager")


def validate_sandbox_executor():
    from sandbox_executor import SandboxExecutor
    ex = SandboxExecutor()
    result = ex.execute("t", "agent", "update_price", {"product_id": "SKU-001", "new_price": 200.0, "reason": "x"})
    assert result.status == ExecutionStatus.SUCCESS
    delete = ex.execute("t", "agent", "delete_product", {"product_id": "SKU-001", "confirmation_code": "CONFIRM-ABCD"})
    assert delete.status == ExecutionStatus.DRY_RUN
    _pass("sandbox_executor")


def validate_immutable_audit():
    from immutable_audit import ImmutableAuditTrail
    trail = ImmutableAuditTrail()
    trail.record("a", "evt1", {"x": 1})
    trail.record("b", "evt2", {"x": 2})
    assert len(trail.entries) == 2
    assert trail.verify_chain() is True
    trail.entries[0].event = "tampered"
    assert trail.verify_chain() is False
    _pass("immutable_audit")


def validate_gateway_authorize_execute():
    config = GatewayConfig(token_secret="validation-secret-32-bytes-1234567890")
    gateway = SecureToolGateway(config=config)
    req = ToolRequest(
        agent_id="agent_pricing_eu",
        action="update_price",
        params={"product_id": "SKU-001", "new_price": 125.0, "reason": "Ajuste"},
        environment="default",
    )
    auth = gateway.authorize(req)
    assert auth.verdict == AuthorizationVerdict.ALLOWED
    result = gateway.execute(req, auth.capability_token)
    assert result.status == ExecutionStatus.SUCCESS
    _pass("gateway_authorize_execute")


def validate_gateway_human_approval():
    config = GatewayConfig(token_secret="validation-secret-32-bytes-1234567890")
    gateway = SecureToolGateway(config=config)
    req = ToolRequest(
        agent_id="agent_pricing_us",
        action="send_payment",
        params={"recipient_id": "vendor_1", "amount": 15000.0, "currency": "USD", "memo": "x"},
        environment="default",
    )
    # Sin aprobación
    pending = gateway.authorize(req)
    assert pending.verdict == AuthorizationVerdict.PENDING_APPROVAL

    # Con aprobación explícita ligada al hash exacto
    action_hash = req.compute_action_hash()
    approved = gateway.approve_request(
        req,
        dossier_id="dos_val",
        dossier_hash="dhash_val",
        reviewer_id="reviewer_001",
        approval_action_hash=action_hash,
    )
    assert approved.verdict == AuthorizationVerdict.ALLOWED
    result = gateway.execute(req, approved.capability_token)
    assert result.status == ExecutionStatus.DRY_RUN
    _pass("gateway_human_approval")


def validate_toctou_param_change():
    config = GatewayConfig(token_secret="validation-secret-32-bytes-1234567890")
    gateway = SecureToolGateway(config=config)
    req = ToolRequest(
        agent_id="agent_pricing_eu",
        action="update_price",
        params={"product_id": "SKU-001", "new_price": 125.0, "reason": "Ajuste"},
        environment="default",
    )
    auth = gateway.authorize(req)
    req.params["new_price"] = 999.99
    result = gateway.execute(req, auth.capability_token)
    assert result.status == ExecutionStatus.BLOCKED
    assert "action hash mismatch" in result.error
    _pass("gateway_toctou_param_change")


def validate_kill_switch():
    config = GatewayConfig(token_secret="validation-secret-32-bytes-1234567890")
    gateway = SecureToolGateway(config=config)
    gateway.set_kill_switch(True)
    req = ToolRequest(
        agent_id="agent_pricing_eu",
        action="update_price",
        params={"product_id": "SKU-001", "new_price": 125.0, "reason": "Ajuste"},
        environment="default",
    )
    result = gateway.process(req)
    assert result.verdict == AuthorizationVerdict.KILLED.value
    _pass("gateway_kill_switch")


def validate_audit_chain():
    config = GatewayConfig(token_secret="validation-secret-32-bytes-1234567890")
    gateway = SecureToolGateway(config=config)
    req = ToolRequest(
        agent_id="agent_pricing_eu",
        action="read_file",
        params={"path": "catalog/eu_products.md"},
        environment="default",
    )
    gateway.process(req)
    assert len(gateway.audit_trail.entries) > 0
    assert gateway.audit_trail.verify_chain() is True
    _pass("gateway_audit_chain")


def main():
    print("=" * 70)
    print("UC-300 — Validación operacional")
    print("=" * 70)
    checks = [
        validate_schema_registry,
        validate_injection_detector,
        validate_policy_engine,
        validate_capability_tokens,
        validate_credential_broker,
        validate_quota_manager,
        validate_sandbox_executor,
        validate_immutable_audit,
        validate_gateway_authorize_execute,
        validate_gateway_human_approval,
        validate_toctou_param_change,
        validate_kill_switch,
        validate_audit_chain,
    ]
    failed = []
    for check in checks:
        try:
            check()
        except Exception as exc:
            failed.append((check.__name__, exc))
            _fail(check.__name__, exc)
    print("=" * 70)
    if failed:
        print(f"RESULTADO: {len(checks) - len(failed)}/{len(checks)} PASS")
        sys.exit(1)
    print(f"RESULTADO: {len(checks)}/{len(checks)} PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
