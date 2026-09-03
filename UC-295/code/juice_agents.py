"""Juice Agents - Validación de inferencias para UC-292.

Los Juice Agents son agentes especializados que desafían las predicciones y
señales del sistema de trading antes de ejecutar. Si existe un endpoint externo
(JUICE_URL), se envía la inferencia para validación; de lo contrario se ejecuta
un panel local determinista.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from config import JuiceConfig, get_config
from models import JuiceValidationResult, MarketSnapshot, TradingSignal


class JuiceAgent:
    """Agente validador base."""

    name: str = "base"

    def validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> Dict[str, Any]:
        raise NotImplementedError


class JuiceTechnicalAgent(JuiceAgent):
    """Valida coherencia técnica de la señal."""

    name = "technical"

    def validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> Dict[str, Any]:
        f = snapshot.features
        issues: List[str] = []
        score = signal.confidence

        if signal.side == "BUY" and f.rsi > 70:
            issues.append("rsi_overbought")
            score -= 0.2
        if signal.side == "SELL" and f.rsi < 30:
            issues.append("rsi_oversold")
            score -= 0.2
        if signal.side == "BUY" and f.trend_direction < 0:
            issues.append("signal_against_trend")
            score -= 0.15
        if signal.side == "SELL" and f.trend_direction > 0:
            issues.append("signal_against_trend")
            score -= 0.15
        if f.volatility > 0.05:
            issues.append("high_volatility")
            score -= 0.1

        return {
            "agent": self.name,
            "score": max(0.0, min(1.0, score)),
            "issues": issues,
        }


class JuiceSentimentAgent(JuiceAgent):
    """Valida coherencia con sentimiento de noticias."""

    name = "sentiment"

    def validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> Dict[str, Any]:
        issues: List[str] = []
        score = signal.confidence
        sentiment = snapshot.news_sentiment

        if signal.side == "BUY" and sentiment < -0.3:
            issues.append("negative_sentiment_conflicts_buy")
            score -= 0.25
        if signal.side == "SELL" and sentiment > 0.3:
            issues.append("positive_sentiment_conflicts_sell")
            score -= 0.25
        if abs(sentiment) > 0.7:
            score += 0.05
        return {
            "agent": self.name,
            "score": max(0.0, min(1.0, score)),
            "issues": issues,
        }


class JuiceRiskAgent(JuiceAgent):
    """Valida riesgo de la señal."""

    name = "risk"

    def validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> Dict[str, Any]:
        issues: List[str] = []
        score = signal.confidence
        vol = snapshot.features.volatility
        atr = snapshot.features.atr
        price = snapshot.latest_price

        if price > 0 and signal.stop_loss > 0:
            sl_pct = abs(signal.stop_loss - signal.entry_price) / price
            if sl_pct < 0.005:
                issues.append("stop_loss_too_tight")
                score -= 0.1
            if sl_pct > 0.1:
                issues.append("stop_loss_too_wide")
                score -= 0.1
        if vol > 0.03:
            issues.append("elevated_volatility")
            score -= 0.1
        if signal.position_fraction > 0.25:
            issues.append("position_fraction_high")
            score -= 0.15

        return {
            "agent": self.name,
            "score": max(0.0, min(1.0, score)),
            "issues": issues,
        }


class JuiceFundamentalAgent(JuiceAgent):
    """Valida consistencia básica fundamental/macro (mock lookup)."""

    name = "fundamental"

    def validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> Dict[str, Any]:
        # En un sistema real consultaría earnings, FOMC, etc.
        return {
            "agent": self.name,
            "score": signal.confidence,
            "issues": [],
        }


class JuiceValidator:
    """Orquesta los Juice Agents y decide si una inferencia es aprobada."""

    _AGENT_CLASSES: Dict[str, type[JuiceAgent]] = {
        "technical": JuiceTechnicalAgent,
        "sentiment": JuiceSentimentAgent,
        "risk": JuiceRiskAgent,
        "fundamental": JuiceFundamentalAgent,
    }

    def __init__(self, config: Optional[JuiceConfig] = None) -> None:
        self.config = config or get_config().juice
        self.agents: List[JuiceAgent] = [
            self._AGENT_CLASSES[a]() for a in self.config.agents if a in self._AGENT_CLASSES
        ]

    def validate(
        self,
        signal: TradingSignal,
        snapshot: MarketSnapshot,
    ) -> JuiceValidationResult:
        if self.config.enabled and self.config.url:
            return self._external_validate(signal, snapshot)
        return self._local_validate(signal, snapshot)

    def _local_validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> JuiceValidationResult:
        agent_scores: Dict[str, float] = {}
        all_issues: List[str] = []
        for agent in self.agents:
            result = agent.validate(signal, snapshot)
            agent_scores[agent.name] = round(result["score"], 4)
            all_issues.extend(result["issues"])

        if agent_scores:
            consensus = float(np.mean(list(agent_scores.values())))
        else:
            consensus = signal.confidence

        approved = consensus >= 0.55 and not all_issues
        confidence = float(np.std(list(agent_scores.values()))) if agent_scores else 0.0

        return JuiceValidationResult(
            consensus_score=round(consensus, 4),
            approved=approved,
            issues=list(dict.fromkeys(all_issues)),
            agent_scores=agent_scores,
            confidence=round(1.0 - confidence, 4),
            timestamp=now_iso(),
        )

    def _external_validate(self, signal: TradingSignal, snapshot: MarketSnapshot) -> JuiceValidationResult:
        import requests

        try:
            payload = {
                "signal": signal.to_dict(),
                "snapshot": snapshot.to_dict(),
                "agents": self.config.agents,
            }
            resp = requests.post(
                self.config.url,
                json=payload,
                timeout=self.config.timeout,
            )
            data = resp.json()
            return JuiceValidationResult(**data)
        except Exception as exc:
            return JuiceValidationResult(
                consensus_score=0.0,
                approved=False,
                issues=[f"juice_external_error: {exc}"],
                agent_scores={},
                confidence=0.0,
            )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
