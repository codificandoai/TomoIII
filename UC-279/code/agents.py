"""Six specialized agents collaborating through typed signals."""
from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from typing import Dict

from models import AgentName, AgentSignal, MarketState, PricingPolicy, ScenarioType
from pricing_engine import estimate_elasticity, optimize_price


class BaseAgent(ABC):
    name: AgentName

    @abstractmethod
    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        raise NotImplementedError


class TrendAgent(BaseAgent):
    name = AgentName.TREND

    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        prices = [o.price for o in state.observations[-20:]] + [state.current_price]
        if len(prices) < 4:
            return AgentSignal(self.name, 0.3, "Insufficient history", {"trend": "unknown"})
        short = statistics.mean(prices[-3:])
        long = statistics.mean(prices[-min(10, len(prices)):])
        momentum = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] else 0.0
        trend = "up" if short > long and momentum > 0 else "down" if short < long and momentum < 0 else "flat"
        confidence = min(0.95, 0.5 + min(len(prices), 20) / 50 + abs(momentum) * 3)
        return AgentSignal(self.name, confidence, f"Market trend is {trend}",
                           {"trend": trend, "short_ma": short, "long_ma": long, "momentum_rate": momentum})


class CompetitorAgent(BaseAgent):
    name = AgentName.COMPETITOR

    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        gap = (state.current_price - state.competitor_price) / state.competitor_price
        position = "premium" if gap > 0.1 else "discount" if gap < -0.05 else "competitive"
        flags = ["large_competitor_gap"] if abs(gap) > 0.2 else []
        return AgentSignal(self.name, 0.9, f"Pricing position is {position}",
                           {"gap_rate": gap, "position": position}, flags)


class DemandAgent(BaseAgent):
    name = AgentName.DEMAND

    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        elasticity, confidence = estimate_elasticity(state, state.elasticity)
        predicted_change = 1.05 ** elasticity - 1
        return AgentSignal(self.name, confidence, "Demand elasticity estimated",
                           {"elasticity": elasticity, "demand_change_at_plus_5pct": predicted_change})


class PriceOptimizerAgent(BaseAgent):
    name = AgentName.OPTIMIZER

    def __init__(self, policy: PricingPolicy, scenario: ScenarioType, objective: str = "profit") -> None:
        self.policy, self.scenario, self.objective = policy, scenario, objective

    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        demand_signal = context.get(AgentName.DEMAND.value)
        elasticity = demand_signal.metrics.get("elasticity", state.elasticity) if demand_signal else state.elasticity
        result = optimize_price(state, self.policy, elasticity, self.scenario, self.objective)
        return AgentSignal(self.name, min(0.95, (demand_signal.confidence if demand_signal else 0.5) + 0.15),
                           "Constrained optimum calculated", {
                               "optimal_price": result.price, "expected_demand": result.demand,
                               "expected_revenue": result.revenue, "expected_profit": result.profit,
                               "profit_uplift_rate": result.uplift_rate, "lower_bound": result.bounds[0],
                               "upper_bound": result.bounds[1], "objective": self.objective,
                           })


class AnomalyAgent(BaseAgent):
    name = AgentName.ANOMALY

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        prices = [o.price for o in state.observations[-30:]]
        if len(prices) < 5:
            return AgentSignal(self.name, 0.35, "Insufficient anomaly baseline", {"z_score": 0.0})
        mean, std = statistics.mean(prices), statistics.pstdev(prices)
        z_score = (state.current_price - mean) / std if std > 1e-9 else 0.0
        anomaly = abs(z_score) >= self.threshold
        flags = ["price_anomaly"] if anomaly else []
        return AgentSignal(self.name, min(0.99, 0.7 + len(prices) / 100),
                           "Price anomaly detected" if anomaly else "No price anomaly",
                           {"z_score": z_score, "anomaly": anomaly}, flags)


class StrategyAgent(BaseAgent):
    name = AgentName.STRATEGY

    def __init__(self, policy: PricingPolicy) -> None:
        self.policy = policy

    def analyze(self, state: MarketState, context: Dict[str, AgentSignal]) -> AgentSignal:
        optimizer = context[AgentName.OPTIMIZER.value]
        anomaly = context[AgentName.ANOMALY.value]
        risk_flags = [flag for signal in context.values() for flag in signal.risk_flags]
        confidence = statistics.mean(s.confidence for s in context.values())
        price = optimizer.metrics["optimal_price"]
        change = (price - state.current_price) / state.current_price
        execute = not anomaly.metrics.get("anomaly") and confidence >= self.policy.min_confidence_to_execute
        if abs(change) < 0.002:
            action, execute = "hold", False
        elif execute:
            action = "increase" if change > 0 else "decrease"
        else:
            action = "review"
        return AgentSignal(self.name, confidence, f"Strategy decision: {action}", {
            "action": action, "execute": execute, "recommended_price": price,
            "change_rate": change,
        }, risk_flags)