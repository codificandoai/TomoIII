"""Feed sintético de datos de mercado para entrenamiento y backtests de UC-292."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import AppConfig, MarketConfig, get_config
from models import MarketTick


class SyntheticMarketDataGenerator:
    """Genera series de precios sintéticas con volatilidad y eventos ocultos."""

    def __init__(self, config: Optional[MarketConfig] = None, seed: int = 42) -> None:
        self.cfg = config or get_config().market
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

    def generate_ticks(
        self,
        symbol: str,
        n: int = 200,
        start_price: float = 100.0,
        interval_ms: int = 1000,
        base_volatility: float = 0.001,
        drift: float = 0.0001,
        event_prob: float = 0.02,
    ) -> List[MarketTick]:
        """Genera n ticks con movimiento browniano geométrico y shocks."""
        now = datetime.now(timezone.utc)
        ticks: List[MarketTick] = []
        price = float(start_price)
        hidden_event = False
        base_volume = 1_000_000.0

        for i in range(n):
            # Evento oculto (whale) altera temporalmente drift y volatilidad
            if self.rng.random() < event_prob:
                hidden_event = not hidden_event
            event_drift = 0.003 if hidden_event else 0.0
            event_vol = 0.004 if hidden_event else 0.0

            shock = self.np_rng.normal(0, base_volatility + event_vol)
            price *= max(0.01, 1.0 + drift + event_drift + shock)
            spread = price * 0.0002
            bid = price - spread / 2
            ask = price + spread / 2
            volume = max(1, int(base_volume * (1 + self.np_rng.exponential(0.2))))
            vwap = price * (1 + self.np_rng.normal(0, 0.0001))

            ts = now + timedelta(milliseconds=i * interval_ms)
            ticks.append(
                MarketTick(
                    timestamp=ts.isoformat(),
                    symbol=symbol,
                    bid=round(bid, 4),
                    ask=round(ask, 4),
                    bid_size=max(1, int(volume * 0.3)),
                    ask_size=max(1, int(volume * 0.2)),
                    last_price=round(price, 4),
                    volume=volume,
                    vwap=round(vwap, 4),
                )
            )
        return ticks

    def generate_multi_symbol_history(
        self,
        symbols: List[str],
        n: int = 200,
        start_prices: Optional[Dict[str, float]] = None,
        seed: Optional[int] = None,
    ) -> Dict[str, List[MarketTick]]:
        seed = seed or self.cfg.seed
        result: Dict[str, List[MarketTick]] = {}
        for idx, symbol in enumerate(symbols):
            gen = SyntheticMarketDataGenerator(self.cfg, seed=seed + idx)
            price = (start_prices or {}).get(symbol, 100.0 + idx * 20.0)
            result[symbol] = gen.generate_ticks(symbol, n=n, start_price=price)
        return result

    def to_dataframe(self, ticks: List[MarketTick]) -> pd.DataFrame:
        rows = [t.model_dump() for t in ticks]
        return pd.DataFrame(rows)
