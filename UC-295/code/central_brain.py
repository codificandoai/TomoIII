"""Cerebro central de UC-292.

El `CentralBrain` es la interfaz única a través de la cual todos los agentes
especializados consultan el estado del mundo, las creencias, predicciones de
precios, estimaciones empíricas y contexto de riesgo. Aisla a los agentes de la
implementación interna del world model y del pipeline de percepción.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import AppConfig, get_config
from models import AgentAction, BeliefState, MarketSnapshot, MarketTick, TradingRequest, WorldModelState, now_iso
from perception import MarketPerceptionPipeline
from world_model import TradingWorldModel


class CentralBrain:
    """Cerebro central: world model + percepción + estado compartido."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        world_model: Optional[TradingWorldModel] = None,
        perception_pipeline: Optional[MarketPerceptionPipeline] = None,
    ) -> None:
        self.config = config or get_config()
        self.world_model = world_model or TradingWorldModel(
            self.config.model, app_config=self.config
        )
        self.perception = perception_pipeline or MarketPerceptionPipeline(
            self.config.market, self.config.features
        )
        self.snapshots: Dict[str, MarketSnapshot] = {}
        self.beliefs: Dict[str, BeliefState] = {}
        self.last_predictions: Dict[str, Dict[str, Any]] = {}
        self.latest_request_id: str = ""

    # ------------------------------------------------------------------
    # Observación y actualización del estado compartido
    # ------------------------------------------------------------------
    def observe(self, request: TradingRequest) -> Dict[str, MarketSnapshot]:
        """Procesa la solicitud, actualiza snapshots, historial y creencias."""
        ticks_by_symbol: Dict[str, Any] = {}
        for tick in request.ticks:
            ticks_by_symbol.setdefault(tick.symbol, []).append(tick)
        self.snapshots = self.perception.perceive(
            request_id=request.request_id,
            ticks_by_symbol=ticks_by_symbol,
            news=request.news,
        )
        self.latest_request_id = request.request_id
        for symbol, snapshot in self.snapshots.items():
            # Alimentar todo el historial de ticks al world model, no solo el último,
            # para que la estimación empírica de retorno sea más informativa.
            for tick in sorted(ticks_by_symbol.get(symbol, []), key=lambda t: t.timestamp):
                self.world_model.update_price_history(symbol, tick.last_price)
            if symbol not in self.beliefs:
                self.beliefs[symbol] = self.world_model.initialize_belief(symbol)
            self.beliefs[symbol] = self.world_model.update_belief(
                self.beliefs[symbol],
                snapshot.latest_price,
                snapshot.features.volatility,
            )
        return self.snapshots

    # ------------------------------------------------------------------
    # Consultas de agentes
    # ------------------------------------------------------------------
    def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        return self.snapshots.get(symbol)

    def get_belief(self, symbol: str) -> Optional[BeliefState]:
        return self.beliefs.get(symbol)

    def get_regime(self, symbol: str) -> str:
        snap = self.snapshots.get(symbol)
        return snap.regime if snap else "unknown"

    def get_sentiment(self, symbol: str) -> float:
        snap = self.snapshots.get(symbol)
        return snap.news_sentiment if snap else 0.0

    def get_uncertainty(self, symbol: str) -> float:
        return self.world_model.last_uncertainty

    def predict_next_price(self, symbol: str) -> Dict[str, Any]:
        """Predicción del siguiente tick para un símbolo observado."""
        snap = self.snapshots.get(symbol)
        if snap is None:
            return self.world_model.predict_next_price(symbol, 0.0)
        features = snap.features.to_dict()
        prediction = self.world_model.predict_next_price(
            symbol, snap.latest_price, features
        )
        self.last_predictions[symbol] = prediction
        return prediction

    def predict_action_outcome(
        self, state: WorldModelState, action: AgentAction
    ) -> Dict[str, Any]:
        """Consulta el world model para una transición (s, a)."""
        transition = self.world_model.predict_transition(state, action)
        return transition.to_dict()

    def get_empirical_estimate(self, symbol: str, side: str = "BUY") -> Dict[str, Any]:
        return self.world_model._get_estimate(symbol, side).to_dict()

    def get_risk_context(self, symbol: str) -> Dict[str, Any]:
        """Contexto de riesgo basado en el cerebro."""
        snap = self.snapshots.get(symbol)
        if snap is None:
            return {"volatility": 0.0, "regime": "unknown", "uncertainty": 1.0}
        return {
            "volatility": snap.features.volatility,
            "regime": snap.regime,
            "uncertainty": self.world_model.last_uncertainty,
            "latest_price": snap.latest_price,
            "atr": snap.features.atr,
            "rsi": snap.features.rsi,
        }

    def get_context(self, symbol: str) -> Dict[str, Any]:
        """Devuelve el contexto completo que cualquier agente puede consultar."""
        snap = self.snapshots.get(symbol)
        belief = self.beliefs.get(symbol)
        return {
            "symbol": symbol,
            "request_id": self.latest_request_id,
            "snapshot": snap.to_dict() if snap else None,
            "belief": belief.to_dict() if belief else None,
            "regime": self.get_regime(symbol),
            "sentiment": self.get_sentiment(symbol),
            "uncertainty": self.get_uncertainty(symbol),
            "price_prediction": self.predict_next_price(symbol),
            "empirical_estimate": self.get_empirical_estimate(symbol),
            "risk_context": self.get_risk_context(symbol),
            "world_model": self.world_model.to_dict(),
        }

    # ------------------------------------------------------------------
    # Aprendizaje centralizado
    # ------------------------------------------------------------------
    def learn_from_tick(
        self, symbol: str, current_price: float, next_price: float
    ) -> None:
        # Observar el tick actual para disponer de features técnicos actualizadas
        self.observe(
            TradingRequest(
                symbols=[symbol],
                ticks=[
                    MarketTick(
                        timestamp=now_iso(),
                        symbol=symbol,
                        bid=current_price,
                        ask=current_price,
                        last_price=current_price,
                    )
                ],
            )
        )
        features = (
            self.snapshots[symbol].features.to_dict()
            if symbol in self.snapshots
            else {}
        )
        self.world_model.update_from_tick(
            symbol, current_price, next_price, features=features
        )

    def learn_from_observation(self, observation: Any) -> None:
        from models import WorldModelObservation

        if not isinstance(observation, WorldModelObservation):
            observation = WorldModelObservation(**observation)
        self.world_model.update_from_observation(observation)

    # ------------------------------------------------------------------
    # Estado serializable del cerebro
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.latest_request_id,
            "symbols": list(self.snapshots.keys()),
            "snapshots": {s: snap.to_dict() for s, snap in self.snapshots.items()},
            "beliefs": {s: belief.to_dict() for s, belief in self.beliefs.items()},
            "last_predictions": self.last_predictions,
            "world_model": self.world_model.to_dict(),
        }
