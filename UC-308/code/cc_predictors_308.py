"""
UC-308 — Champion/Challenger predictor adapters.

Duck-typed, injectable predictor adapters. No network access, no tight coupling
with UC-315 imports. A UC-315 skill can be wrapped by passing its executor or the
skill object itself.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from cc_models_308 import MarketEvent, ModelRegistration, Prediction


@runtime_checkable
class PredictorAdapter(Protocol):
    """Duck-typed interface for any bid/ask predictor."""

    model_id: str
    version: str

    def predict(
        self,
        event: MarketEvent,
        correlation_id: str,
        prediction_ts: float,
    ) -> Prediction:
        ...


class ChampionDemoPredictor:
    """Deterministic demo predictor representing the current champion."""

    model_id = "champion_demo"
    version = "1.0.0"

    def __init__(self, bid_noise_std: float = 0.02, ask_noise_std: float = 0.02):
        self.bid_noise_std = bid_noise_std
        self.ask_noise_std = ask_noise_std

    def predict(
        self,
        event: MarketEvent,
        correlation_id: str,
        prediction_ts: float,
    ) -> Prediction:
        rng = random.Random(int(event.event_hash()[:16], 16))
        predicted_bid = event.reference_bid + rng.gauss(0.0, self.bid_noise_std)
        predicted_ask = event.reference_ask + rng.gauss(0.0, self.ask_noise_std)
        return Prediction(
            model_id=self.model_id,
            version=self.version,
            event_id=event.event_id,
            correlation_id=correlation_id,
            predicted_bid=round(predicted_bid, 6),
            predicted_ask=round(predicted_ask, 6),
            confidence=0.75,
            prediction_ts=prediction_ts,
            input_hash=event.event_hash(),
            latency_ms=round(rng.uniform(1.0, 5.0), 3),
        )


class ChallengerDemoPredictor:
    """Deterministic demo predictor representing a challenger (smaller noise)."""

    model_id = "challenger_demo"
    version = "2.0.0"

    def __init__(self, bid_noise_std: float = 0.005, ask_noise_std: float = 0.005):
        self.bid_noise_std = bid_noise_std
        self.ask_noise_std = ask_noise_std

    def predict(
        self,
        event: MarketEvent,
        correlation_id: str,
        prediction_ts: float,
    ) -> Prediction:
        rng = random.Random(int(event.event_hash()[:16], 16) + 1)
        predicted_bid = event.reference_bid + rng.gauss(0.0, self.bid_noise_std)
        predicted_ask = event.reference_ask + rng.gauss(0.0, self.ask_noise_std)
        return Prediction(
            model_id=self.model_id,
            version=self.version,
            event_id=event.event_id,
            correlation_id=correlation_id,
            predicted_bid=round(predicted_bid, 6),
            predicted_ask=round(predicted_ask, 6),
            confidence=0.82,
            prediction_ts=prediction_ts,
            input_hash=event.event_hash(),
            latency_ms=round(rng.uniform(1.0, 5.0), 3),
        )


class UC315SkillPredictorAdapter:
    """Wrap any UC-315 skill object or executor callable.

    The wrapped object must be callable or expose a callable `.executor`.
    It receives at least `{"symbol": event.symbol}` and returns a dict with
    `predicted_bid`, `predicted_ask` and optionally `confidence`.
    """

    def __init__(
        self,
        skill_or_executor: Any,
        model_id: str,
        version: str,
        latency_ms: float = 10.0,
    ):
        self._skill = skill_or_executor
        self.model_id = model_id
        self.version = version
        self.latency_ms = latency_ms

    def _call_executor(self, symbol: str) -> Dict[str, Any]:
        executor: Optional[Callable[..., Any]] = None
        if callable(self._skill):
            executor = self._skill
        else:
            executor = getattr(self._skill, "executor", None)
        if executor is None:
            raise TypeError(f"UC-315 adapter: no callable executor found in {type(self._skill)}")
        # Accept either executor(inputs, domain) or executor(inputs)
        try:
            result = executor({"symbol": symbol}, "trading")
        except TypeError:
            result = executor({"symbol": symbol})
        if not isinstance(result, dict):
            raise ValueError(f"UC-315 adapter: executor returned non-dict: {type(result)}")
        return result

    def predict(
        self,
        event: MarketEvent,
        correlation_id: str,
        prediction_ts: float,
    ) -> Prediction:
        result = self._call_executor(event.symbol)
        predicted_bid = float(result.get("predicted_bid", event.bid))
        predicted_ask = float(result.get("predicted_ask", event.ask))
        confidence = result.get("confidence")
        if confidence is not None:
            confidence = float(confidence)
        return Prediction(
            model_id=self.model_id,
            version=self.version,
            event_id=event.event_id,
            correlation_id=correlation_id,
            predicted_bid=round(predicted_bid, 6),
            predicted_ask=round(predicted_ask, 6),
            confidence=confidence,
            prediction_ts=prediction_ts,
            input_hash=event.event_hash(),
            latency_ms=self.latency_ms,
        )


def make_demo_predictors() -> Tuple[PredictorAdapter, PredictorAdapter]:
    """Return a deterministic (champion, challenger) pair for demos/tests."""
    return ChampionDemoPredictor(), ChallengerDemoPredictor()
