"""Entorno de mercado bursátil: dinámico, probabilístico, parcialmente observable.

El agente no observa directamente variables ocultas ("whale order", "sentimiento
institucional") y debe actualizar sus creencias y actuar con gestión de riesgo.
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List

from config import EnvironmentConfig
from environments.base import Environment
from models import AgentAction, EnvironmentProperties, Observation, StepResult


class StockMarketEnvironment(Environment):
    """Simulación simple de mercado de acciones."""

    def __init__(self, config: EnvironmentConfig | None = None, seed: int = 42):
        self.config = config or EnvironmentConfig()
        self.rng = random.Random(seed)
        self.price: float = 100.0
        self.volatility: float = self.config.stock_volatility
        self.hidden_whale: bool = False
        self.hidden_sentiment: str = "neutral"  # bullish / neutral / bearish
        self.portfolio: Dict[str, float] = {"cash": 10000.0, "shares": 0.0}
        self.history: List[float] = [self.price]
        self._tick_hidden_state()

    @property
    def properties(self) -> EnvironmentProperties:
        return EnvironmentProperties(
            name="stock_market",
            is_dynamic=True,
            is_deterministic=False,
            is_fully_observable=False,
            is_discrete=False,
            is_episodic=False,
            is_multi_agent=True,
        )

    def get_observation(self) -> Observation:
        return Observation(
            data={
                "price": round(self.price, 4),
                "volatility": self.volatility,
                "cash": round(self.portfolio["cash"], 2),
                "shares": round(self.portfolio["shares"], 4),
                "history": self.history[-20:],
            },
            hidden={
                "whale_order": self.hidden_whale,
                "institutional_sentiment": self.hidden_sentiment,
            },
            confidence=0.55,
            source="market_data_feed",
        )

    def is_valid_action(self, action: Any) -> bool:
        a = action.name if isinstance(action, AgentAction) else str(action)
        return a.lower() in ("hold", "buy_small", "buy_large", "sell_small", "sell_large")

    def step(self, action: Any) -> StepResult:
        action = action.name if isinstance(action, AgentAction) else str(action)
        action = action.lower()
        if not self.is_valid_action(action):
            return StepResult(
                observation=self.get_observation(),
                reward=-1.0,
                done=False,
                info={"error": "invalid_action"},
            )

        # Impacto de la acción sobre el mercado (simulado)
        size = 1.0 if "large" in action else 0.2
        if "buy" in action and self.portfolio["cash"] >= self.price * size * 10:
            self.portfolio["shares"] += size * 10
            self.portfolio["cash"] -= self.price * size * 10
        elif "sell" in action and self.portfolio["shares"] >= size * 10:
            self.portfolio["shares"] -= size * 10
            self.portfolio["cash"] += self.price * size * 10

        self._tick_market()
        pnl = self._portfolio_value() - 10000.0
        reward = pnl / 1000.0  # normalizado
        return StepResult(
            observation=self.get_observation(),
            reward=round(reward, 4),
            done=False,
            info={"action": action, "pnl": round(pnl, 2)},
        )

    def _tick_market(self) -> None:
        self._tick_hidden_state()
        drift = 0.0
        if self.hidden_whale:
            drift = 0.015
        if self.hidden_sentiment == "bullish":
            drift += 0.005
        elif self.hidden_sentiment == "bearish":
            drift -= 0.005
        shock = self.rng.gauss(0, self.volatility)
        self.price = max(1.0, self.price * (1.0 + drift + shock))
        self.history.append(self.price)

    def _tick_hidden_state(self) -> None:
        if self.rng.random() < self.config.stock_hidden_event_prob:
            self.hidden_whale = not self.hidden_whale
        r = self.rng.random()
        if r < 0.33:
            self.hidden_sentiment = "bullish"
        elif r < 0.66:
            self.hidden_sentiment = "bearish"
        else:
            self.hidden_sentiment = "neutral"

    def _portfolio_value(self) -> float:
        return self.portfolio["cash"] + self.portfolio["shares"] * self.price

    def reset(self) -> Observation:
        self.__init__(self.config, seed=42)
        return self.get_observation()

    def get_state(self) -> Dict[str, Any]:
        obs = self.get_observation()
        return {**obs.data, "hidden": obs.hidden}
