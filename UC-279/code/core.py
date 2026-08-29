"""Event-driven core and lifecycle for TrackPrice.ai digital twins."""
from __future__ import annotations

import random
import threading
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agents import AnomalyAgent, CompetitorAgent, DemandAgent, PriceOptimizerAgent, StrategyAgent, TrendAgent
from models import AgentName, CycleResult, MarketState, PriceRecommendation, PricingPolicy, ScenarioType
from pricing_engine import SCENARIO_MULTIPLIERS, forecast


class TrackPriceDigitalTwin:
    """Coordinates six specialized agents over a versioned market state."""

    def __init__(self, state: MarketState, policy: Optional[PricingPolicy] = None,
                 seed: int = 42) -> None:
        state.validate()
        self.twin_id = uuid4().hex[:16]
        self.state = state
        self.policy = policy or PricingPolicy()
        self.policy.validate()
        self.random = random.Random(seed)
        self.cycles: List[CycleResult] = []
        self._lock = threading.RLock()
        if not self.state.observations:
            self._seed_history()

    def _seed_history(self, points: int = 12) -> None:
        base_price, base_demand = self.state.current_price, self.state.current_demand
        for i in range(points):
            drift = (i - points) * 0.002
            self.state.current_price = base_price * (1 + drift)
            self.state.current_demand = base_demand * (self.state.current_price / base_price) ** self.state.elasticity
            self.state.record()
        self.state.current_price, self.state.current_demand = base_price, base_demand

    def ingest(self, price: float, demand: float, competitor_price: float,
               inventory: Optional[float] = None, expected_version: Optional[int] = None) -> Dict[str, Any]:
        """Atomically ingest observed market data with optimistic concurrency."""
        with self._lock:
            if expected_version is not None and expected_version != self.state.version:
                raise ValueError(f"version conflict: expected {expected_version}, current {self.state.version}")
            if min(price, demand, competitor_price) < 0 or price == 0 or competitor_price == 0:
                raise ValueError("prices must be positive and demand non-negative")
            self.state.current_price, self.state.current_demand = price, demand
            self.state.competitor_price = competitor_price
            if inventory is not None:
                if inventory < 0:
                    raise ValueError("inventory cannot be negative")
                self.state.inventory = inventory
            self.state.step += 1
            self.state.version += 1
            self.state.record()
            return self.state.public_dict()

    def analyze(self, scenario: ScenarioType = ScenarioType.BASELINE,
                objective: str = "profit", execute: bool = False) -> CycleResult:
        if objective not in {"profit", "revenue"}:
            raise ValueError("objective must be profit or revenue")
        with self._lock:
            before = self.state.public_dict()
            agents = [
                TrendAgent(), CompetitorAgent(), DemandAgent(),
                PriceOptimizerAgent(self.policy, scenario, objective),
                AnomalyAgent(self.policy.anomaly_z_threshold),
                StrategyAgent(self.policy),
            ]
            context = {}
            signals = []
            for agent in agents:
                signal = agent.analyze(self.state, context)
                context[signal.agent.value] = signal
                signals.append(signal)

            optimizer = context[AgentName.OPTIMIZER.value]
            strategy = context[AgentName.STRATEGY.value]
            recommended = optimizer.metrics["optimal_price"]
            guardrails = list(dict.fromkeys(flag for signal in signals for flag in signal.risk_flags))
            should_execute = bool(execute and strategy.metrics["execute"])
            if should_execute:
                self.state.current_price = recommended
                self.state.current_demand = min(self.state.inventory, optimizer.metrics["expected_demand"])
                self.state.step += 1
                self.state.version += 1
                self.state.record()
            recommendation = PriceRecommendation(
                recommended_price=round(recommended, 2),
                expected_demand=round(optimizer.metrics["expected_demand"], 2),
                expected_revenue=round(optimizer.metrics["expected_revenue"], 2),
                expected_profit=round(optimizer.metrics["expected_profit"], 2),
                profit_uplift_rate=round(optimizer.metrics["profit_uplift_rate"], 6),
                action=strategy.metrics["action"], confidence=round(strategy.confidence, 4),
                guardrails=guardrails,
            )
            result = CycleResult.create(
                twin_id=self.twin_id, state_before=before, state_after=self.state.public_dict(),
                signals=signals, recommendation=recommendation, scenario=scenario, executed=should_execute,
            )
            self.cycles.append(result)
            return result

    def project(self, days: int, scenario: ScenarioType = ScenarioType.BASELINE,
                price: Optional[float] = None) -> List[Dict[str, Any]]:
        return [asdict(point) for point in forecast(self.state, days, scenario, price)]

    def simulate(self, steps: int, scenario: ScenarioType = ScenarioType.BASELINE,
                 auto_execute: bool = True) -> List[CycleResult]:
        if not 1 <= steps <= 365:
            raise ValueError("steps must be between 1 and 365")
        results = []
        competitor_multiplier, demand_multiplier = SCENARIO_MULTIPLIERS[scenario]
        for _ in range(steps):
            competitor = max(self.state.unit_cost, self.state.competitor_price * (
                1 + self.random.gauss(0, 0.008)) * (1 + (competitor_multiplier - 1) * 0.08))
            organic_demand = max(0.0, self.state.current_demand * demand_multiplier * (1 + self.random.gauss(0, 0.025)))
            self.ingest(self.state.current_price, organic_demand, competitor,
                        max(0.0, self.state.inventory - min(self.state.inventory, organic_demand)))
            results.append(self.analyze(scenario, execute=auto_execute))
        return results


class TwinRegistry:
    """Thread-safe in-process registry of SKU digital twins."""

    def __init__(self) -> None:
        self._twins: Dict[str, TrackPriceDigitalTwin] = {}
        self._lock = threading.RLock()

    def create(self, state: MarketState, policy: Optional[PricingPolicy] = None,
               seed: int = 42) -> TrackPriceDigitalTwin:
        with self._lock:
            if state.sku in self._twins:
                raise ValueError(f"Twin already exists for {state.sku}")
            twin = TrackPriceDigitalTwin(state, policy, seed)
            self._twins[state.sku] = twin
            return twin

    def get(self, sku: str) -> TrackPriceDigitalTwin:
        try:
            return self._twins[sku]
        except KeyError as exc:
            raise KeyError(f"Twin not found for {sku}") from exc

    def list(self) -> List[TrackPriceDigitalTwin]:
        return list(self._twins.values())