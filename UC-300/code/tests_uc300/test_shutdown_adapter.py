"""UC-300 — Tests for the UC-324 safe-shutdown adapter methods."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from secure_tool_gateway import SecureToolGateway
from models_300 import ToolRequest, GatewayConfig


def _gateway():
    return SecureToolGateway(config=GatewayConfig(token_ttl_seconds=60.0))


def test_quiesce_for_shutdown_rejects_authorize_and_execute():
    gw = _gateway()
    result = gw.quiesce_for_shutdown("sd-001")
    assert result["quiesced"] is True
    assert gw.is_killed() is True

    # authorize should be rejected
    req = ToolRequest(action="send_payment", agent_id="agent-1", params={"amount": 10})
    decision = gw.authorize(req)
    assert decision.verdict.value.lower() == "killed"

    # execute should also be rejected
    exec_result = gw.execute(req, "some-token")
    assert exec_result.status.value.lower() == "blocked"


def test_revoke_pending_for_shutdown_revokes_capability_tokens_and_leases():
    gw = _gateway()
    gw.quiesce_for_shutdown("sd-002")

    # Issue a real capability token directly
    token = gw.capability_tokens.issue(
        action_hash="hash-1",
        dossier_hash="dhash-1",
        agent_id="agent-1",
        action="send_payment",
    )

    # Issue a credential lease
    lease = gw.credential_broker.issue(token, resource="res-1", scope="read")
    assert lease.lease_id in gw.credential_broker._leases
    assert not gw.credential_broker._leases[lease.lease_id].revoked

    result = gw.revoke_pending_for_shutdown("sd-002")
    assert result["revoked_credentials"] == 1
    assert result["revoked_tokens"] == 1
    assert gw.credential_broker._leases[lease.lease_id].revoked


def test_resume_after_approved_reactivation_clears_kill_switch():
    gw = _gateway()
    gw.quiesce_for_shutdown("sd-003")
    assert gw.is_killed() is True
    result = gw.resume_after_approved_reactivation("sd-003")
    assert result["resumed"] is True
    assert gw.is_killed() is False


def test_shutdown_status_reports_state():
    gw = _gateway()
    gw.quiesce_for_shutdown("sd-004")
    status = gw.shutdown_status()
    assert status["kill_switch"] is True
    assert status["shutdown_reason"] == "safe_shutdown:sd-004"
