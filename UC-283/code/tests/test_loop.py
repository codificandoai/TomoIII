import pytest

from mcp_server import MCPToolServer, build_pricing_server
from memory import LessonMemory
from models import GateStatus, MarketContext, ToolDefinition
from self_correction import GovernedPricingLoop, IndependentCritic


def context(): return MarketContext("SKU", 249.99, 150, 245, 5.5)


def test_loop_reduces_gap_and_approves():
    result = GovernedPricingLoop(max_attempts=4).execute(context())
    assert result.status == "approved"
    assert len(result.attempts) >= 2
    assert result.attempts[0].critique.status == GateStatus.FAIL
    assert result.attempts[-1].critique.status == GateStatus.PASS
    assert len(result.audit_hash()) == 64


def test_challenge_gates_are_evidence_based():
    result = GovernedPricingLoop().execute(context())
    gates = result.attempts[-1].critique.challenge_results
    assert {g["gate"] for g in gates} >= {"margin_floor", "competitive_ceiling", "volatility"}
    assert all("passed" in g and "value" in g for g in gates)


def test_memory_persists_lessons():
    memory = LessonMemory()
    GovernedPricingLoop(memory).execute(context())
    assert memory.stats("SKU")["total"] > 0
    assert memory.recall("SKU")


def test_dangerous_tool_requires_approval():
    loop = GovernedPricingLoop()
    pending = loop.execute(context(), apply=True, approved=False)
    assert pending.status == "approval_required"
    applied = loop.execute(context(), apply=True, approved=True)
    assert applied.status == "applied"


def test_tool_discovery_and_schema_validation():
    server = build_pricing_server(lambda: {"ok": True})
    assert len(server.list_tools()) == 3
    with pytest.raises(ValueError, match="missing"):
        server.call_tool("get_market_context", {})
    with pytest.raises(ValueError, match="unknown"):
        server.call_tool("get_market_context", {"product_id": "x", "extra": 1})
    with pytest.raises(KeyError):
        server.call_tool("unknown", {})


def test_invalid_context():
    with pytest.raises(ValueError):
        GovernedPricingLoop().execute(MarketContext("", 100, 50, 90, 5))
