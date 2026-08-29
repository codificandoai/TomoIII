"""Shared contracts for synchronized multi-framework agent execution."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List
from uuid import uuid4


class Framework(str, Enum):
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    MAF_AUTOGEN = "maf_autogen"
    GOOGLE_ADK = "google_adk"
    AWS_STRANDS = "aws_strands"


class ExecutionMode(str, Enum):
    SIMULATION = "simulation"
    NATIVE = "native"
    AUTO = "auto"


@dataclass
class MarketState:
    sku: str
    current_price: float
    unit_cost: float
    competitor_price: float
    demand: float
    inventory: float = 10000.0
    elasticity: float = -1.5
    headlines: List[str] = field(default_factory=list)
    version: int = 1
    step: int = 0

    def validate(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku is required")
        if min(self.current_price, self.unit_cost, self.competitor_price, self.demand, self.inventory) < 0:
            raise ValueError("market values cannot be negative")
        if self.current_price == 0 or self.competitor_price == 0:
            raise ValueError("prices must be positive")
        if self.elasticity >= 0:
            raise ValueError("elasticity must be negative")

    @property
    def profit(self) -> float:
        return (self.current_price - self.unit_cost) * min(self.demand, self.inventory)

    def public_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "profit": round(self.profit, 2)}


@dataclass(frozen=True)
class AgentRequest:
    run_id: str
    correlation_id: str
    framework: Framework
    task: str
    state: Dict[str, Any]
    context: Dict[str, Any]
    idempotency_key: str
    deadline: float


@dataclass(frozen=True)
class AgentResponse:
    framework: Framework
    adapter: str
    native: bool
    confidence: float
    proposed_price: float
    sentiment: float
    rationale: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    latency_ms: float = 0.0


@dataclass(frozen=True)
class ConsensusDecision:
    recommended_price: float
    applied_price: float
    confidence: float
    dispersion_rate: float
    action: str
    guardrails: List[str]
    votes: Dict[str, float]


@dataclass
class PipelineRun:
    state_before: Dict[str, Any]
    responses: List[AgentResponse]
    decision: ConsensusDecision
    state_after: Dict[str, Any]
    run_id: str = field(default_factory=lambda: uuid4().hex[:16])
    status: str = "completed"
    created_at: float = field(default_factory=time.time)

    def public_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def audit_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.public_dict(), sort_keys=True, default=str).encode()).hexdigest()