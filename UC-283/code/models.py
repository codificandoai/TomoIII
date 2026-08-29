"""Domain contracts for governed self-correction and MCP tools."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    APPROVAL_REQUIRED = "approval_required"


@dataclass(frozen=True)
class PricingPolicy:
    min_margin: float = .15
    max_margin: float = .60
    max_competitor_gap: float = .15
    min_competitor_gap: float = -.05
    max_volatility_multiple: float = 2.0
    approval_threshold: float = 80.0


@dataclass(frozen=True)
class MarketContext:
    product_id: str
    current_price: float
    cost: float
    competitor_price: float
    historical_volatility: float
    elasticity: float = -1.5
    base_demand: float = 5000

    def validate(self) -> None:
        if not self.product_id.strip(): raise ValueError("product_id is required")
        if min(self.current_price, self.cost, self.competitor_price, self.historical_volatility, self.base_demand) < 0:
            raise ValueError("market values cannot be negative")
        if self.current_price == 0 or self.competitor_price == 0: raise ValueError("prices must be positive")
        if self.elasticity >= 0: raise ValueError("elasticity must be negative")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    risk: str = "safe"


@dataclass
class Critique:
    score: float
    status: GateStatus
    errors: List[str]
    metrics: Dict[str, float]
    challenge_results: List[Dict[str, Any]]


@dataclass
class Attempt:
    number: int
    proposed_price: float
    reasoning: str
    evidence: Dict[str, Any]
    critique: Optional[Critique] = None


@dataclass
class LoopResult:
    context: MarketContext
    attempts: List[Attempt]
    final_price: Optional[float]
    status: str
    lessons: List[str]
    run_id: str = field(default_factory=lambda: uuid4().hex[:16])
    created_at: float = field(default_factory=time.time)

    def public_dict(self) -> Dict[str, Any]: return asdict(self)
    def audit_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.public_dict(), sort_keys=True, default=str).encode()).hexdigest()