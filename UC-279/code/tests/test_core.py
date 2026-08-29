from dataclasses import asdict
import pytest

from core import TrackPriceDigitalTwin, TwinRegistry
from models import AgentName, MarketState, PricingPolicy, ScenarioType


def twin():
    return TrackPriceDigitalTwin(MarketState("SKU-X", 100, 60, 95, 1000, inventory=10000), seed=7)


def test_state_validation():
    with pytest.raises(ValueError):
        TrackPriceDigitalTwin(MarketState("", 100, 60, 95, 1000))


def test_pipeline_emits_six_ordered_signals():
    result = twin().analyze()
    assert [s.agent for s in result.signals] == list(AgentName)
    assert result.recommendation.recommended_price > 0
    assert len(result.audit_hash()) == 64


def test_analysis_is_dry_run_by_default():
    t = twin()
    version = t.state.version
    result = t.analyze()
    assert not result.executed
    assert t.state.version == version


def test_execute_updates_version_when_approved():
    t = twin()
    version = t.state.version
    result = t.analyze(execute=True)
    if result.executed:
        assert t.state.version == version + 1


def test_optimistic_concurrency():
    t = twin()
    with pytest.raises(ValueError, match="version conflict"):
        t.ingest(101, 900, 96, expected_version=999)


def test_ingest_records_observation():
    t = twin()
    count = len(t.state.observations)
    state = t.ingest(102, 900, 97, inventory=8000, expected_version=1)
    assert len(t.state.observations) == count + 1
    assert state["version"] == 2


def test_scenario_forecast():
    points = twin().project(7, ScenarioType.PESSIMISTIC)
    assert len(points) == 7
    assert set(points[0]) == {"horizon", "price", "demand", "lower_demand", "upper_demand", "expected_profit"}


def test_simulation_is_reproducible():
    one, two = twin(), twin()
    a = one.simulate(3, auto_execute=False)
    b = two.simulate(3, auto_execute=False)
    assert [r.state_after["competitor_price"] for r in a] == [r.state_after["competitor_price"] for r in b]


def test_registry_lifecycle():
    registry = TwinRegistry()
    registry.create(MarketState("SKU-A", 100, 50, 90, 1000))
    assert registry.get("SKU-A").state.sku == "SKU-A"
    assert len(registry.list()) == 1
    with pytest.raises(ValueError):
        registry.create(MarketState("SKU-A", 100, 50, 90, 1000))
    with pytest.raises(KeyError):
        registry.get("missing")
