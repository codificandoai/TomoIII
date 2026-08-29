"""Domain contracts for the TrackPrice.ai pricing digital twin."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ScenarioType(str, Enum):
    BASELINE = "baseline"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    COMPETITOR_SHOCK = "competitor_shock"
    DEMAND_SHOCK = "demand_shock"


class AgentName(str, Enum):
    TREND = "alpha_trend"
    COMPETITOR = "beta_competitor"
    DEMAND = "gamma_demand"
    OPTIMIZER = "delta_optimizer"
    ANOMALY = "epsilon_anomaly"
    STRATEGY = "zeta_strategy"


@dataclass(frozen=True)
class PricingPolicy:
    min_margin_rate: float = 0.10
    max_competitor_gap_rate: float = 0.20
    max_price_change_rate: float = 0.10
    anomaly_z_threshold: float = 2.5
    min_confidence_to_execute: float = 0.65

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if name != "anomaly_z_threshold" and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.anomaly_z_threshold <= 0:
            raise ValueError("anomaly_z_threshold must be positive")


@dataclass
class MarketObservation:
    price: float
    demand: float
    competitor_price: float
    timestamp: float = field(default_factory=time.time)
    inventory: float = 10000.0
    conversion_rate: float = 0.03

    def validate(self) -> None:
        if min(self.price, self.demand, self.competitor_price, self.inventory) < 0:
            raise ValueError("Market values cannot be negative")
        if not 0 <= self.conversion_rate <= 1:
            raise ValueError("conversion_rate must be between 0 and 1")


@dataclass
class MarketState:
    sku: str
    current_price: float
    unit_cost: float
    competitor_price: float
    current_demand: float
    inventory: float = 10000.0
    step: int = 0
    version: int = 1
    elasticity: float = -1.5
    observations: List[MarketObservation] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def validate(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku is required")
        if min(self.current_price, self.unit_cost, self.competitor_price, self.current_demand, self.inventory) < 0:
            raise ValueError("State values cannot be negative")
        if self.current_price == 0 or self.competitor_price == 0:
            raise ValueError("Prices must be greater than zero")
        if self.elasticity >= 0:
            raise ValueError("Price elasticity must be negative")
        for observation in self.observations:
            observation.validate()

    @property
    def revenue(self) -> float:
        return self.current_price * self.current_demand

    @property
    def profit(self) -> float:
        return (self.current_price - self.unit_cost) * self.current_demand

    @property
    def margin_rate(self) -> float:
        return (self.current_price - self.unit_cost) / self.current_price

    def record(self) -> None:
        self.observations.append(MarketObservation(
            price=self.current_price, demand=self.current_demand,
            competitor_price=self.competitor_price, inventory=self.inventory,
        ))
        self.updated_at = time.time()

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["revenue"] = round(self.revenue, 2)
        data["profit"] = round(self.profit, 2)
        data["margin_rate"] = round(self.margin_rate, 6)
        return data


@dataclass(frozen=True)
class AgentSignal:
    agent: AgentName
    confidence: float
    summary: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceRecommendation:
    recommended_price: float
    expected_demand: float
    expected_revenue: float
    expected_profit: float
    profit_uplift_rate: float
    action: str
    confidence: float
    guardrails: List[str]


@dataclass
class CycleResult:
    twin_id: str
    cycle_id: str
    state_before: Dict[str, Any]
    state_after: Dict[str, Any]
    signals: List[AgentSignal]
    recommendation: PriceRecommendation
    scenario: ScenarioType
    executed: bool
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(cls, twin_id: str, **kwargs: Any) -> "CycleResult":
        return cls(twin_id=twin_id, cycle_id=uuid4().hex[:16], **kwargs)

    def audit_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ForecastPoint:
    horizon: int
    price: float
    demand: float
    lower_demand: float
    upper_demand: float
    expected_profit: float
