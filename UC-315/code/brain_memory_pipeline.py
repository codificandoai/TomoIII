"""Pipeline integrado: cerebro AGI + gestión de memoria (UC-296).

Este módulo conecta las capas de memoria (corto, estructurada, vectorial),
self-model persistente, spotlight de atención, autoevaluación y modificación
segura de objetivos con el cerebro central y el grafo de trading del sistema.
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "UC-295", "code")))

from agent_core import run_sam_aware_pipeline
from attention_spotlight import AttentionSpotlight
from central_brain import CentralBrain
from cognitive_evolution_layer import (
    ExecutionObservation,
    UC307CognitiveEvolutionLayer,
)
from config import AppConfig, get_config
from continuous_self_eval import ContinuousSelfEvaluator
from market_data import SyntheticMarketDataGenerator
from memory_router import IntelligentMemoryRouter
from memory_types import MemoryIntent, SpotlightItem
from metacognitive_goals import GoalManager
from models import Portfolio, TradingRequest
from react_tot import ReActReasonactToTBrain, TickPredictionEnvironment
from self_model_store import SelfModelStore


class BrainMemoryPipeline:
    """Orquesta la interacción entre el cerebro de trading y la memoria AGI.

    Flujo:
    1. Cargar o crear self-model persistente.
    2. Ejecutar percepción y predicción ToT sobre el CentralBrain.
    3. Recuperar memorias relevantes (notepad, SQL, vectorial) para el símbolo.
    4. Aplicar spotlight de atención sobre hipótesis/señales/recuerdos.
    5. Ejecutar pipeline SAM + BDI + Juice + World Model.
    6. Registrar episodio de desempeño y autoevaluar.
    7. Proponer ajustes de objetivos de forma segura.
    8. Persistir self-model y reentrenar world model si corresponde.
    """

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        central_brain: Optional[CentralBrain] = None,
    ) -> None:
        self.config = config or get_config()
        self.brain = central_brain or CentralBrain(self.config)
        self.memory_router = IntelligentMemoryRouter()
        self.spotlight = AttentionSpotlight()
        self.self_store = SelfModelStore()
        self.evaluator = ContinuousSelfEvaluator(self.self_store)
        self.goal_manager = GoalManager()
        self.evolution_layer = UC307CognitiveEvolutionLayer(
            memory_router=self.memory_router,
            self_store=self.self_store,
            evaluator=self.evaluator,
            goal_manager=self.goal_manager,
            central_brain=self.brain,
        )
        self._ensure_demo_facts()

    def _ensure_demo_facts(self) -> None:
        """Carga hechos de ejemplo para demostraciones si no existen."""
        if self.memory_router.structured.query("products", "SKU-001", "cost") is None:
            self.memory_router.structured.store("products", "SKU-001", "cost", 100.0)
            self.memory_router.structured.store("products", "SKU-001", "stock", 450)
            self.memory_router.structured.store("products", "SKU-002", "cost", 45.5)
            self.memory_router.structured.store("products", "SKU-002", "stock", 1200)
            self.memory_router.structured.store("users", "U-99", "role", "Pricing_Manager")

    def run(
        self,
        request: TradingRequest,
        propose_goal: bool = True,
    ) -> Dict[str, Any]:
        symbol = request.symbols[0] if request.symbols else "AAPL"

        # 1. Cargar self-model y actualizar notas de contexto
        self_model = self.self_store.load()
        self.memory_router.store_working_memory(
            f"Processing request {request.request_id} for {symbol}",
            note_type="pipeline",
        )

        # 2. Ejecutar pipeline principal usando el CentralBrain compartido
        trading_output = run_sam_aware_pipeline(request, self.config, central_brain=self.brain)

        # 3. Predicción ToT usando el mismo cerebro
        tot_result = self._tot_prediction(symbol, request.ticks, request.news)

        # 4. Recuperar memorias relevantes
        memories = self._retrieve_relevant_memories(symbol, request)

        # 5. Spotlight de atención sobre candidatos
        spotlight_items = self._build_spotlight_items(
            trading_output, tot_result, memories, symbol
        )
        selected = self.spotlight.select(
            spotlight_items,
            current_goal=self_model.get("current_goal", ""),
            current_price=self._latest_price(symbol, request),
        )

        # 6. Evaluar desempeño del ciclo
        success = trading_output.get("status") not in ("failed", "aborted_by_sam")
        metrics = self._extract_metrics(trading_output, tot_result)
        episode = self.evaluator.evaluate_execution(
            task=f"trading_pipeline:{symbol}",
            success=success,
            metrics=metrics,
            context={
                "symbol": symbol,
                "status": trading_output.get("status"),
                "selected_strategy": trading_output.get("selected_strategy"),
            },
        )

        # 7. Proponer cambio de objetivo si la autoevaluación lo sugiere
        goal_proposal = None
        if propose_goal:
            goal_proposal = self._maybe_propose_goal(self_model, episode)

        # 8. Evaluar plasticidad sináptica digital (UC-307 / UC-313)
        plasticity_obs = self._build_plasticity_observation(
            symbol, trading_output, tot_result, request
        )
        plasticity_result = self.evolution_layer.evaluate_execution(plasticity_obs)
        if trading_output.get("selected_strategy"):
            self.evolution_layer.update_synaptic_weights(
                trading_output["selected_strategy"],
                success=success,
                confidence=plasticity_obs.confidence,
            )

        # 9. Reflejar y persistir
        reflection = self.evaluator.reflect(limit=20)
        self.self_store.save(self_model)

        return {
            "request_id": request.request_id,
            "symbol": symbol,
            "status": trading_output.get("status"),
            "trading_output": trading_output,
            "tot_prediction": tot_result,
            "memories": {k: v.to_dict() for k, v in memories.items()},
            "spotlight": [s.to_dict() for s in selected],
            "self_model": self_model,
            "performance_episode": episode.to_dict(),
            "goal_proposal": goal_proposal,
            "plasticity_result": plasticity_result.to_dict(),
            "synaptic_weights": self.evolution_layer.get_synaptic_snapshot(),
            "reflection": reflection,
        }

    def _tot_prediction(
        self,
        symbol: str,
        ticks: List[Any],
        news: Optional[List[Any]],
    ) -> Optional[Dict[str, Any]]:
        if not ticks:
            return None
        env = TickPredictionEnvironment(
            brain=self.brain,
            fallback_map={
                "brain": ["ensemble"],
                "world_model": ["technical", "ensemble"],
                "technical": ["microstructure", "ensemble"],
                "microstructure": ["sentiment", "ensemble"],
                "sentiment": ["ensemble"],
            },
            latency_ms=0.0,
        )
        tot = ReActReasonactToTBrain(env, confidence_threshold=0.5, max_depth=2)
        try:
            return tot.predict(
                symbol=symbol,
                ticks=ticks,
                news=news or [],
                predictors=["brain", "technical", "microstructure"],
            )
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def _retrieve_relevant_memories(
        self,
        symbol: str,
        request: TradingRequest,
    ) -> Dict[str, Any]:
        memories: Dict[str, Any] = {}
        memories["self_model"] = self.memory_router.retrieve(
            "cuál es mi objetivo actual",
            context={"intent": MemoryIntent.SELF_MODEL},
        )
        memories["market_context"] = self.memory_router.retrieve(
            f"experiencias previas con {symbol} y volatilidad",
        )
        memories["facts"] = self.memory_router.retrieve(
            f"costo e inventario de {symbol}",
            context={"entity_type": "products", "entity_id": symbol, "attribute": "cost"},
        )
        return memories

    def _build_spotlight_items(
        self,
        trading_output: Dict[str, Any],
        tot_result: Optional[Dict[str, Any]],
        memories: Dict[str, Any],
        symbol: str,
    ) -> List[SpotlightItem]:
        items: List[SpotlightItem] = []

        # Hipótesis del cerebro
        for hyp in trading_output.get("sam_state", {}).get("workspace", {}).get("hypotheses", []):
            items.append(SpotlightItem(
                item_id=f"hyp_{uuid.uuid4().hex[:6]}",
                item_type="hypothesis",
                content=hyp,
            ))

        # Predicción ToT
        if tot_result and tot_result.get("final_prediction"):
            items.append(SpotlightItem(
                item_id="tot_prediction",
                item_type="tot_prediction",
                content=tot_result["final_prediction"],
            ))

        # Señales aprobadas
        for sig in trading_output.get("signals", []):
            items.append(SpotlightItem(
                item_id=f"sig_{uuid.uuid4().hex[:6]}",
                item_type="signal",
                content=sig,
            ))

        # Recuerdos recuperados
        for key, mem in memories.items():
            if isinstance(mem, object) and hasattr(mem, "data"):
                items.append(SpotlightItem(
                    item_id=f"mem_{key}",
                    item_type="memory",
                    content=mem.to_dict(),
                ))

        return items

    def _extract_metrics(
        self,
        trading_output: Dict[str, Any],
        tot_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "reward": (trading_output.get("execution_result") or {}).get("success", False),
            "status": trading_output.get("status"),
            "juice_approved": (trading_output.get("juice_verdict") or {}).get("approved", True),
        }
        if tot_result and tot_result.get("final_prediction"):
            metrics["tot_confidence"] = tot_result["final_prediction"].get("confidence", 0.0)
        return metrics

    def _maybe_propose_goal(
        self,
        self_model: Dict[str, Any],
        episode: Any,
    ) -> Optional[Dict[str, Any]]:
        recent = self.self_store.get_recent_performance(limit=10)
        if len(recent) < 5:
            return None
        success_rate = sum(1 for r in recent if r.get("success")) / len(recent)
        current_goal = self_model.get("current_goal", "")
        if success_rate < 0.4 and "Minimizar drawdown" not in current_goal:
            return self.goal_manager.apply_goal_change(
                current_goal,
                "Minimizar drawdown",
                f"Tasa de éxito reciente baja ({success_rate:.2%}); proteger capital.",
                context={"recent_success_rate": success_rate, "metrics": episode.metrics},
                approved=True,
            )
        return None

    @staticmethod
    def _latest_price(symbol: str, request: TradingRequest) -> float:
        for t in reversed(request.ticks):
            if t.symbol == symbol:
                return float(t.last_price)
        return 0.0

    def _build_plasticity_observation(
        self,
        symbol: str,
        trading_output: Dict[str, Any],
        tot_result: Optional[Dict[str, Any]],
        request: TradingRequest,
    ) -> ExecutionObservation:
        """Construye una observación de ejecución para la capa UC-307."""
        success = trading_output.get("status") not in ("failed", "aborted_by_sam")
        juice = trading_output.get("juice_verdict") or {}
        confidence = 0.7
        if tot_result and tot_result.get("final_prediction"):
            confidence = tot_result["final_prediction"].get("confidence", 0.7)
        elif juice:
            confidence = 1.0 if juice.get("approved") else 0.4

        return ExecutionObservation(
            agent_id=trading_output.get("selected_strategy") or "central_brain",
            task_id=str(request.request_id),
            success=success,
            reward=1.0 if success else -1.0,
            latency_seconds=float(trading_output.get("latency_seconds", 0.0)),
            tokens_used=trading_output.get("tokens_used", 0),
            tool_calls=trading_output.get("tool_calls", len(trading_output.get("signals", []))),
            errors=0 if success else 1,
            confidence=confidence,
            coherence=confidence,
            activations={symbol: confidence},
            context={
                "symbol": symbol,
                "mode": request.mode,
                "requires_confirmation": trading_output.get("requires_confirmation"),
                "selected_strategy": trading_output.get("selected_strategy"),
            },
        )


def run_memory_brain_demo() -> Dict[str, Any]:
    """Demo rápida del pipeline integrado."""
    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=80, start_price=150.0)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
        mode="paper",
        approved=False,
    )
    pipeline = BrainMemoryPipeline(cfg)
    return pipeline.run(request, propose_goal=True)


if __name__ == "__main__":
    from rich.console import Console
    from rich.pretty import pprint

    console = Console()
    console.print("[bold cyan]UC-296 — Brain + Memory Pipeline Demo[/bold cyan]")
    result = run_memory_brain_demo()
    pprint(result)
