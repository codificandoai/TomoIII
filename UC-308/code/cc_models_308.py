"""
UC-308 — Champion/Challenger experiment models and canonical market events.

All data structures are pure, serializable and version-aware. Market events are
immutable by convention: the orchestrator never mutates an event after creation;
outcomes and predictions are recorded as separate records.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ExperimentState(str, Enum):
    """Lifecycle of a Champion/Challenger experiment."""

    DRAFT = "draft"
    HISTORICAL = "historical"
    WALK_FORWARD = "walk_forward"
    SHADOW = "shadow"
    PAPER = "paper"
    AWAITING_APPROVAL = "awaiting_approval"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    STOPPED = "stopped"
    CONTAINED = "contained"


class PromotionAction(str, Enum):
    PROMOTE = "promote"
    REJECT = "reject"
    CONTINUE = "continue"
    CONTAIN = "contain"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderState(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class MarketEvent:
    """Canonical market event fan-out object.

    Both champion and challenger receive exactly the same object (or a copy) and
    the same hash. The event carries hidden reference prices used for offline
    prediction-quality metrics. In a production wiring reference prices come
    from a future realization or official fix, never from the live feed itself.
    """

    event_id: str
    source_ts: float
    receive_ts: float
    symbol: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    # Reference future/true prices for offline metric computation.
    reference_bid: float
    reference_ask: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_ts": self.source_ts,
            "receive_ts": self.receive_ts,
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "reference_bid": self.reference_bid,
            "reference_ask": self.reference_ask,
            "metadata": self.metadata,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str)

    def event_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    def validate(self, last_source_ts: Optional[float] = None) -> Tuple[bool, str]:
        if not self.event_id or not isinstance(self.event_id, str):
            return False, "event_id missing"
        if self.source_ts <= 0:
            return False, "invalid source_ts"
        if self.receive_ts < self.source_ts:
            return False, "receive_ts before source_ts"
        if last_source_ts is not None and self.source_ts <= last_source_ts:
            return False, "stale or out-of-order source_ts"
        if self.bid <= 0 or self.ask <= 0:
            return False, "non-positive price"
        if self.bid >= self.ask:
            return False, "invalid spread: bid >= ask"
        if self.bid_size <= 0 or self.ask_size <= 0:
            return False, "non-positive liquidity"
        if self.reference_bid <= 0 or self.reference_ask <= 0 or self.reference_bid >= self.reference_ask:
            return False, "invalid reference prices"
        return True, ""


@dataclass
class ModelRegistration:
    model_id: str
    version: str
    role: str  # 'champion' | 'challenger'
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)

    def key(self) -> str:
        return f"{self.model_id}:{self.version}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "role": self.role,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
        }


@dataclass
class Prediction:
    model_id: str
    version: str
    event_id: str
    correlation_id: str
    predicted_bid: float
    predicted_ask: float
    confidence: Optional[float]
    prediction_ts: float
    input_hash: str
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "predicted_bid": self.predicted_bid,
            "predicted_ask": self.predicted_ask,
            "confidence": self.confidence,
            "prediction_ts": self.prediction_ts,
            "input_hash": self.input_hash,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


@dataclass
class PaperFill:
    fill_id: str
    order_id: str
    side: str
    quantity: float
    price: float
    expected_price: float
    slippage: float
    fee: float
    latency_ms: float
    fill_ts: float
    partial: bool
    available_liquidity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "expected_price": self.expected_price,
            "slippage": self.slippage,
            "fee": self.fee,
            "latency_ms": self.latency_ms,
            "fill_ts": self.fill_ts,
            "partial": self.partial,
            "available_liquidity": self.available_liquidity,
        }


@dataclass
class PaperOrder:
    order_id: str
    model_id: str
    version: str
    event_id: str
    side: str
    quantity: float
    order_type: str
    limit_price: float
    state: str = OrderState.PENDING.value
    filled_qty: float = 0.0
    avg_fill_price: float = 0.0
    expected_price: float = 0.0
    total_slippage: float = 0.0
    total_fees: float = 0.0
    total_latency_ms: float = 0.0
    created_ts: float = field(default_factory=time.time)
    fills: List[PaperFill] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "model_id": self.model_id,
            "version": self.version,
            "event_id": self.event_id,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "state": self.state,
            "filled_qty": self.filled_qty,
            "avg_fill_price": self.avg_fill_price,
            "expected_price": self.expected_price,
            "total_slippage": self.total_slippage,
            "total_fees": self.total_fees,
            "total_latency_ms": self.total_latency_ms,
            "created_ts": self.created_ts,
            "fills": [f.to_dict() for f in self.fills],
        }


@dataclass
class PortfolioSnapshot:
    cash: float
    position: float
    market_price: float
    market_value: float
    avg_entry_price: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    exposure: float
    drawdown: float
    max_drawdown: float
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cash": self.cash,
            "position": self.position,
            "market_price": self.market_price,
            "market_value": self.market_value,
            "avg_entry_price": self.avg_entry_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "exposure": self.exposure,
            "drawdown": self.drawdown,
            "max_drawdown": self.max_drawdown,
            "timestamp": self.timestamp,
        }


@dataclass
class StageMetrics:
    stage: str
    sample_count: int
    bid_mae: float = 0.0
    bid_rmse: float = 0.0
    ask_mae: float = 0.0
    ask_rmse: float = 0.0
    mid_accuracy: float = 0.0
    directional_accuracy: float = 0.0
    calibration_brier: Optional[float] = None
    fill_ratio: float = 0.0
    avg_slippage: float = 0.0
    implementation_shortfall: float = 0.0
    spread_capture: float = 0.0
    avg_latency_ms: float = 0.0
    total_fees: float = 0.0
    total_pnl: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    var_95: float = 0.0
    avg_exposure: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "sample_count": self.sample_count,
            "bid_mae": self.bid_mae,
            "bid_rmse": self.bid_rmse,
            "ask_mae": self.ask_mae,
            "ask_rmse": self.ask_rmse,
            "mid_accuracy": self.mid_accuracy,
            "directional_accuracy": self.directional_accuracy,
            "calibration_brier": self.calibration_brier,
            "fill_ratio": self.fill_ratio,
            "avg_slippage": self.avg_slippage,
            "implementation_shortfall": self.implementation_shortfall,
            "spread_capture": self.spread_capture,
            "avg_latency_ms": self.avg_latency_ms,
            "total_fees": self.total_fees,
            "total_pnl": self.total_pnl,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "avg_exposure": self.avg_exposure,
            "timestamp": self.timestamp,
        }


@dataclass
class PromotionRecommendation:
    experiment_id: str
    report_hash: str
    state: str
    recommended_action: str
    reason: str
    champion_version: str
    challenger_version: str
    metrics_summary: Dict[str, Any] = field(default_factory=dict)
    confidence_intervals: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    approved: bool = False
    approval_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "report_hash": self.report_hash,
            "state": self.state,
            "recommended_action": self.recommended_action,
            "reason": self.reason,
            "champion_version": self.champion_version,
            "challenger_version": self.challenger_version,
            "metrics_summary": self.metrics_summary,
            "confidence_intervals": self.confidence_intervals,
            "timestamp": self.timestamp,
            "approved": self.approved,
            "approval_info": self.approval_info,
        }


@dataclass
class ExperimentConfig:
    experiment_id: Optional[str] = None
    symbol: str = "DEMO"
    initial_cash: float = 1_000_000.0
    max_position: float = 1000.0
    max_exposure: float = 200_000.0
    max_drawdown: float = 0.10
    fee_rate: float = 0.001
    base_latency_ms: float = 5.0
    slippage_model: str = "linear"
    min_paired_samples: int = 30
    walk_forward_samples: int = 30
    shadow_samples: int = 30
    paper_samples: int = 30
    bootstrap_iterations: int = 2000
    bootstrap_seed: int = 42
    confidence_level: float = 0.95
    practical_effect_threshold: float = 0.0001
    non_inferiority_threshold: float = -0.00005
    superiority_threshold: float = 0.0001
    risk_free_return: float = 0.0
    allowed_states: List[str] = field(default_factory=lambda: [s.value for s in ExperimentState])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "symbol": self.symbol,
            "initial_cash": self.initial_cash,
            "max_position": self.max_position,
            "max_exposure": self.max_exposure,
            "max_drawdown": self.max_drawdown,
            "fee_rate": self.fee_rate,
            "base_latency_ms": self.base_latency_ms,
            "slippage_model": self.slippage_model,
            "min_paired_samples": self.min_paired_samples,
            "walk_forward_samples": self.walk_forward_samples,
            "shadow_samples": self.shadow_samples,
            "paper_samples": self.paper_samples,
            "bootstrap_iterations": self.bootstrap_iterations,
            "bootstrap_seed": self.bootstrap_seed,
            "confidence_level": self.confidence_level,
            "practical_effect_threshold": self.practical_effect_threshold,
            "non_inferiority_threshold": self.non_inferiority_threshold,
            "superiority_threshold": self.superiority_threshold,
            "risk_free_return": self.risk_free_return,
        }


@dataclass
class AuditNode:
    """One link in the immutable local audit hash chain."""

    entry_type: str
    seq: int
    data: Dict[str, Any]
    previous_hash: str
    current_hash: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_type": self.entry_type,
            "seq": self.seq,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "timestamp": self.timestamp,
        }
