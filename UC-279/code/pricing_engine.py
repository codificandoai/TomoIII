"""Deterministic demand estimation, forecasting and constrained price optimization."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import List, Tuple

from models import ForecastPoint, MarketState, PricingPolicy, ScenarioType


SCENARIO_MULTIPLIERS = {
    ScenarioType.BASELINE: (1.0, 1.0),
    ScenarioType.OPTIMISTIC: (1.06, 1.10),
    ScenarioType.PESSIMISTIC: (0.94, 0.88),
    ScenarioType.COMPETITOR_SHOCK: (0.88, 0.92),
    ScenarioType.DEMAND_SHOCK: (1.0, 0.72),
}


def estimate_elasticity(state: MarketState, fallback: float = -1.5) -> Tuple[float, float]:
    """Estimate log-log elasticity and a bounded confidence score."""
    valid = [(o.price, o.demand) for o in state.observations if o.price > 0 and o.demand > 0]
    if len(valid) < 4:
        return fallback, min(0.55, 0.15 + len(valid) * 0.1)
    xs = [math.log(p) for p, _ in valid[-60:]]
    ys = [math.log(q) for _, q in valid[-60:]]
    x_mean, y_mean = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator < 1e-9:
        return fallback, 0.35
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    slope = min(-0.05, max(-5.0, slope))
    predictions = [y_mean + slope * (x - x_mean) for x in xs]
    residual = sum((y - p) ** 2 for y, p in zip(ys, predictions))
    total = sum((y - y_mean) ** 2 for y in ys) or 1.0
    r2 = max(0.0, min(1.0, 1 - residual / total))
    confidence = min(0.98, 0.45 + 0.45 * r2 + min(len(valid), 30) / 300)
    return slope, confidence


def demand_at_price(state: MarketState, price: float, elasticity: float,
                    demand_multiplier: float = 1.0) -> float:
    return max(0.0, state.current_demand * (price / state.current_price) ** elasticity * demand_multiplier)


@dataclass(frozen=True)
class OptimizationResult:
    price: float
    demand: float
    revenue: float
    profit: float
    uplift_rate: float
    bounds: Tuple[float, float]


def optimize_price(state: MarketState, policy: PricingPolicy, elasticity: float,
                   scenario: ScenarioType = ScenarioType.BASELINE,
                   objective: str = "profit", grid_size: int = 401) -> OptimizationResult:
    """Grid-search a global optimum under business and safety constraints."""
    policy.validate()
    competitor_multiplier, demand_multiplier = SCENARIO_MULTIPLIERS[scenario]
    scenario_competitor = state.competitor_price * competitor_multiplier
    floor = max(state.unit_cost * (1 + policy.min_margin_rate),
                state.current_price * (1 - policy.max_price_change_rate))
    ceiling = min(scenario_competitor * (1 + policy.max_competitor_gap_rate),
                  state.current_price * (1 + policy.max_price_change_rate))
    if floor > ceiling:
        floor = ceiling = max(state.unit_cost * (1 + policy.min_margin_rate), min(floor, ceiling))

    best = None
    for i in range(max(2, grid_size)):
        price = floor + (ceiling - floor) * i / (max(2, grid_size) - 1)
        demand = min(state.inventory, demand_at_price(state, price, elasticity, demand_multiplier))
        revenue = price * demand
        profit = (price - state.unit_cost) * demand
        score = profit if objective == "profit" else revenue
        if best is None or score > best[0]:
            best = (score, price, demand, revenue, profit)
    _, price, demand, revenue, profit = best
    current_profit = state.profit
    uplift = (profit - current_profit) / abs(current_profit) if current_profit else 0.0
    return OptimizationResult(price, demand, revenue, profit, uplift, (floor, ceiling))


def forecast(state: MarketState, days: int, scenario: ScenarioType,
             price: float | None = None) -> List[ForecastPoint]:
    """Create deterministic scenario projections with widening uncertainty bands."""
    if not 1 <= days <= 365:
        raise ValueError("days must be between 1 and 365")
    competitor_multiplier, demand_multiplier = SCENARIO_MULTIPLIERS[scenario]
    target_price = price or state.current_price
    trend = 0.0
    if len(state.observations) >= 2:
        prices = [o.price for o in state.observations[-14:]]
        trend = (prices[-1] - prices[0]) / max(1, len(prices) - 1)
    points = []
    for horizon in range(1, days + 1):
        projected_price = max(state.unit_cost, target_price + trend * horizon)
        seasonality = 1 + 0.04 * math.sin(2 * math.pi * horizon / 7)
        projected_demand = demand_at_price(
            state, projected_price, state.elasticity,
            demand_multiplier * seasonality,
        )
        uncertainty = min(0.45, 0.08 + horizon * 0.008)
        points.append(ForecastPoint(
            horizon=horizon, price=round(projected_price, 2),
            demand=round(projected_demand, 2),
            lower_demand=round(projected_demand * (1 - uncertainty), 2),
            upper_demand=round(projected_demand * (1 + uncertainty), 2),
            expected_profit=round((projected_price - state.unit_cost) * min(projected_demand, state.inventory), 2),
        ))
    return points