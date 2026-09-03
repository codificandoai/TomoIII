"""Generador de datos sintéticos de mercado para entrenar el world model de UC-292."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, get_config
from market_data import SyntheticMarketDataGenerator
from models import AgentAction, Transition, TradingRequest, WorldModelObservation, WorldModelState
from world_model import TradingWorldModel


class SyntheticTradingDataGenerator:
    """Genera trayectorias sintéticas (s, a, r, s') ejecutando estrategias aleatorias."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.market_gen = SyntheticMarketDataGenerator(config.market, seed=config.market.seed)
        self.rng = np.random.default_rng(config.market.seed + 999)

    def generate_trajectory(
        self,
        symbol: str = "SYNTH",
        n_ticks: int = 100,
        start_price: float = 100.0,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Genera una trayectoria de ticks con acciones aleatorias y resultados."""
        ticks = self.market_gen.generate_ticks(
            symbol=symbol,
            n=n_ticks,
            start_price=start_price,
        )
        transitions: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []

        price = start_price
        cash = 100_000.0
        position = 0.0
        for i, tick in enumerate(ticks[:-1]):
            current_price = tick.last_price
            next_price = ticks[i + 1].last_price
            # Acción aleatoria conservadora
            side = self.rng.choice(["HOLD", "BUY", "SELL"])
            if side == "HOLD":
                qty = 0.0
            else:
                qty = self.rng.uniform(1, 10)

            action = AgentAction(
                symbol=symbol,
                side=side,
                quantity=round(qty, 4),
                price=current_price,
            )

            # Resultado determinista simplificado
            if side == "BUY" and qty * current_price <= cash:
                position += qty
                cash -= qty * current_price
                success = True
            elif side == "SELL" and qty <= position:
                position -= qty
                cash += qty * current_price
                success = True
            else:
                success = False

            pnl = position * (next_price - current_price)
            reward = np.tanh(pnl / 1_000.0)

            prev_state = WorldModelState(
                symbol=symbol,
                price=current_price,
                cash=cash,
                position=position,
                portfolio_value=cash + position * current_price,
            )
            next_state = WorldModelState(
                symbol=symbol,
                price=next_price,
                cash=cash,
                position=position,
                portfolio_value=cash + position * next_price,
            )

            transition = Transition(
                prev_state=prev_state.to_dict(),
                action=action.to_dict(),
                next_state=next_state.to_dict(),
                reward=round(float(reward), 6),
                probability=1.0,
                info={"source": "synthetic", "real_success": success},
            )
            transitions.append(transition.to_dict())

            observations.append({
                "action_type": side,
                "item_id": symbol,
                "symbol": symbol,
                "predicted_success_prob": 0.5,
                "actual_success": success,
                "actual_cost": qty * current_price,
                "reward": transition.reward,
            })

        return transitions, observations

    def generate_batch(
        self,
        n: int = 100,
        symbols: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        symbols = symbols or ["AAPL", "TSLA", "BTC"]
        transitions: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []
        for i in range(n):
            sym = symbols[i % len(symbols)]
            t, o = self.generate_trajectory(symbol=f"{sym}-SYNTH", start_price=100.0 + i * 5.0)
            transitions.extend(t)
            observations.extend(o)
        return transitions, observations
