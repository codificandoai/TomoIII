"""Agentes especializados del equipo de trading para UC-292."""
from __future__ import annotations

from typing import Dict, List, Optional

from models import AgentAction, MarketSnapshot, Portfolio, RiskConstraints, TradingSignal
from risk import RiskEngine


class PerceptionAgent:
    """Agente sensor: convierte datos brutos en snapshots."""

    def __init__(self, perception_pipeline) -> None:
        self.pipeline = perception_pipeline

    def perceive(self, request) -> Dict[str, MarketSnapshot]:
        from models import MarketTick

        ticks_by_symbol: Dict[str, List[MarketTick]] = {}
        for tick in request.ticks:
            ticks_by_symbol.setdefault(tick.symbol, []).append(tick)
        return self.pipeline.perceive(request.request_id, ticks_by_symbol, request.news)


class TechnicalAnalyst:
    """Agente analista técnico."""

    name = "technical"

    def analyze(self, snapshot: MarketSnapshot) -> TradingSignal:
        f = snapshot.features
        side = "HOLD"
        confidence = 0.5
        reasons: List[str] = []

        if f.rsi < 35 and f.trend_direction > 0:
            side = "BUY"
            confidence = min(1.0, 0.6 + (35 - f.rsi) / 100.0)
            reasons.append(f"RSI {f.rsi:.1f} oversold + uptrend")
        elif f.rsi > 65 and f.trend_direction < 0:
            side = "SELL"
            confidence = min(1.0, 0.6 + (f.rsi - 65) / 100.0)
            reasons.append(f"RSI {f.rsi:.1f} overbought + downtrend")

        if f.macd > f.macd_signal and side in ("BUY", "HOLD"):
            side = "BUY" if side == "HOLD" else side
            confidence += 0.05
            reasons.append("MACD bullish cross")
        elif f.macd < f.macd_signal and side in ("SELL", "HOLD"):
            side = "SELL" if side == "HOLD" else side
            confidence += 0.05
            reasons.append("MACD bearish cross")

        bb = f.bollinger_position
        if side == "BUY" and bb < 0.2:
            confidence += 0.05
            reasons.append("price near lower band")
        if side == "SELL" and bb > 0.8:
            confidence += 0.05
            reasons.append("price near upper band")

        confidence = min(1.0, confidence)

        entry = snapshot.latest_price
        stop = entry * (1 - 0.02) if side == "BUY" else entry * (1 + 0.02) if side == "SELL" else entry
        target = entry * (1 + 0.04) if side == "BUY" else entry * (1 - 0.04) if side == "SELL" else entry

        return TradingSignal(
            symbol=snapshot.symbol,
            side=side,
            confidence=round(confidence, 4),
            entry_price=round(entry, 4),
            stop_loss=round(stop, 4),
            take_profit=round(target, 4),
            position_fraction=0.1,
            time_horizon="short",
            reasoning="; ".join(reasons),
            agent=self.name,
        )


class SentimentAnalyst:
    """Agente analista de sentimiento."""

    name = "sentiment"

    def analyze(self, snapshot: MarketSnapshot) -> TradingSignal:
        sentiment = snapshot.news_sentiment
        side = "HOLD"
        confidence = 0.5
        reasons: List[str] = []

        if sentiment > 0.3:
            side = "BUY"
            confidence = min(1.0, 0.5 + abs(sentiment) * 0.5)
            reasons.append(f"positive sentiment {sentiment:.2f}")
        elif sentiment < -0.3:
            side = "SELL"
            confidence = min(1.0, 0.5 + abs(sentiment) * 0.5)
            reasons.append(f"negative sentiment {sentiment:.2f}")
        else:
            reasons.append(f"neutral sentiment {sentiment:.2f}")

        if snapshot.news_credibility < 0.4:
            confidence *= 0.7
            reasons.append("low source credibility")

        entry = snapshot.latest_price
        return TradingSignal(
            symbol=snapshot.symbol,
            side=side,
            confidence=round(confidence, 4),
            entry_price=round(entry, 4),
            stop_loss=round(entry * 0.98, 4) if side == "BUY" else round(entry * 1.02, 4) if side == "SELL" else entry,
            take_profit=round(entry * 1.04, 4) if side == "BUY" else round(entry * 0.96, 4) if side == "SELL" else entry,
            position_fraction=0.05,
            time_horizon="short",
            reasoning="; ".join(reasons),
            agent=self.name,
        )


