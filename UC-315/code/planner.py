"""Generador de estrategias candidatas y planificación para UC-292."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import AppConfig, ModelConfig, get_config
from models import AgentAction, CandidateStrategy, TradingRequest, WorldModelState
from mcts import MCTSPlanner
from world_model import TradingWorldModel


class StrategyGenerator:
    """Genera estrategias candidatas de trading (heurísticas + MCTS)."""

    _SIZES = [0.03, 0.10, 0.20]

    def __init__(
        self,
        world_model: TradingWorldModel,
        config: ModelConfig,
    ) -> None:
        self.world_model = world_model
        self.config = config

    def generate(
        self,
        request: TradingRequest,
        snapshots: Dict[str, Any],
        portfolio: Dict[str, Any],
        num_strategies: Optional[int] = None,
    ) -> Tuple[List[List[AgentAction]], Dict[str, Any]]:
        """Devuelve secuencias de acciones candidatas por símbolo."""
        num_strategies = num_strategies or self.config.num_candidate_strategies
        symbols = request.symbols or list(snapshots.keys())
        if not symbols:
            return [], {"error": "No symbols provided"}

        candidates: List[List[AgentAction]] = []
        strategies_meta = ["hold", "momentum_buy", "momentum_sell", "mean_reversion_buy", "mean_reversion_sell", "mcts"]

        for symbol in symbols:
            snapshot = snapshots.get(symbol) or {}
            price = snapshot.get("latest_price", 0.0)
            features = snapshot.get("features") or {}
            regime = snapshot.get("regime", "unknown")
            cash = portfolio.get("cash", 100_000.0)
            position = portfolio.get("positions", {}).get(symbol, 0.0)

            hold = [AgentAction(symbol=symbol, side="HOLD", quantity=0.0, price=price, action_type="ORDER", metadata={"strategy": "hold"})]
            candidates.append(hold)

            # Estrategias heurísticas simples
            for size_pct in self._SIZES[:2]:
                for side, label in [("BUY", "momentum_buy"), ("SELL", "momentum_sell")]:
                    qty = self._sizing(side, cash, position, price, size_pct)
                    candidates.append([
                        AgentAction(
                            symbol=symbol,
                            side=side,
                            quantity=qty,
                            price=price,
                            action_type="ORDER",
                            metadata={"strategy": label, "size_pct": size_pct},
                        )
                    ])

            # MCTS: acciones discretas por horizonte
            mcts_plan = self._mcts_plan(symbol, price, cash, position, features, regime)
            if mcts_plan:
                candidates.append(mcts_plan)

        # Limitar a num_strategies pedido
        if len(candidates) > num_strategies:
            rng = np.random.default_rng(hash(request.request_id) % 2**32)
            selected = rng.choice(len(candidates), size=num_strategies, replace=False)
            candidates = [candidates[i] for i in selected]

        return candidates, {"strategies": strategies_meta, "generated": len(candidates)}

    def _sizing(self, side: str, cash: float, position: float, price: float, size_pct: float) -> float:
        if price <= 0:
            return 0.0
        if side == "BUY":
            return round((cash * size_pct) / price, 6)
        return round(position * size_pct, 6)

    def _mcts_plan(
        self,
        symbol: str,
        price: float,
        cash: float,
        position: float,
        features: Dict[str, Any],
        regime: str,
    ) -> List[AgentAction]:
        from mcts import MCTSNode

        initial_state = WorldModelState(
            symbol=symbol,
            price=price,
            cash=cash,
            position=position,
            features=features,
            portfolio_value=cash + position * price,
        )
        # Niveles de acciones: para un horizonte pequeño se repiten opciones
        levels = []
        for _ in range(self.config.horizon):
            level_actions = [
                AgentAction(symbol=symbol, side="HOLD", quantity=0.0, price=price, action_type="ORDER"),
                AgentAction(symbol=symbol, side="BUY", quantity=round(0.05 * cash / max(price, 1e-6), 6), price=price, action_type="ORDER"),
                AgentAction(symbol=symbol, side="SELL", quantity=round(0.05 * position, 6), price=price, action_type="ORDER"),
            ]
            levels.append(level_actions)
        mcts = MCTSPlanner(self.world_model, self.config.mcts)
        try:
            plan = mcts.search(initial_state, levels)
        except Exception:
            plan = []
        if plan:
            return [AgentAction(**{**a.to_dict(), "metadata": {"strategy": "mcts"}}) for a in plan]
        return []


def candidate_to_strategy(
    actions: List[AgentAction],
    name: str,
    expected_return: float = 0.0,
    expected_risk: float = 0.0,
    reasoning: str = "",
) -> CandidateStrategy:
    return CandidateStrategy(
        name=name,
        actions=actions,
        expected_return=expected_return,
        expected_risk=expected_risk,
        reasoning=reasoning,
    )
