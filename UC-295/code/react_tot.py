"""ReAct Híbrido con Árbol de Pensamientos (Tree of Thoughts - ToT) para predicción
ask/bid del siguiente tick.

UC-295 añade una capa de planificación en grafo sobre el bucle ReAct lineal. En
lugar de pensar "usaré la API 1, luego la 2, luego la 3", el agente expande
varias hipótesis de predicción en paralelo, evalúa cada rama, poda las fallidas y
retrocede (backtracking) hacia predictores de contingencia antes de sintetizar el
veredicto final ask/bid.

Integración con el cerebro AGI existente:
- Un predictor `brain` consume `CentralBrain.predict_next_price()` y convierte la
  predicción de mid-price en ask/bid.
- El resto de predictores (`technical`, `microstructure`, `sentiment`,
  `world_model` simulado, `ensemble`) actúan como APIs alternativas que el
  árbol explora y combina.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from models import MarketTick, NewsItem, TradingRequest
from perception import MarketPerceptionPipeline, NewsPipeline


class PredictorStatus(str, Enum):
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    NO_RESULTS = "NO_RESULTS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class ToTNodeState(str, Enum):
    PENDING = "PENDING"
    EXPLORING = "EXPLORING"
    SUCCESS = "SUCCESS"
    PRUNED_FAILED = "PRUNED_FAILED"
    BACKTRACKED = "BACKTRACKED"


@dataclass
class PredictorResult:
    """Resultado de consultar una API / predictor de ticks."""

    source: str
    predicted_ask: float
    predicted_bid: float
    confidence: float
    status: PredictorStatus = PredictorStatus.SUCCESS
    latency_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "predicted_ask": round(self.predicted_ask, 6),
            "predicted_bid": round(self.predicted_bid, 6),
            "predicted_mid": round((self.predicted_ask + self.predicted_bid) / 2.0, 6),
            "spread": round(self.predicted_ask - self.predicted_bid, 6),
            "confidence": round(self.confidence, 6),
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 3),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ThoughtNode:
    """Nodo del árbol de pensamientos ToT."""

    node_id: str
    thought: str
    action: str
    parent: Optional["ThoughtNode"] = None
    children: List["ThoughtNode"] = field(default_factory=list)
    observation: Optional[PredictorResult] = None
    state: ToTNodeState = ToTNodeState.PENDING
    score: Optional[float] = None
    depth: int = 0


class TickPredictionEnvironment:
    """Entorno que simula / invoca predictores ask/bid del siguiente tick.

    Cada predictor actúa como una "API" independiente. `failure_sources` permite
    forzar fallos controlados (TIMEOUT/NO_RESULTS) para demostrar poda y
    backtracking.
    """

    def __init__(
        self,
        brain: Optional[Any] = None,
        fallback_map: Optional[Dict[str, List[str]]] = None,
        failure_sources: Optional[List[str]] = None,
        latency_ms: float = 0.0,
    ) -> None:
        self.brain = brain
        self.fallback_map = fallback_map or self._default_fallback_map()
        self.failure_sources = set(failure_sources or [])
        self.latency_ms = latency_ms
        self._results: List[PredictorResult] = []

    # ------------------------------------------------------------------
    # Predictores
    # ------------------------------------------------------------------
    def _predictors(self) -> Dict[str, Any]:
        return {
            "brain": self._predict_brain,
            "world_model": self._predict_world_model,
            "technical": self._predict_technical,
            "microstructure": self._predict_microstructure,
            "sentiment": self._predict_sentiment,
            "ensemble": self._predict_ensemble,
        }

    def _default_fallback_map(self) -> Dict[str, List[str]]:
        return {
            "brain": ["ensemble"],
            "world_model": ["technical", "ensemble"],
            "technical": ["microstructure", "ensemble"],
            "microstructure": ["sentiment", "ensemble"],
            "sentiment": ["ensemble"],
        }

    def begin(self, ctx: Dict[str, Any]) -> None:
        """Reinicia el entorno para una nueva solicitud."""
        self._results = []
        self._ctx = ctx

    def query(self, source: str, ctx: Dict[str, Any]) -> PredictorResult:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000.0)
        if source in self.failure_sources:
            return self._fail(source, f"Simulated failure on {source}")
        fn = self._predictors().get(source)
        if fn is None:
            return self._fail(source, f"Unknown predictor {source}", PredictorStatus.NO_RESULTS)
        return fn(ctx)

    def fallback_for(self, source: str) -> List[str]:
        return self.fallback_map.get(source, [])

    def record_success(self, result: PredictorResult) -> None:
        if result.status == PredictorStatus.SUCCESS:
            self._results.append(result)

    # ------------------------------------------------------------------
    # APIs / predictores concretos
    # ------------------------------------------------------------------
    def _predict_brain(self, ctx: Dict[str, Any]) -> PredictorResult:
        """Predictor real basado en CentralBrain (world model neuronal)."""
        brain = ctx.get("brain") or self.brain
        if brain is None:
            return self._fail("brain", "No brain instance available")
        symbol = ctx["symbol"]
        try:
            if symbol not in brain.snapshots:
                ticks = ctx.get("ticks", [])
                news = ctx.get("news", [])
                request = TradingRequest(symbols=[symbol], ticks=ticks, news=news)
                brain.observe(request)
            pred = brain.predict_next_price(symbol)
            mid = float(pred["predicted_next_price"])
            confidence = max(0.0, 1.0 - float(pred.get("uncertainty", 0.5)))
            spread = _estimate_spread(ctx, mid)
            return PredictorResult(
                source="brain",
                predicted_ask=mid + spread / 2.0,
                predicted_bid=mid - spread / 2.0,
                confidence=confidence,
                metadata={"brain_prediction": pred},
            )
        except Exception as exc:
            return self._fail("brain", str(exc))

    def _predict_world_model(self, ctx: Dict[str, Any]) -> PredictorResult:
        """Predictor de tipo world-model (simulado si no hay brain)."""
        features = _features(ctx)
        last_price = _last_price(ctx)
        trend = features.get("trend_direction", 0)
        if trend == 0:
            return self._fail("world_model", "No clear trend to extrapolate")
        ret = 0.0005 * trend
        mid = last_price * (1.0 + ret)
        spread = _estimate_spread(ctx, mid)
        return PredictorResult(
            source="world_model",
            predicted_ask=mid + spread / 2.0,
            predicted_bid=mid - spread / 2.0,
            confidence=0.75,
        )

    def _predict_technical(self, ctx: Dict[str, Any]) -> PredictorResult:
        features = _features(ctx)
        if not features or "rsi" not in features:
            return self._fail("technical", "Insufficient technical features")
        last_price = _last_price(ctx)
        rsi = features.get("rsi", 50.0)
        trend = features.get("trend_direction", 0)
        if rsi > 70:
            ret = -0.001
        elif rsi < 30:
            ret = 0.001
        else:
            ret = 0.0005 * trend
        confidence = min(0.95, 0.5 + abs(rsi - 50.0) / 50.0)
        mid = last_price * (1.0 + ret)
        spread = _estimate_spread(ctx, mid)
        return PredictorResult(
            source="technical",
            predicted_ask=mid + spread / 2.0,
            predicted_bid=mid - spread / 2.0,
            confidence=round(confidence, 4),
            metadata={"rsi": rsi, "trend": trend},
        )

    def _predict_microstructure(self, ctx: Dict[str, Any]) -> PredictorResult:
        last_tick = ctx.get("last_tick")
        if last_tick is None or not (last_tick.bid_size and last_tick.ask_size):
            return self._fail("microstructure", "No order book size data")
        last_price = _last_price(ctx)
        imbalance = (last_tick.bid_size - last_tick.ask_size) / (
            last_tick.bid_size + last_tick.ask_size
        )
        ret = 0.0005 * imbalance
        confidence = 0.6 + 0.35 * abs(imbalance)
        mid = last_price * (1.0 + ret)
        spread = _estimate_spread(ctx, mid)
        return PredictorResult(
            source="microstructure",
            predicted_ask=mid + spread / 2.0,
            predicted_bid=mid - spread / 2.0,
            confidence=round(confidence, 4),
            metadata={"imbalance": round(imbalance, 4)},
        )

    def _predict_sentiment(self, ctx: Dict[str, Any]) -> PredictorResult:
        news = ctx.get("news", [])
        if not news:
            return self._fail("sentiment", "No news items available")
        last_price = _last_price(ctx)
        pipe = NewsPipeline()
        scores = [pipe.preprocess(n).sentiment for n in news]
        sentiment = sum(scores) / len(scores)
        ret = 0.001 * sentiment
        confidence = 0.5 + 0.4 * abs(sentiment)
        mid = last_price * (1.0 + ret)
        spread = _estimate_spread(ctx, mid)
        return PredictorResult(
            source="sentiment",
            predicted_ask=mid + spread / 2.0,
            predicted_bid=mid - spread / 2.0,
            confidence=round(confidence, 4),
            metadata={"sentiment": round(sentiment, 4)},
        )

    def _predict_ensemble(self, ctx: Dict[str, Any]) -> PredictorResult:
        """Fallback que combina (promedia ponderado por confianza) los predictores
        exitosos ya ejecutados, o emite una predicción conservadora si no hay."""
        if self._results:
            total_conf = sum(r.confidence for r in self._results) or 1.0
            ask = sum(r.predicted_ask * r.confidence for r in self._results) / total_conf
            bid = sum(r.predicted_bid * r.confidence for r in self._results) / total_conf
            confidence = sum(r.confidence for r in self._results) / len(self._results)
            return PredictorResult(
                source="ensemble",
                predicted_ask=ask,
                predicted_bid=bid,
                confidence=round(confidence, 4),
                metadata={"sources_used": [r.source for r in self._results]},
            )
        last_price = _last_price(ctx)
        mid = last_price
        spread = _estimate_spread(ctx, mid)
        return PredictorResult(
            source="ensemble",
            predicted_ask=mid + spread / 2.0,
            predicted_bid=mid - spread / 2.0,
            confidence=0.4,
            metadata={"note": "No prior successful predictors; conservative fallback"},
        )

    def _fail(
        self,
        source: str,
        error: str,
        status: PredictorStatus = PredictorStatus.TIMEOUT,
    ) -> PredictorResult:
        return PredictorResult(
            source=source,
            predicted_ask=0.0,
            predicted_bid=0.0,
            confidence=0.0,
            status=status,
            error=error,
        )


class ReActReasonactToTBrain:
    """Cerebro híbrido ReAct + Tree of Thoughts para predicción ask/bid."""

    def __init__(
        self,
        environment: TickPredictionEnvironment,
        confidence_threshold: float = 0.5,
        max_depth: int = 2,
    ) -> None:
        self.env = environment
        self.confidence_threshold = confidence_threshold
        self.max_depth = max_depth
        self.root: Optional[ThoughtNode] = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def predict(
        self,
        symbol: str,
        ticks: List[MarketTick],
        news: Optional[List[NewsItem]] = None,
        predictors: Optional[List[str]] = None,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ejecuta el árbol de pensamientos y devuelve el veredicto ask/bid."""
        if not ticks:
            return {"status": "error", "message": "ticks are required"}

        request_ctx = self._build_context(symbol, ticks, news, extra=ctx)
        self.env.begin(request_ctx)

        trace: List[Dict[str, Any]] = []
        self.root = ThoughtNode(
            node_id=f"root_{uuid.uuid4().hex[:6]}",
            thought=(
                f"Predict next ask/bid for {symbol}. Instead of a linear ReAct loop, "
                "I will expand multiple predictor branches in parallel, prune failures, "
                "backtrack to fallbacks, and synthesize a consensus."
            ),
            action="ROOT",
        )
        trace.append({"step": 0, "type": "thought", "content": self.root.thought})

        initial = predictors or ["world_model", "technical", "microstructure"]
        branches: List[ThoughtNode] = []
        for src in initial:
            node = ThoughtNode(
                node_id=f"node_{uuid.uuid4().hex[:6]}",
                thought=f"Branch: consult predictor '{src}' for next ask/bid.",
                action=src,
                parent=self.root,
                depth=1,
            )
            self.root.children.append(node)
            branches.append(node)
            trace.append({"step": len(trace), "type": "action", "content": src})

        for branch in branches:
            self._explore(branch, request_ctx, trace)

        synthesis = self._synthesize(self.root)
        trace.append({"step": len(trace), "type": "synthesis", "content": "Final consensus selected"})

        return {
            "status": "ok",
            "symbol": symbol,
            "request_id": str(uuid.uuid4())[:8],
            "final_prediction": synthesis["final_prediction"],
            "selected_leaf": synthesis["selected_leaf"],
            "consensus": synthesis["consensus"],
            "tree_summary": {
                "total_nodes": self._count_nodes(self.root),
                "success_leaves": len(self._success_leaves(self.root)),
                "pruned_leaves": len(self._pruned_leaves(self.root)),
                "backtracked_nodes": len(self._backtracked_nodes(self.root)),
            },
            "leaves": [n.observation.to_dict() for n in self._success_leaves(self.root) if n.observation],
            "tree": self._tree_to_dict(self.root),
            "trace": trace,
        }

    # ------------------------------------------------------------------
    # Construcción de contexto
    # ------------------------------------------------------------------
    def _build_context(
        self,
        symbol: str,
        ticks: List[MarketTick],
        news: Optional[List[NewsItem]],
        extra: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        news = news or []
        sorted_ticks = sorted(ticks, key=lambda t: t.timestamp)
        last_tick = sorted_ticks[-1]
        snapshot = None
        features: Dict[str, Any] = {}
        try:
            pipeline = MarketPerceptionPipeline()
            snapshots = pipeline.perceive(
                request_id=f"tot-{uuid.uuid4().hex[:6]}",
                ticks_by_symbol={symbol: sorted_ticks},
                news=news,
            )
            snapshot = snapshots.get(symbol)
            if snapshot:
                features = snapshot.features.to_dict()
        except Exception:
            snapshot = None
        ctx: Dict[str, Any] = {
            "symbol": symbol,
            "ticks": sorted_ticks,
            "last_tick": last_tick,
            "news": news,
            "snapshot": snapshot,
            "features": features,
        }
        if extra:
            ctx.update(extra)
        return ctx

    # ------------------------------------------------------------------
    # Exploración y retroceso
    # ------------------------------------------------------------------
    def _explore(
        self,
        node: ThoughtNode,
        ctx: Dict[str, Any],
        trace: List[Dict[str, Any]],
    ) -> None:
        if node.depth > self.max_depth:
            node.state = ToTNodeState.PRUNED_FAILED
            node.observation = self.env._fail(
                node.action, "Max depth exceeded", PredictorStatus.NO_RESULTS
            )
            return

        node.state = ToTNodeState.EXPLORING
        result = self.env.query(node.action, ctx)
        node.observation = result
        trace.append(
            {
                "step": len(trace),
                "type": "observation",
                "content": {
                    "source": result.source,
                    "status": result.status.value,
                    "ask": round(result.predicted_ask, 4),
                    "bid": round(result.predicted_bid, 4),
                    "confidence": round(result.confidence, 4),
                    "error": result.error,
                },
            }
        )

        if result.status == PredictorStatus.SUCCESS and result.confidence >= self.confidence_threshold:
            node.state = ToTNodeState.SUCCESS
            node.score = self._score(result)
            self.env.record_success(result)
            return

        node.state = ToTNodeState.PRUNED_FAILED
        self._backtrack(node, ctx, trace)

    def _backtrack(
        self,
        failed_node: ThoughtNode,
        ctx: Dict[str, Any],
        trace: List[Dict[str, Any]],
    ) -> None:
        for fallback in self.env.fallback_for(failed_node.action):
            if self._already_tried(failed_node, fallback):
                continue
            back_node = ThoughtNode(
                node_id=f"node_{uuid.uuid4().hex[:6]}",
                thought=f"Backtracking from '{failed_node.action}' failure to fallback '{fallback}'.",
                action=fallback,
                parent=failed_node,
                depth=failed_node.depth + 1,
            )
            failed_node.children.append(back_node)
            trace.append(
                {
                    "step": len(trace),
                    "type": "backtrack",
                    "content": f"{failed_node.action} -> {fallback}",
                }
            )
            self._explore(back_node, ctx, trace)
            if back_node.state == ToTNodeState.SUCCESS:
                failed_node.state = ToTNodeState.BACKTRACKED
                return

    def _already_tried(self, node: ThoughtNode, source: str) -> bool:
        current: Optional[ThoughtNode] = node
        while current is not None:
            if current.action == source:
                return True
            current = current.parent
        return False

    # ------------------------------------------------------------------
    # Síntesis convergente
    # ------------------------------------------------------------------
    def _synthesize(self, root: ThoughtNode) -> Dict[str, Any]:
        leaves = self._success_leaves(root)
        if not leaves:
            return {
                "final_prediction": None,
                "selected_leaf": None,
                "consensus": None,
                "message": "All branches were pruned; no prediction available.",
            }

        # Hoja mejor según score
        best = max(leaves, key=lambda n: n.score or 0.0)
        best_obs = best.observation
        best_dict = best_obs.to_dict() if best_obs else None

        # Consenso ponderado por confianza
        total_conf = sum(leaf.observation.confidence for leaf in leaves) or 1.0
        consensus_ask = (
            sum(leaf.observation.predicted_ask * leaf.observation.confidence for leaf in leaves)
            / total_conf
        )
        consensus_bid = (
            sum(leaf.observation.predicted_bid * leaf.observation.confidence for leaf in leaves)
            / total_conf
        )
        consensus_conf = sum(leaf.observation.confidence for leaf in leaves) / len(leaves)
        consensus = {
            "predicted_ask": round(consensus_ask, 6),
            "predicted_bid": round(consensus_bid, 6),
            "predicted_mid": round((consensus_ask + consensus_bid) / 2.0, 6),
            "spread": round(consensus_ask - consensus_bid, 6),
            "confidence": round(consensus_conf, 6),
            "source_strategy": "consensus_weighted",
            "contributing_sources": sorted({leaf.observation.source for leaf in leaves}),
        }

        final = {
            "predicted_ask": consensus["predicted_ask"],
            "predicted_bid": consensus["predicted_bid"],
            "predicted_mid": consensus["predicted_mid"],
            "spread": consensus["spread"],
            "confidence": consensus["confidence"],
            "source_strategy": consensus["source_strategy"],
        }

        return {
            "final_prediction": final,
            "selected_leaf": best_dict,
            "consensus": consensus,
        }

    def _score(self, result: PredictorResult) -> float:
        mid = (result.predicted_ask + result.predicted_bid) / 2.0
        spread = result.predicted_ask - result.predicted_bid
        spread_ratio = spread / mid if mid > 0 else 0.0
        return result.confidence / (1.0 + spread_ratio)

    # ------------------------------------------------------------------
    # Utilidades de recorrido
    # ------------------------------------------------------------------
    def _success_leaves(self, node: ThoughtNode) -> List[ThoughtNode]:
        if not node.children:
            return [node] if node.state == ToTNodeState.SUCCESS else []
        out: List[ThoughtNode] = []
        for child in node.children:
            out.extend(self._success_leaves(child))
        return out

    def _pruned_leaves(self, node: ThoughtNode) -> List[ThoughtNode]:
        if not node.children:
            return [node] if node.state == ToTNodeState.PRUNED_FAILED else []
        out: List[ThoughtNode] = []
        for child in node.children:
            out.extend(self._pruned_leaves(child))
        return out

    def _backtracked_nodes(self, node: ThoughtNode) -> List[ThoughtNode]:
        out: List[ThoughtNode] = [node] if node.state == ToTNodeState.BACKTRACKED else []
        for child in node.children:
            out.extend(self._backtracked_nodes(child))
        return out

    def _count_nodes(self, node: ThoughtNode) -> int:
        return 1 + sum(self._count_nodes(c) for c in node.children)

    def _tree_to_dict(self, node: ThoughtNode) -> Dict[str, Any]:
        obs = node.observation.to_dict() if node.observation else None
        return {
            "id": node.node_id,
            "thought": node.thought,
            "action": node.action,
            "state": node.state.value,
            "depth": node.depth,
            "score": round(node.score, 6) if node.score is not None else None,
            "observation": obs,
            "children": [self._tree_to_dict(c) for c in node.children],
        }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _last_price(ctx: Dict[str, Any]) -> float:
    last_tick = ctx.get("last_tick")
    if last_tick is not None:
        return float(last_tick.last_price)
    snapshot = ctx.get("snapshot")
    if snapshot is not None:
        return float(snapshot.latest_price)
    raise ValueError("No last tick or snapshot available")


def _features(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return ctx.get("features") or {}


def _estimate_spread(ctx: Dict[str, Any], mid: float) -> float:
    last_tick = ctx.get("last_tick")
    if last_tick is not None and last_tick.ask > last_tick.bid:
        return float(last_tick.ask - last_tick.bid)
    features = _features(ctx)
    vol = features.get("volatility", 0.0)
    if vol:
        return mid * vol * 0.5
    return mid * 0.0002
