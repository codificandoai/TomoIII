"""UC-313 — Validador de compatibilidad del stack AGI completo.

Ejecuta un conjunto de comprobaciones para garantizar que todas las capas
existentes (UC-292 a UC-296) funcionan de forma conjunta con la nueva capa de
autoconciencia/plasticidad (UC-313), tal como se representa en brain.png.
"""
from __future__ import annotations

from typing import Any, Dict, List

from brain_memory_pipeline import BrainMemoryPipeline
from brain_plasticity_interface import PrefrontalController
from central_brain import CentralBrain
from cognitive_evolution_layer import UC307CognitiveEvolutionLayer
from config import get_config
from cnp_broadcast_middleware import CNPAgentProfile, ContractNetMiddleware
from curiosity_skill_loop import CuriositySkillLoop
from market_data import SyntheticMarketDataGenerator
from memory_router import IntelligentMemoryRouter
from models import Portfolio, TradingRequest
from sam import MetacognitionModule, SafetySupervisor, SituationalAwarenessMiddleware
from self_awareness_loop import SelfAwarenessLoop
from self_model_store import SelfModelStore


class AGICompatibilityValidator:
    """Comprueba que el stack AGI completo es compatible y operativo."""

    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.config = get_config()

    def _check(
        self,
        name: str,
        fn: Any,
    ) -> bool:
        try:
            fn()
            self.results.append({"check": name, "status": "ok"})
            return True
        except Exception as exc:
            self.results.append({"check": name, "status": "fail", "error": str(exc)})
            return False

    def validate(self) -> Dict[str, Any]:
        checks = [
            ("central_brain_instantiation", self._central_brain),
            ("sam_gwt_workspace", self._sam_gwt),
            ("brain_memory_pipeline", self._brain_memory_pipeline),
            ("prefrontal_controller", self._prefrontal_controller),
            ("cognitive_evolution_layer", self._evolution_layer),
            ("cnp_middleware", self._cnp_middleware),
            ("curiosity_skill_loop", self._curiosity),
            ("self_awareness_loop", self._self_awareness_loop),
            ("memory_router", self._memory_router),
            ("shared_central_brain", self._shared_brain),
        ]
        passed = sum(self._check(name, fn) for name, fn in checks)
        return {
            "status": "compatible" if passed == len(checks) else "issues",
            "passed": passed,
            "total": len(checks),
            "details": self.results,
        }

    def _central_brain(self) -> None:
        brain = CentralBrain(self.config)
        gen = SyntheticMarketDataGenerator(self.config.market, seed=42)
        ticks = gen.generate_ticks("AAPL", n=20, start_price=150.0)
        request = TradingRequest(symbols=["AAPL"], ticks=ticks, portfolio=Portfolio(cash=100_000.0))
        snapshots = brain.observe(request)
        assert "AAPL" in snapshots
        pred = brain.predict_next_price("AAPL")
        assert "predicted_next_price" in pred

    def _sam_gwt(self) -> None:
        sam = SituationalAwarenessMiddleware(agent_identity="test")
        workspace = sam.build_workspace(
            request=TradingRequest(symbols=["AAPL"], ticks=[], portfolio=Portfolio(cash=100_000.0)),
            snapshots={"AAPL": {"symbol": "AAPL", "latest_price": 150.0, "regime": "normal"}},
            signals=[{"side": "BUY", "confidence": 0.8, "agent": "technical"}],
            hypotheses=[{"name": "bullish", "confidence": 0.75, "risk_score": 0.2}],
        )
        meta = MetacognitionModule().evaluate(workspace)
        safety = SafetySupervisor().check(workspace.selected_hypothesis or {},
            TradingRequest(symbols=["AAPL"], ticks=[], portfolio=Portfolio(cash=100_000.0)),
            workspace.perception.get("snapshots", {}),
        )
        assert workspace.selected_hypothesis is not None
        assert "recommendation" in meta
        assert isinstance(safety["allowed"], bool)
        messages = sam.broadcast_to_modules(workspace)
        assert len(messages) > 0

    def _brain_memory_pipeline(self) -> None:
        pipeline = BrainMemoryPipeline(self.config)
        gen = SyntheticMarketDataGenerator(self.config.market, seed=42)
        ticks = gen.generate_ticks("AAPL", n=30, start_price=150.0)
        request = TradingRequest(
            symbols=["AAPL"], ticks=ticks, portfolio=Portfolio(cash=100_000.0), mode="paper"
        )
        result = pipeline.run(request, propose_goal=False)
        assert "plasticity_result" in result
        assert "synaptic_weights" in result

    def _prefrontal_controller(self) -> None:
        brain = CentralBrain(self.config)
        ctrl = PrefrontalController(brain)
        params = ctrl.get_current_params()
        assert "model.learning_rate" in params
        result = ctrl.update_param("model.learning_rate", 0.25, "test", approved_by="t")
        assert result["status"] == "applied"
        result = ctrl.retrain_world_model("test", approved_by="t")
        assert result["status"] == "applied"
        rollback = ctrl.rollback()
        assert rollback["status"] == "rolled_back"

    def _evolution_layer(self) -> None:
        layer = UC307CognitiveEvolutionLayer()
        from cognitive_evolution_layer import ExecutionObservation
        obs = ExecutionObservation(
            agent_id="x", success=True, confidence=0.9, coherence=0.9,
            tokens_used=100, tool_calls=1, latency_seconds=0.1,
        )
        result = layer.evaluate_execution(obs)
        assert result.fitness > 0.8
        assert result.homeostasis.stable

    def _cnp_middleware(self) -> None:
        cnp = ContractNetMiddleware(
            agents=[CNPAgentProfile("a", skills=["x"], reliability=0.9)],
            window_size=2,
        )
        out = cnp.run_round("t1", "test task", execution_success=True)
        assert out["round"]["status"] == "completed"
        assert out["round"]["winner_id"] == "a"

    def _curiosity(self) -> None:
        loop = CuriositySkillLoop()
        out = loop.metatool_learn_new_skill("¿Cuál es el precio de SKU-1?", 100.0)
        assert out["outcome"] == "solved"

    def _self_awareness_loop(self) -> None:
        loop = SelfAwarenessLoop()
        ep = loop.run_episode(symbol="AAPL", n_ticks=30, run_cnp=True, run_curiosity=True)
        assert ep.narrative
        assert "Yo observé" in ep.narrative

    def _memory_router(self) -> None:
        router = IntelligentMemoryRouter()
        router.store_working_memory("test note")
        result = router.retrieve("acabo de hacer un cálculo")
        assert result.intent.value == "WORKING_STATE"
        result2 = router.retrieve("¿Cuál es mi objetivo actual?")
        assert result2.intent.value == "SELF_MODEL"

    def _shared_brain(self) -> None:
        brain = CentralBrain(self.config)
        pipeline = BrainMemoryPipeline(self.config, central_brain=brain)
        loop = SelfAwarenessLoop()
        assert loop.brain is not None
        # El pipeline debe reutilizar el mismo cerebro cuando se le pasa
        assert pipeline.brain is brain


def main() -> int:
    import json
    from rich.console import Console
    from rich.pretty import pprint

    console = Console()
    console.print("[bold cyan]UC-313 — Validación de compatibilidad del stack AGI[/bold cyan]")
    validator = AGICompatibilityValidator()
    report = validator.validate()
    pprint(report)
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] == "compatible" else 1


if __name__ == "__main__":
    raise SystemExit(main())
