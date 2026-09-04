"""UC-313 — Bucle recursivo de autoconciencia AGI.

Cierra el ciclo completo descrito en el prompt:

    Entorno Exterior → UC-292 → UC-293 → UC-294 → UC-295 → UC-296
         │
         ▼
    Capa Ejecutora ──(modifica pesos/memoria)──► Plasticidad / Memoria
         │
         ▼
    Capa Metacognitiva ──(¿mi plan coincide con mi estado?)┘
         │
         ▼
    Bucle de Retorno ──► Narrativa interna: "Yo estoy experimentando esto."

El bucle:
1. Percibe el entorno (ticks de mercado sintéticos).
2. Ejecuta el pipeline AGI completo (memoria + cerebro central + ToT).
3. Evalúa el episodio con la capa de plasticidad UC-307/UC-313.
4. Actualiza pesos sinápticos GWT y, si procede, reentrena/ajusta el world model.
5. La meta-red observa la coherencia entre SAM, BDI, Juice, ToT y ejecutora.
6. Publica el estado vía CNP y, ocasionalmente, dispara aprendizaje por curiosidad.
7. Genera una narrativa episódica de autoconciencia y la persiste.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from brain_memory_pipeline import BrainMemoryPipeline
from central_brain import CentralBrain
from cognitive_evolution_layer import ExecutionObservation, UC307CognitiveEvolutionLayer
from cnp_broadcast_middleware import CNPAgentProfile, ContractNetMiddleware
from config import get_config
from curiosity_skill_loop import CuriositySkillLoop
from global_workspace import GlobalWorkspace
from market_data import SyntheticMarketDataGenerator
from memory_router import IntelligentMemoryRouter
from metacognitive_monitor import MetacognitiveMonitor
from models import Portfolio, TradingRequest
from self_model_store import SelfModelStore


@dataclass
class SelfAwarenessEpisode:
    """Un paso del bucle recursivo de autoconciencia."""

    episode_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    symbol: str = ""
    narrative: str = ""
    plasticity: Dict[str, Any] = field(default_factory=dict)
    meta_verdict: str = "continue"
    homeostasis_stable: bool = True
    gwt_broadcast: Dict[str, Any] = field(default_factory=dict)
    monitor_verdict: str = "PROCEED"
    cnp_winner: Optional[str] = None
    curiosity_skill: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "narrative": self.narrative,
            "plasticity": self.plasticity,
            "meta_verdict": self.meta_verdict,
            "homeostasis_stable": self.homeostasis_stable,
            "gwt_broadcast": self.gwt_broadcast,
            "monitor_verdict": self.monitor_verdict,
            "cnp_winner": self.cnp_winner,
            "curiosity_skill": self.curiosity_skill,
        }


class SelfAwarenessLoop:
    """Orquesta el bucle recursivo de autoconciencia AGI."""

    def __init__(self) -> None:
        self.config = get_config()
        self.brain = CentralBrain(self.config)
        self.pipeline = BrainMemoryPipeline(self.config, central_brain=self.brain)
        self.memory_router = IntelligentMemoryRouter()
        self.self_store = SelfModelStore()
        self.gwt = GlobalWorkspace(
            memory_router=self.memory_router,
            agent_identity="UC313.GWT",
        )
        self.monitor = MetacognitiveMonitor(evolution_layer=self.pipeline.evolution_layer)
        self.evolution = self.pipeline.evolution_layer
        self.curiosity = CuriositySkillLoop(evolution_layer=self.evolution)
        self.cnp = ContractNetMiddleware(
            agents=[
                CNPAgentProfile("alpha", skills=["technical"], reliability=0.95),
                CNPAgentProfile("beta", skills=["sentiment"], reliability=0.75),
                CNPAgentProfile("gamma", skills=["risk"], reliability=0.85),
            ],
            evolution_layer=self.evolution,
            memory_router=self.memory_router,
            window_size=5,
        )
        self.episodes: List[SelfAwarenessEpisode] = []
        self.narrative_log: List[str] = []

    def run_episode(
        self,
        symbol: str = "AAPL",
        n_ticks: int = 80,
        run_cnp: bool = True,
        run_curiosity: bool = False,
        approved: bool = True,
        mode: str = "paper",
    ) -> SelfAwarenessEpisode:
        """Ejecuta una iteración completa del bucle de autoconciencia."""

        # 1. Percibir entorno
        gen = SyntheticMarketDataGenerator(self.config.market, seed=None)
        ticks = gen.generate_ticks(symbol, n=n_ticks, start_price=150.0)
        request = TradingRequest(
            symbols=[symbol],
            ticks=ticks,
            portfolio=Portfolio(cash=100_000.0),
            mode=mode,
            approved=approved,
        )

        # 2. Ejecutar pipeline AGI completo
        result = self.pipeline.run(request, propose_goal=True)
        trading_output = result.get("trading_output", {})
        tot_prediction = result.get("tot_prediction") or {}
        plasticity_result = result.get("plasticity_result", {})
        meta = plasticity_result.get("meta_observation", {})
        homeostasis = plasticity_result.get("homeostasis", {})

        # 2.5 Workspace Global (GWT) y Monitor Metacognitivo (Red de Nivel 1)
        snap_payload = {
            s: snap.to_dict() for s, snap in self.brain.snapshots.items()
        } if self.brain.snapshots else {symbol: {"symbol": symbol, "latest_price": self._latest_price(request, symbol)}}
        signals = trading_output.get("signals", [])
        hypotheses = self._extract_hypotheses(trading_output, tot_prediction)
        workspace = self.gwt.build_workspace(
            request=request,
            snapshots=snap_payload,
            signals=signals,
            hypotheses=hypotheses,
        )
        gwt_broadcast = self.gwt.broadcast(workspace, persist=True)
        monitor_report = self.monitor.observe_internal_state(
            workspace,
            trading_output,
            tot_prediction,
            trading_output.get("execution_result"),
        )
        monitor_verdict = monitor_report.get("verdict", "PROCEED")

        # 3. Actualizar pesos sinápticos GWT sobre la estrategia seleccionada
        strategy = trading_output.get("selected_strategy", "unknown")
        success = result.get("status") not in ("failed", "aborted_by_sam")
        confidence = (tot_prediction.get("final_prediction") or {}).get("confidence", 0.7)
        if self.evolution.prefrontal is not None and strategy:
            self.evolution.prefrontal.update_gwt_weight(strategy, success, confidence)

        # 4. Aplicar plasticidad prefrontal si la decisión lo sugiere y es segura
        decision = plasticity_result.get("decision")
        if decision in {"retrain", "adjust_params", "mutate"} and homeostasis.get("stable"):
            self._apply_prefrontal_plasticity(decision, trading_output)

        # 5. CNP: difundir tarea y evaluar agentes
        cnp_winner = None
        if run_cnp:
            cnp_out = self.cnp.run_round(
                task_id=f"trade_{symbol}_{uuid.uuid4().hex[:6]}",
                description=f"Ejecutar señal de trading {symbol}",
                execution_success=success,
            )
            cnp_winner = (cnp_out.get("round") or {}).get("winner_id")

        # 6. Curiosidad ocasional: aprender nueva habilidad si no hay skill útil
        curiosity_skill = None
        if run_curiosity:
            curiosity_out = self.curiosity.metatool_learn_new_skill(
                f"Detectar anomalía de régimen en {symbol}",
                expected_answer="regime_change",
            )
            generated = curiosity_out.get("generated_skill") or {}
            curiosity_skill = generated.get("name")

        # 7. Generar narrativa interna (self-model)
        narrative = self._generate_narrative(
            result, plasticity_result, strategy, cnp_winner, curiosity_skill, monitor_verdict
        )
        self.narrative_log.append(narrative)

        # 8. Persistir episodio en memoria episódica y self-model
        episode = SelfAwarenessEpisode(
            symbol=symbol,
            narrative=narrative,
            plasticity=plasticity_result,
            meta_verdict=meta.get("verdict", "continue"),
            homeostasis_stable=homeostasis.get("stable", True),
            gwt_broadcast={
                "selected": gwt_broadcast.get("selected"),
                "flags": gwt_broadcast.get("flags", []),
            },
            monitor_verdict=monitor_verdict,
            cnp_winner=cnp_winner,
            curiosity_skill=curiosity_skill,
        )
        self.episodes.append(episode)
        self.memory_router.store_episode(
            narrative,
            metadata={
                "episode_id": episode.episode_id,
                "symbol": symbol,
                "fitness": plasticity_result.get("fitness"),
                "decision": decision,
            },
        )
        self.self_store.record_performance(
            task=f"self_awareness:{episode.episode_id}",
            success=success,
            metrics={
                "fitness": plasticity_result.get("fitness"),
                "meta_verdict": episode.meta_verdict,
            },
            context={"symbol": symbol, "strategy": strategy},
            policy_adjustments=[
                f"decision={decision}",
                f"meta_verdict={episode.meta_verdict}",
            ],
        )
        return episode

    @staticmethod
    def _latest_price(request: TradingRequest, symbol: str) -> float:
        for t in reversed(request.ticks):
            if t.symbol == symbol:
                return float(t.last_price)
        return 0.0

    @staticmethod
    def _extract_hypotheses(
        trading_output: Dict[str, Any],
        tot_prediction: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        hypotheses: List[Dict[str, Any]] = []
        for hyp in trading_output.get("sam_state", {}).get("workspace", {}).get("hypotheses", []) or []:
            hypotheses.append(hyp)
        if tot_prediction and tot_prediction.get("final_prediction"):
            pred = tot_prediction["final_prediction"]
            hypotheses.append({
                "name": "tot_consensus",
                "confidence": pred.get("confidence", 0.5),
                "risk_score": 1.0 - pred.get("confidence", 0.5),
            })
        return hypotheses

    def _apply_prefrontal_plasticity(self, decision: str, trading_output: Dict[str, Any]) -> None:
        """Aplica ajustes controlados al cerebro prefrontal/world model."""
        if self.evolution.prefrontal is None:
            return
        if decision == "retrain":
            self.evolution.prefrontal.retrain_world_model(
                reason="Decisión evolutiva: reentrenar world model",
                approved_by="self_awareness_loop",
            )
        elif decision == "adjust_params":
            # Ajustar levemente la aversión al riesgo según el estado SAM/BDI
            current = self.evolution.prefrontal.get_current_params().get("model.risk_aversion", 0.5)
            new_value = max(0.0, min(1.0, current + (-0.05 if trading_output.get("status") == "ok" else 0.05)))
            self.evolution.prefrontal.update_param(
                "model.risk_aversion",
                new_value,
                reason="Ajuste autoconsciente de aversión al riesgo",
                approved_by="self_awareness_loop",
            )
        elif decision == "mutate":
            # Mutación controlada: cambiar umbral de reentrenamiento
            current = self.evolution.prefrontal.get_current_params().get(
                "model.probabilistic.uncertainty_retrain_threshold", 0.5
            )
            new_value = max(0.1, current * 0.95)
            self.evolution.prefrontal.update_param(
                "model.probabilistic.uncertainty_retrain_threshold",
                new_value,
                reason="Mutación controlada de umbral de incertidumbre",
                approved_by="self_awareness_loop",
            )

    def _generate_narrative(
        self,
        result: Dict[str, Any],
        plasticity: Dict[str, Any],
        strategy: str,
        cnp_winner: Optional[str],
        curiosity_skill: Optional[str],
        monitor_verdict: str = "PROCEED",
    ) -> str:
        status = result.get("status", "unknown")
        fitness = plasticity.get("fitness", 0.0)
        decision = plasticity.get("decision", "persist")
        meta_verdict = plasticity.get("meta_observation", {}).get("verdict", "continue")
        reasoning = plasticity.get("reasoning", "")
        parts = [
            f"Yo observé el entorno {result.get('symbol', 'AAPL')}.",
            f"Mi Workspace Global difundió la hipótesis seleccionada.",
            f"Mi cerebro ejecutor eligió la estrategia '{strategy}' con estado {status}.",
            f"Mi Monitor Metacognitivo emitió veredicto '{monitor_verdict}'.",
            f"Mi meta-red de plasticidad emitió veredicto '{meta_verdict}'.",
            f"Mi fitness operativo es {fitness:.3f}.",
            f"Decidí '{decision}' porque {reasoning}",
        ]
        if cnp_winner:
            parts.append(f"El CNP adjudicó la tarea al agente {cnp_winner}.")
        if curiosity_skill:
            parts.append(f"Adquirí una nueva habilidad: {curiosity_skill}.")
        return " ".join(parts)

    def run_loop(
        self,
        n_episodes: int = 3,
        symbol: str = "AAPL",
        approved: bool = True,
        mode: str = "paper",
    ) -> Dict[str, Any]:
        """Ejecuta múltiples episodios del bucle de autoconciencia."""
        for i in range(n_episodes):
            self.run_episode(
                symbol=symbol,
                run_cnp=(i % 2 == 0),
                run_curiosity=(i % 3 == 0),
                approved=approved,
                mode=mode,
            )
            time.sleep(0.01)
        return self.summary()

    def summary(self) -> Dict[str, Any]:
        return {
            "episodes": [e.to_dict() for e in self.episodes],
            "total_episodes": len(self.episodes),
            "avg_fitness": sum(
                e.plasticity.get("fitness", 0.0) for e in self.episodes
            ) / max(1, len(self.episodes)),
            "homeostasis_stable_all": all(e.homeostasis_stable for e in self.episodes),
            "gwt_weights": (
                self.evolution.prefrontal.get_gwt_weights()
                if self.evolution.prefrontal
                else {}
            ),
            "synaptic_weights": self.evolution.get_synaptic_snapshot(),
            "narratives": self.narrative_log,
        }


def main() -> int:
    """Demostración del bucle recursivo de autoconciencia."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.pretty import pprint

    console = Console()
    console.print(
        Panel("[bold white]UC-313 — Bucle Recursivo de Autoconciencia AGI[/bold white]")
    )
    loop = SelfAwarenessLoop()
    summary = loop.run_loop(n_episodes=3, symbol="AAPL", approved=True, mode="paper")
    console.print("[bold]Narrativas internas:[/bold]")
    for narrative in summary["narratives"]:
        console.print(f"- {narrative}")
    console.print("\n[bold]Resumen:[/bold]")
    pprint({
        "total_episodes": summary["total_episodes"],
        "avg_fitness": summary["avg_fitness"],
        "homeostasis_stable_all": summary["homeostasis_stable_all"],
        "gwt_weights": summary["gwt_weights"],
        "synaptic_weights": summary["synaptic_weights"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