class FundamentalAnalyst:
    """Agente analista fundamental/macro (stub para extensión)."""

    name = "fundamental"

    def analyze(self, snapshot: MarketSnapshot) -> TradingSignal:
        # Placeholder: en producción consultaría earnings, FOMC, etc.
        return TradingSignal(
            symbol=snapshot.symbol,
            side="HOLD",
            confidence=0.5,
            entry_price=snapshot.latest_price,
            stop_loss=snapshot.latest_price,
            take_profit=snapshot.latest_price,
            position_fraction=0.0,
            time_horizon="medium",
            reasoning="no fundamental data configured",
            agent=self.name,
        )


class TraderAgent:
    """Agente trader: combina señales de analistas en una propuesta de orden."""

    name = "trader"

    def __init__(self, risk_engine: RiskEngine) -> None:
        self.risk_engine = risk_engine

    def generate_signal(
        self,
        snapshot: MarketSnapshot,
        signals: List[TradingSignal],
        portfolio: Portfolio,
        constraints: RiskConstraints,
    ) -> Optional[AgentAction]:
        if not signals:
            return None

        # Voto ponderado por confianza y credibilidad del agente
        weights = {"technical": 0.35, "sentiment": 0.25, "fundamental": 0.15}
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        entry = snapshot.latest_price

        for signal in signals:
            w = weights.get(signal.agent, 0.1)
            total_weight += w
            if signal.side == "BUY":
                buy_score += w * signal.confidence
            elif signal.side == "SELL":
                sell_score += w * signal.confidence

        if total_weight == 0:
            return None

        if buy_score > sell_score and buy_score / total_weight >= constraints.min_signal_confidence:
            side = "BUY"
            confidence = buy_score / total_weight
        elif sell_score > buy_score and sell_score / total_weight >= constraints.min_signal_confidence:
            side = "SELL"
            confidence = sell_score / total_weight
        else:
            return None

        # Asignar tamaño fraccional conservador
        position_fraction = 0.05 if confidence > 0.7 else 0.03

        # Validar con motor de riesgo
        consolidated = TradingSignal(
            symbol=snapshot.symbol,
            side=side,
            confidence=round(confidence, 4),
            entry_price=round(entry, 4),
            stop_loss=round(entry * (1 - constraints.stop_loss_pct), 4) if side == "BUY" else round(entry * (1 + constraints.stop_loss_pct), 4),
            take_profit=round(entry * (1 + constraints.take_profit_pct), 4) if side == "BUY" else round(entry * (1 - constraints.take_profit_pct), 4),
            position_fraction=position_fraction,
            time_horizon="short",
            reasoning="consensus from analysts",
            agent=self.name,
        )

        assessment = self.risk_engine.assess_signal(consolidated, snapshot, portfolio)
        if not assessment.allowed:
            return None

        qty = min(assessment.max_quantity, (portfolio.cash * position_fraction) / max(entry, 1e-6))
        if side == "SELL":
            qty = min(qty, portfolio.positions.get(snapshot.symbol, 0.0))
        if qty <= 0:
            return None

        return AgentAction(
            symbol=snapshot.symbol,
            side=side,
            quantity=round(qty, 6),
            price=round(entry, 4),
            stop_loss=round(consolidated.stop_loss, 4),
            take_profit=round(consolidated.take_profit, 4),
            confidence=round(confidence, 4),
            metadata={
                "signal": consolidated.to_dict(),
                "risk_assessment": assessment.to_dict(),
            },
        )


class PortfolioManager:
    """Gestor de portafolio: agrupa acciones finales y supervisa exposición."""

    name = "portfolio_manager"

    def __init__(self, risk_engine: RiskEngine) -> None:
        self.risk_engine = risk_engine

    def finalize_actions(
        self,
        proposed: List[AgentAction],
        portfolio: Portfolio,
        prices: Dict[str, float],
    ) -> List[AgentAction]:
        assessment = self.risk_engine.check_strategy(proposed, portfolio, prices)
        if not assessment.allowed:
            return []
        return proposed
