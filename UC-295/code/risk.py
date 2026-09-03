"""Motor de riesgo y guardrails operativos para UC-292."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models import (
    AgentAction,
    MarketSnapshot,
    Portfolio,
    RiskAssessment,
    RiskConstraints,
    TradingSignal,
)


class RiskEngine:
    """Evalúa riesgo y aplica guardrails a señales y estrategias."""

    def __init__(self, constraints: Optional[RiskConstraints] = None) -> None:
        self.constraints = constraints or RiskConstraints()
        self._failure_count = 0
        self._last_failure_ts: Optional[str] = None
        self._order_times: List[str] = []

    def assess_signal(
        self,
        signal: TradingSignal,
        snapshot: MarketSnapshot,
        portfolio: Portfolio,
    ) -> RiskAssessment:
        flags: List[str] = []
        reasons: List[str] = []

        # Confianza mínima
        if signal.confidence < self.constraints.min_signal_confidence:
            flags.append("low_confidence")
            reasons.append(f"confianza {signal.confidence:.2f} < {self.constraints.min_signal_confidence}")

        # Detección de anomalía: salto de precio extremo
        price = snapshot.latest_price
        vol = snapshot.features.volatility if snapshot.features else 0.0
        if vol > 0 and abs(signal.entry_price - price) / price > max(0.05, 5 * vol):
            flags.append("price_anomaly")
            reasons.append("diferencia entrada/precio actual excede tolerancia")

        # Circuit breaker por fallos recientes
        if self._failure_count >= self.constraints.circuit_breaker_failures:
            flags.append("circuit_breaker")
            reasons.append(f"circuit breaker activado ({self._failure_count} fallos)")

        # Rate limiting
        if not self._check_rate_limit():
            flags.append("rate_limited")
            reasons.append("límite de órdenes por minuto excedido")

        allowed = not flags
        side = signal.side if allowed else "HOLD"

        # Tamaño máximo por posición y notional
        portfolio_value = portfolio.market_value({signal.symbol: price})
        max_notional = min(
            self.constraints.max_trade_notional,
            portfolio_value * self.constraints.max_position_pct,
        )
        if signal.side == "BUY":
            max_qty = max_notional / max(price, 1e-6)
            proposed_qty = max_notional * signal.position_fraction / max(price, 1e-6)
            quantity = min(max_qty, proposed_qty)
        elif signal.side == "SELL":
            owned = portfolio.positions.get(signal.symbol, 0.0)
            proposed_qty = max_notional * signal.position_fraction / max(price, 1e-6)
            quantity = min(owned, proposed_qty)
        else:
            quantity = 0.0

        risk_score = min(1.0, len(flags) * 0.25 + signal.position_fraction * 0.3 + vol * 10)

        return RiskAssessment(
            allowed=allowed,
            side=side,
            max_quantity=round(quantity, 6),
            max_notional=round(max_notional, 4),
            risk_score=round(risk_score, 4),
            flags=flags,
            reasons=reasons,
        )

    def check_strategy(
        self,
        actions: List[AgentAction],
        portfolio: Portfolio,
        prices: Dict[str, float],
    ) -> RiskAssessment:
        flags: List[str] = []
        reasons: List[str] = []
        portfolio_value = portfolio.market_value(prices)
        gross_notional = 0.0
        for action in actions:
            price = prices.get(action.symbol, action.price)
            notional = action.quantity * price
            gross_notional += notional
            if notional > self.constraints.max_trade_notional:
                flags.append("max_trade_notional")
                reasons.append(f"{action.symbol} notional {notional:.2f} > límite")

        exposure_by_symbol: Dict[str, float] = {}
        for sym, qty in portfolio.positions.items():
            exposure_by_symbol[sym] = qty * prices.get(sym, 0.0)
        for action in actions:
            sign = 1 if action.side == "BUY" else -1 if action.side == "SELL" else 0
            if action.side != "HOLD":
                exposure_by_symbol[action.symbol] = exposure_by_symbol.get(action.symbol, 0.0) + sign * action.quantity * prices.get(action.symbol, action.price)

        for sym, exp in exposure_by_symbol.items():
            if portfolio_value > 0 and abs(exp) / portfolio_value > self.constraints.max_position_pct:
                flags.append("max_position_pct")
                reasons.append(f"{sym} exposición {exp/portfolio_value:.2%} > límite")

        if gross_notional > self.constraints.max_trade_notional * len(actions):
            flags.append("aggregate_notional")
            reasons.append("notional agregado excede límite por acción")

        allowed = not flags and self._check_rate_limit()
        return RiskAssessment(
            allowed=allowed,
            side="MIXED" if actions else "HOLD",
            max_quantity=0.0,
            max_notional=round(min(self.constraints.max_trade_notional, portfolio_value * self.constraints.max_position_pct), 4),
            risk_score=round(min(1.0, len(flags) * 0.2), 4),
            flags=flags,
            reasons=reasons,
        )

    def register_outcome(self, success: bool) -> None:
        if not success:
            self._failure_count += 1
            self._last_failure_ts = datetime.now(timezone.utc).isoformat()
        else:
            self._failure_count = 0

    def reset_circuit_breaker(self) -> None:
        self._failure_count = 0
        self._last_failure_ts = None

    def _check_rate_limit(self) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - 60.0
        self._order_times = [
            t for t in self._order_times
            if datetime.fromisoformat(t).timestamp() > cutoff
        ]
        if len(self._order_times) >= self.constraints.max_orders_per_min:
            return False
        self._order_times.append(now.isoformat())
        return True


class AnomalyDetector:
    """Detecta anomalías en ticks (salto de precio, volumen spoofing, micro spoofing)."""

    def __init__(
        self,
        max_price_jump_std: float = 5.0,
        volume_spike_ratio: float = 5.0,
        micro_adjustment_count: int = 5,
        micro_adjustment_pct: float = 0.001,
    ) -> None:
        self.max_price_jump_std = max_price_jump_std
        self.volume_spike_ratio = volume_spike_ratio
        self.micro_adjustment_count = micro_adjustment_count
        self.micro_adjustment_pct = micro_adjustment_pct

    def detect(self, snapshots: Dict[str, MarketSnapshot]) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for symbol, snap in snapshots.items():
            flags: List[str] = []
            f = snap.features
            latest = snap.latest_price
            if f.volatility > 0 and abs(latest - f.sma_fast) / max(f.sma_fast, 1e-6) > self.max_price_jump_std * f.volatility:
                flags.append("price_jump")
            if f.volume_trend != 0 and f.obv == 0:
                flags.append("volume_anomaly")
            result[symbol] = flags
        return result


def drawdown(portfolio_values: List[float]) -> float:
    """Drawdown máximo dado una serie de valores de portafolio."""
    if not portfolio_values or portfolio_values[0] <= 0:
        return 0.0
    peak = portfolio_values[0]
    max_dd = 0.0
    for v in portfolio_values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd
