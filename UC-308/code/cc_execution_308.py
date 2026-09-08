"""
UC-308 — Paper/simulated execution engine for Champion/Challenger experiments.

This engine has no real order authority. It models spread, fees, slippage,
latency, partial fills, available liquidity, positions, cash, PnL, exposure and
drawdown with deterministic RNG. Champion and challenger receive identical market
events and run under common execution assumptions.
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from cc_models_308 import (
    MarketEvent,
    OrderSide,
    OrderState,
    PaperFill,
    PaperOrder,
    PortfolioSnapshot,
    Prediction,
)


def _slippage_linear(
    quantity: float,
    liquidity: float,
    spread: float,
    rng: random.Random,
) -> float:
    if liquidity <= 0:
        return spread * 2.0
    fill_fraction = min(quantity / liquidity, 1.0)
    return spread * (0.1 + 0.9 * fill_fraction) * (1.0 + rng.uniform(-0.05, 0.05))


def _make_rng(seed: int) -> random.Random:
    return random.Random(seed)


def _order_seed(event: MarketEvent, model_key: str) -> int:
    return int(hashlib_seed(event.event_hash(), model_key), 16) % (2**32)


def hashlib_seed(h1: str, h2: str) -> str:
    import hashlib
    return hashlib.sha256(f"{h1}:{h2}".encode()).hexdigest()


class PaperExecutionEngine:
    """Simulated execution with common assumptions across champion/challenger."""

    def __init__(
        self,
        model_id: str,
        version: str,
        initial_cash: float = 1_000_000.0,
        fee_rate: float = 0.001,
        base_latency_ms: float = 5.0,
        slippage_model: str = "linear",
        max_position: float = 1000.0,
        max_exposure: float = 200_000.0,
        default_quantity: float = 100.0,
    ):
        self.model_id = model_id
        self.version = version
        self.initial_cash = initial_cash
        self.fee_rate = fee_rate
        self.base_latency_ms = base_latency_ms
        self.slippage_model = slippage_model
        self.max_position = max_position
        self.max_exposure = max_exposure
        self.default_quantity = default_quantity

        self.cash = initial_cash
        self.position = 0.0
        self.avg_entry_price = 0.0
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        self.total_latency_ms = 0.0
        self.peak_equity = initial_cash
        self.max_drawdown = 0.0
        self.pending_orders: List[PaperOrder] = []
        self.filled_orders: List[PaperOrder] = []
        self._canceled_order_ids: set = set()
        self.equity_curve: List[Tuple[float, float]] = []  # (timestamp, equity)
        self._last_price = 0.0

    @property
    def exposure(self) -> float:
        return abs(self.position) * self._last_price

    @property
    def _last_market_price(self) -> float:
        return self._last_price

    def _compute_slippage(self, quantity: float, liquidity: float, spread: float, rng: random.Random) -> float:
        if self.slippage_model == "linear":
            return _slippage_linear(quantity, liquidity, spread, rng)
        return _slippage_linear(quantity, liquidity, spread, rng)

    def _signal(self, event: MarketEvent, prediction: Prediction) -> Tuple[str, float]:
        predicted_mid = (prediction.predicted_bid + prediction.predicted_ask) / 2.0
        current_mid = event.mid
        if predicted_mid > current_mid:
            side = OrderSide.BUY.value
        elif predicted_mid < current_mid:
            side = OrderSide.SELL.value
        else:
            side = OrderSide.HOLD.value

        if side == OrderSide.HOLD.value:
            return side, 0.0

        # Cap quantity by remaining room under max position/exposure.
        qty = self.default_quantity
        if side == OrderSide.BUY.value:
            max_by_position = self.max_position - self.position
            max_by_exposure = (self.max_exposure / event.ask) - self.position
            qty = min(qty, max_by_position, max_by_exposure, self.cash / event.ask)
        else:
            max_by_position = self.position + self.max_position
            max_by_exposure = (self.max_exposure / event.bid) + self.position
            qty = min(qty, max_by_position, max_by_exposure)

        qty = max(0.0, round(qty, 6))
        return side, qty

    def create_order(self, event: MarketEvent, prediction: Prediction) -> Optional[PaperOrder]:
        side, qty = self._signal(event, prediction)
        if side == OrderSide.HOLD.value or qty <= 0.0:
            return None
        expected_price = event.ask if side == OrderSide.BUY.value else event.bid
        order = PaperOrder(
            order_id=f"ORD-{uuid.uuid4().hex[:12]}",
            model_id=self.model_id,
            version=self.version,
            event_id=event.event_id,
            side=side,
            quantity=qty,
            order_type="market",
            limit_price=expected_price,
            expected_price=expected_price,
            created_ts=time.time(),
        )
        self.pending_orders.append(order)
        return order

    def fill_order(self, order: PaperOrder, event: MarketEvent) -> PaperOrder:
        """Fill or partially fill an order against the current event liquidity."""
        if order.order_id in self._canceled_order_ids:
            order.state = OrderState.CANCELLED.value
            return order

        rng = _make_rng(_order_seed(event, "common-execution-assumptions"))
        side = order.side
        quantity_remaining = order.quantity - order.filled_qty
        if quantity_remaining <= 0.0:
            order.state = OrderState.FILLED.value
            return order

        available = event.ask_size if side == OrderSide.BUY.value else event.bid_size
        fill_qty = min(quantity_remaining, available)
        partial = fill_qty < quantity_remaining

        raw_price = event.ask if side == OrderSide.BUY.value else event.bid
        slippage = self._compute_slippage(fill_qty, available, event.spread, rng)
        if side == OrderSide.BUY.value:
            fill_price = raw_price + slippage
        else:
            fill_price = raw_price - slippage
        fill_price = round(fill_price, 6)

        notional = fill_qty * fill_price
        fee = notional * self.fee_rate
        latency = self.base_latency_ms + rng.uniform(1.0, 4.0)

        fill = PaperFill(
            fill_id=f"FILL-{uuid.uuid4().hex[:12]}",
            order_id=order.order_id,
            side=side,
            quantity=round(fill_qty, 6),
            price=fill_price,
            expected_price=order.expected_price,
            slippage=round(slippage, 6),
            fee=round(fee, 6),
            latency_ms=round(latency, 3),
            fill_ts=time.time(),
            partial=partial,
            available_liquidity=available,
        )
        order.fills.append(fill)
        order.filled_qty = round(sum(f.quantity for f in order.fills), 6)
        order.total_slippage = round(sum(f.slippage for f in order.fills), 6)
        order.total_fees = round(sum(f.fee for f in order.fills), 6)
        order.total_latency_ms = round(sum(f.latency_ms for f in order.fills), 3)
        order.avg_fill_price = round(
            sum(f.quantity * f.price for f in order.fills) / order.filled_qty, 6
        ) if order.filled_qty > 0 else 0.0
        order.state = OrderState.PARTIAL.value if partial else OrderState.FILLED.value

        # Update portfolio.
        self._apply_fill(side, fill_qty, fill_price, fee)
        self.total_fees += fee
        self.total_slippage += slippage * fill_qty
        self.total_latency_ms += latency

        return order

    def _apply_fill(self, side: str, qty: float, price: float, fee: float) -> None:
        notional = qty * price
        if side == OrderSide.BUY.value:
            # Increase long position; pay cash including fee.
            if self.position >= 0:
                total_cost = (self.position * self.avg_entry_price) + (qty * price)
                self.position += qty
                self.avg_entry_price = total_cost / self.position if self.position > 0 else 0.0
            else:
                # Cover short first.
                cover = min(qty, -self.position)
                self.realized_pnl += cover * (self.avg_entry_price - price) - fee * (cover / qty if qty else 0)
                remaining = qty - cover
                self.position += qty
                if self.position > 0:
                    self.avg_entry_price = price
            self.cash -= notional + fee
        else:
            # Decrease position / go short.
            if self.position > 0:
                sell_from_long = min(qty, self.position)
                self.realized_pnl += sell_from_long * (price - self.avg_entry_price)
                remaining = qty - sell_from_long
                self.position -= qty
                if self.position < 0:
                    self.avg_entry_price = price
            else:
                # Increase short.
                total_short = abs(self.position)
                avg = self.avg_entry_price
                total_value = total_short * avg + qty * price
                self.position -= qty
                if self.position != 0:
                    self.avg_entry_price = total_value / abs(self.position)
            self.cash += notional - fee

        self.cash = round(self.cash, 6)
        self.position = round(self.position, 6)

    def process_event(self, event: MarketEvent, prediction: Prediction) -> Dict[str, Any]:
        """Generate and fill one order for this event, then mark-to-market."""
        order = self.create_order(event, prediction)
        fills: List[PaperFill] = []
        if order is not None:
            filled = self.fill_order(order, event)
            if filled.state != OrderState.PENDING.value:
                self.filled_orders.append(filled)
                self.pending_orders = [o for o in self.pending_orders if o.order_id != filled.order_id]
                fills.extend(filled.fills)

        snapshot = self.mark_to_market(event)
        return {
            "order": order.to_dict() if order else None,
            "fills": [f.to_dict() for f in fills],
            "snapshot": snapshot.to_dict(),
        }

    def mark_to_market(self, event: MarketEvent) -> PortfolioSnapshot:
        price = event.mid
        self._last_price = price
        market_value = self.cash + self.position * price
        self.peak_equity = max(self.peak_equity, market_value)
        drawdown = (self.peak_equity - market_value) / self.peak_equity if self.peak_equity > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, drawdown)
        unrealized = self.position * (price - self.avg_entry_price)
        snapshot = PortfolioSnapshot(
            cash=round(self.cash, 6),
            position=round(self.position, 6),
            market_price=round(price, 6),
            market_value=round(market_value, 6),
            avg_entry_price=round(self.avg_entry_price, 6),
            realized_pnl=round(self.realized_pnl, 6),
            unrealized_pnl=round(unrealized, 6),
            total_pnl=round(self.realized_pnl + unrealized, 6),
            exposure=round(self.exposure, 6),
            drawdown=round(drawdown, 6),
            max_drawdown=round(self.max_drawdown, 6),
            timestamp=time.time(),
        )
        self.equity_curve.append((snapshot.timestamp, snapshot.market_value))
        return snapshot

    def cancel_all_orders(self) -> List[PaperOrder]:
        """Cancel pending paper orders and return them (no real side effects)."""
        canceled = []
        for order in self.pending_orders:
            if order.order_id not in self._canceled_order_ids:
                order.state = OrderState.CANCELLED.value
                self._canceled_order_ids.add(order.order_id)
                canceled.append(order)
        self.pending_orders.clear()
        return canceled

    def snapshot(self) -> PortfolioSnapshot:
        price = self._last_market_price
        market_value = self.cash + self.position * price
        drawdown = (self.peak_equity - market_value) / self.peak_equity if self.peak_equity > 0 else 0.0
        return PortfolioSnapshot(
            cash=round(self.cash, 6),
            position=round(self.position, 6),
            market_price=round(price, 6),
            market_value=round(market_value, 6),
            avg_entry_price=round(self.avg_entry_price, 6),
            realized_pnl=round(self.realized_pnl, 6),
            unrealized_pnl=round(self.position * (price - self.avg_entry_price), 6),
            total_pnl=round(self.realized_pnl + self.position * (price - self.avg_entry_price), 6),
            exposure=round(self.exposure, 6),
            drawdown=round(drawdown, 6),
            max_drawdown=round(self.max_drawdown, 6),
            timestamp=time.time(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "cash": round(self.cash, 6),
            "position": round(self.position, 6),
            "avg_entry_price": round(self.avg_entry_price, 6),
            "realized_pnl": round(self.realized_pnl, 6),
            "total_fees": round(self.total_fees, 6),
            "total_slippage": round(self.total_slippage, 6),
            "total_latency_ms": round(self.total_latency_ms, 3),
            "max_drawdown": round(self.max_drawdown, 6),
            "pending_orders": len(self.pending_orders),
            "filled_orders": len(self.filled_orders),
        }
