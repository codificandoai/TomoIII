import pytest

from adapters import build_adapters
from models import ExecutionMode, Framework, MarketState
from orchestrator import TrackPriceFederatedOrchestrator


def pipeline(mode=ExecutionMode.SIMULATION):
    return TrackPriceFederatedOrchestrator(MarketState("SKU", 100, 60, 95, 1000, 5000,
        headlines=["Demand growth", "Chip shortage"]), mode)


def test_all_five_frameworks_respond():
    run = pipeline().run(idempotency_key="one")
    assert {r.framework for r in run.responses} == set(Framework)
    assert all(not r.native for r in run.responses)
    assert len(run.audit_hash()) == 64


def test_auto_mode_runs_real_langgraph():
    run = pipeline(ExecutionMode.AUTO).run(idempotency_key="auto")
    langgraph = next(r for r in run.responses if r.framework == Framework.LANGGRAPH)
    assert langgraph.native


def test_dry_run_does_not_change_state():
    p = pipeline()
    version = p.state.version
    run = p.run(execute=False)
    assert p.state.version == version
    assert run.decision.action in {"recommend", "review"}


def test_execute_closed_loop_is_bounded():
    p = pipeline()
    before = p.state.current_price
    run = p.run(execute=True)
    if run.decision.action == "execute":
        assert abs(p.state.current_price - before) <= before * .1
        assert p.state.version == 2


def test_idempotency_returns_same_run():
    p = pipeline()
    first = p.run(idempotency_key="same")
    second = p.run(idempotency_key="same")
    assert first is second
    assert len(p.runs) == 1


def test_events_cover_barrier():
    p = pipeline()
    run = p.run()
    events = p.bus.events(run.run_id)
    assert events[0]["type"] == "run.started"
    assert sum(e["type"] == "framework.completed" for e in events) == 5
    assert events[-1]["type"] == "run.completed"


def test_invalid_state_and_assimilation():
    with pytest.raises(ValueError):
        TrackPriceFederatedOrchestrator(MarketState("", 100, 50, 90, 1000))
    with pytest.raises(ValueError):
        TrackPriceFederatedOrchestrator(MarketState("x", 100, 50, 90, 1000), assimilation_rate=2)


def test_native_mode_rejects_missing_sdk():
    adapters = build_adapters(ExecutionMode.NATIVE)
    assert not adapters[Framework.CREWAI].available
