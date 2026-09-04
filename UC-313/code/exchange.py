"""Simulador de exchange para ejecución de órdenes de UC-292.

No ejecuta órdenes reales; modela slippage, comisiones, validaciones de margen
y actualización de portafolio para los modos paper/sim.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models import AgentAction, ExecutionResult, Portfolio


class ExchangeSimulator:
    """Exchange simulado con liquidez, slippage y comisiones."""

    def __init__(
        self,
        commission_rate: float = 0.001,
        base_slippage_bps: float = 1.0,
        max_slippage_bps: float = 10.0,
        min_qty: float = 1e-6,
    ) -> None:
        self.commission_rate = commission_rate
        self.base_slippage_bps = base_slippage_bps
        self.max_slippage_bps = max_slippage_bps
        self.min_qty = min_qty
        self.last_prices: Dict[str, float] = {}

    def update_price(self, symbol: str, price: float) -> None:
        self.last_prices[symbol] = price

    def get_price(self, symbol: str, default: float = 0.0) -> float:
        return self.last_prices.get(symbol, default)

    def submit_order(
        self,
        action: AgentAction,
        portfolio: Portfolio,
        price: Optional[float] = None,
    ) -> ExecutionResult:
        """Ejecuta una orden sobre el portafolio dado."""
        symbol = action.symbol
        side = action.side.upper()
        qty = action.quantity
        requested_price = price if price is not None else action.price

        if side not in ("BUY", "SELL", "HOLD"):
            return self._reject(action, portfolio, f"invalid_side:{side}")

        if side == "HOLD" or qty <= self.min_qty:
            return ExecutionResult(
                strategy_id=action.metadata.get("strategy_id", ""),
                status="FILLED",
                action=action.to_dict(),
                filled_quantity=0.0,
                fill_price=requested_price,
                fees=0.0,
                slippage=0.0,
                realized_pnl=0.0,
                remaining_cash=portfolio.cash,
                remaining_position=portfolio.positions.get(symbol, 0.0),
                timestamp=now_iso(),
            )

        if requested_price <= 0:
            return self._reject(action, portfolio, "invalid_price")

        # Slippage proporcional a tamaño relativo (mock liquidez)
        size_pressure = min(1.0, qty * requested_price / max(1.0, action.metadata.get("market_notional", 1e6)))
        slippage_bps = min(
            self.max_slippage_bps,
            self.base_slippage_bps + size_pressure * (self.max_slippage_bps - self.base_slippage_bps),
        )
        slippage_factor = slippage_bps / 10_000.0
        fill_price = requested_price * (1.0 + slippage_factor) if side == "BUY" else requested_price * (1.0 - slippage_factor)
        fill_price = round(fill_price, 4)

        notional = qty * fill_price
        commission = notional * self.commission_rate

        current_position = portfolio.positions.get(symbol, 0.0)
        realized_pnl = 0.0

        if side == "BUY":
            max_affordable = portfolio.cash / (fill_price * (1.0 + self.commission_rate))
            fill_qty = min(qty, max_affordable)
            if fill_qty <= self.min_qty:
                return self._reject(action, portfolio, "insufficient_cash")
            cost = fill_qty * fill_price
            portfolio.cash -= cost + commission
            portfolio.positions[symbol] = current_position + fill_qty
        else:  # SELL
            if qty > current_position:
                return self._reject(action, portfolio, "insufficient_shares")
            proceeds = qty * fill_price
            # PnL simplificado: asume costo base = último precio conocido anterior
            prev_price = self.last_prices.get(symbol, fill_price)
            realized_pnl = qty * (fill_price - prev_price)
            portfolio.cash += proceeds - commission
            portfolio.positions[symbol] = current_position - qty
            if abs(portfolio.positions[symbol]) < self.min_qty:
                del portfolio.positions[symbol]

        self.last_prices[symbol] = fill_price

        return ExecutionResult(
            strategy_id=action.metadata.get("strategy_id", ""),
            status="FILLED",
            action=action.to_dict(),
            filled_quantity=fill_qty if side == "BUY" else qty,
            fill_price=fill_price,
            fees=round(commission, 4),
            slippage=round(slippage_bps, 4),
            realized_pnl=round(realized_pnl, 4),
            remaining_cash=round(portfolio.cash, 4),
            remaining_position=round(portfolio.positions.get(symbol, 0.0), 6),
            timestamp=now_iso(),
        )

    def _reject(
        self,
        action: AgentAction,
        portfolio: Portfolio,
        reason: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            strategy_id=action.metadata.get("strategy_id", ""),
            status="REJECTED",
            action=action.to_dict(),
            filled_quantity=0.0,
            fill_price=0.0,
            fees=0.0,
            slippage=0.0,
            realized_pnl=0.0,
            remaining_cash=round(portfolio.cash, 4),
            remaining_position=round(portfolio.positions.get(action.symbol, 0.0), 6),
            timestamp=now_iso(),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
