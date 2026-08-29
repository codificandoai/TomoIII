import math
import pytest

from models import MarketObservation, MarketState, PricingPolicy, ScenarioType
from pricing_engine import demand_at_price, estimate_elasticity, forecast, optimize_price


def state():
    s = MarketState("SKU-1", 100, 60, 95, 1000, inventory=10000, elasticity=-2)
    for price in [90, 95, 100, 105, 110, 115]:
        s.observations.append(MarketObservation(price, 1000 * (price / 100) ** -2, 95))
    return s


def test_demand_decreases_as_price_increases():
    s = state()
    assert demand_at_price(s, 110, -2) < demand_at_price(s, 90, -2)


def test_estimates_negative_elasticity():
    elasticity, confidence = estimate_elasticity(state())
    assert elasticity == pytest.approx(-2, abs=.05)
    assert .45 <= confidence <= 1


def test_optimizer_respects_guardrails():
    s, policy = state(), PricingPolicy(max_price_change_rate=.05)
    result = optimize_price(s, policy, -2)
    assert s.unit_cost * 1.1 <= result.price <= s.current_price * 1.05
    assert result.demand <= s.inventory


def test_revenue_objective_supported():
    result = optimize_price(state(), PricingPolicy(), -2, objective="revenue")
    assert result.revenue > 0


@pytest.mark.parametrize("scenario", list(ScenarioType))
def test_all_scenarios_optimize(scenario):
    result = optimize_price(state(), PricingPolicy(), -2, scenario)
    assert result.price > 0


def test_forecast_has_bands():
    points = forecast(state(), 10, ScenarioType.BASELINE)
    assert len(points) == 10
    assert all(p.lower_demand <= p.demand <= p.upper_demand for p in points)


def test_forecast_rejects_invalid_horizon():
    with pytest.raises(ValueError):
        forecast(state(), 0, ScenarioType.BASELINE)
