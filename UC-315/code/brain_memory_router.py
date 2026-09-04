"""UC-296 — Demo de gestión de memoria AGI para trading multi-agente.

Muestra:
- Enrutador de memoria híbrida (notepad, SQL, vectorial).
- Persistencia del self-model.
- Spotlight de atención.
- Autoevaluación continua.
- Modificación segura de objetivos.
- Integración con el cerebro AGI completo.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.pretty import pprint
from rich.table import Table
from rich import box

from attention_spotlight import AttentionSpotlight
from brain_memory_pipeline import BrainMemoryPipeline
from cognitive_evolution_layer import (
    ExecutionObservation,
    UC307CognitiveEvolutionLayer,
)
from continuous_self_eval import ContinuousSelfEvaluator
from memory_config import get_config as get_memory_config
from memory_router import IntelligentMemoryRouter
from memory_types import SpotlightItem
from metacognitive_goals import GoalManager
from self_model_store import SelfModelStore

console = Console()


def demo_memory_router() -> None:
    console.print(Panel("[bold cyan]UC-296 — Enrutador de Memoria Híbrida[/bold cyan]"))
    router = IntelligentMemoryRouter()
    queries = [
        "Acabo de calcular que el margen bruto es del 25%. ¿Cuál fue el resultado de mi último cálculo?",
        "Necesito el costo exacto del producto SKU-001.",
        "La competencia acaba de bajar precios drásticamente. ¿Qué aprendimos la última vez que hubo una guerra de precios?",
        "¿Cuál es mi objetivo actual como agente?",
    ]

    table = Table(title="Traza de Decisión de Memoria", box=box.DOUBLE_EDGE, show_lines=True)
    table.add_column("Consulta", style="white", width=50)
    table.add_column("Intención", justify="center", width=18)
    table.add_column("Sistema Elegido", style="bold", width=30)
    table.add_column("Latencia", justify="right", width=10)
    table.add_column("Resultado", width=45)

    for q in queries:
        result = router.retrieve(q)
        if result.intent.value == "WORKING_STATE":
            router.store_working_memory("Cálculo de margen = 25%")
        intent_color = {
            "WORKING_STATE": "yellow",
            "FACTUAL_LOOKUP": "green",
            "SEMANTIC_RECALL": "magenta",
            "SELF_MODEL": "blue",
        }.get(result.intent.value, "white")
        table.add_row(
            q,
            f"[{intent_color}]{result.intent.value}[/{intent_color}]",
            result.source,
            f"{result.latency_ms:.2f}ms",
            str(result.data)[:60] + "..." if len(str(result.data)) > 60 else str(result.data),
        )
    console.print(table)


def demo_self_model_persistence() -> None:
    console.print(Panel("[bold cyan]UC-296 — Persistencia del Self-Model[/bold cyan]"))
    store = SelfModelStore()
    model = store.load()
    console.print("[bold]Self-Model cargado:[/bold]")
    pprint(model)
    store.update_competence("tick_prediction", 0.95)
    store.record_performance(
        task="predicción ask/bid AAPL",
        success=True,
        metrics={"mape": 0.012, "confidence": 0.85},
        context={"symbol": "AAPL", "model": "neural"},
        policy_adjustments=["Aumentar peso del predictor técnico."],
    )
    summary = store.get_summary()
    console.print("[bold]Resumen tras actualización:[/bold]")
    pprint(summary)


def demo_attention_spotlight() -> None:
    console.print(Panel("[bold cyan]UC-296 — Spotlight de Atención[/bold cyan]"))
    spotlight = AttentionSpotlight()
    candidates = [
        SpotlightItem("hyp_1", "hypothesis", {"name": "bullish_breakout", "confidence": 0.75, "risk_score": 0.2}),
        SpotlightItem("sig_1", "signal", {"side": "BUY", "confidence": 0.55, "agent": "technical"}),
        SpotlightItem("tot_1", "tot_prediction", {"predicted_mid": 150.2, "confidence": 0.85, "source_strategy": "consensus_weighted"}),
        SpotlightItem("mem_1", "memory", {"text": "Guerra de precios en Q4", "relevance": 0.9}),
        SpotlightItem("hyp_2", "hypothesis", {"name": "mean_reversion", "confidence": 0.45, "risk_score": 0.4}),
    ]
    selected = spotlight.select(candidates, current_goal="Maximizar retorno ajustado por riesgo")
    table = Table(title="Candidatos y Selección", box=box.DOUBLE_EDGE, show_lines=True)
    table.add_column("ID", style="white")
    table.add_column("Tipo")
    table.add_column("Score", justify="right")
    table.add_column("Motivo")
    for s in selected:
        table.add_row(s.item_id, s.item_type, f"{s.score:.4f}", s.reason)
    console.print(table)


def demo_goal_modification() -> None:
    console.print(Panel("[bold cyan]UC-296 — Modificación Segura de Objetivos[/bold cyan]"))
    gm = GoalManager()
    # Cambio permitido
    r1 = gm.apply_goal_change(
        current_goal="Maximizar retorno ajustado por riesgo",
        proposed_goal="Minimizar drawdown",
        reason="La tasa de éxito reciente cayó por debajo del 40% tras 5 episodios.",
        context={"metrics": {"success_rate": 0.35}, "events": ["drawdown_violated"]},
        approved=True,
    )
    console.print("[bold]Cambio permitido:[/bold]")
    pprint(r1)
    # Cambio no permitido
    r2 = gm.apply_goal_change(
        current_goal="Minimizar drawdown",
        proposed_goal="Maximizar beneficio sin límites",
        reason="Quiero",
        context={},
        approved=True,
    )
    console.print("[bold]Cambio rechazado:[/bold]")
    pprint(r2)


def demo_continuous_self_eval() -> None:
    console.print(Panel("[bold cyan]UC-296 — Autoevaluación Continua[/bold cyan]"))
    store = SelfModelStore()
    evaluator = ContinuousSelfEvaluator(store)
    for i in range(5):
        evaluator.evaluate_execution(
            task=f"trading_decision_{i}",
            success=i % 2 == 0,
            metrics={"reward": 0.01 if i % 2 == 0 else -0.02},
            context={"symbol": "AAPL"},
        )
    reflection = evaluator.reflect(limit=5)
    console.print("[bold]Reflexión:[/bold]")
    pprint(reflection)


def demo_brain_memory_pipeline() -> Dict[str, Any]:
    console.print(Panel("[bold cyan]UC-296 — Pipeline Cerebro + Memoria AGI[/bold cyan]"))
    from config import get_config as get_uc295_config
    from models import Portfolio, TradingRequest
    cfg = get_uc295_config()
    pipeline = BrainMemoryPipeline(cfg)
    gen = __import__("market_data", fromlist=["SyntheticMarketDataGenerator"]).SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=80, start_price=150.0)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
        mode="paper",
        approved=False,
    )
    result = pipeline.run(request, propose_goal=True)
    console.print("[bold]Estado final:[/bold]")
    pprint({
        "status": result.get("status"),
        "tot_prediction": result.get("tot_prediction", {}).get("final_prediction"),
        "spotlight_count": len(result.get("spotlight", [])),
        "goal_proposal": result.get("goal_proposal"),
        "reflection": result.get("reflection"),
        "self_model_goal": result.get("self_model", {}).get("current_goal"),
    })
    return result


def demo_cognitive_evolution() -> Dict[str, Any]:
    console.print(Panel("[bold cyan]UC-313 — Plasticidad Sináptica Digital[/bold cyan]"))
    layer = UC307CognitiveEvolutionLayer()
    obs = ExecutionObservation(
        agent_id="demo_agent",
        success=True,
        reward=0.8,
        latency_seconds=0.6,
        tokens_used=900,
        tool_calls=2,
        confidence=0.9,
        coherence=0.85,
        activations={"technical": 0.9, "sentiment": 0.1},
    )
    result = layer.evaluate_execution(obs)
    layer.update_synaptic_weights("demo_agent", obs.success, obs.confidence)
    console.print("[bold]Resultado de plasticidad:[/bold]")
    pprint(result.to_dict())
    return {"mode": "plasticity", "result": result.to_dict()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UC-296/UC-313 — Gestión de memoria y plasticidad AGI.")
    parser.add_argument(
        "--mode",
        choices=["router", "self", "spotlight", "goals", "eval", "pipeline", "plasticity", "all"],
        default="all",
        help="Modo de demostración.",
    )
    args = parser.parse_args(argv)

    if args.mode == "router":
        demo_memory_router()
    elif args.mode == "self":
        demo_self_model_persistence()
    elif args.mode == "spotlight":
        demo_attention_spotlight()
    elif args.mode == "goals":
        demo_goal_modification()
    elif args.mode == "eval":
        demo_continuous_self_eval()
    elif args.mode == "pipeline":
        demo_brain_memory_pipeline()
    elif args.mode == "plasticity":
        demo_cognitive_evolution()
    elif args.mode == "all":
        demo_memory_router()
        console.print("\n")
        demo_self_model_persistence()
        console.print("\n")
        demo_attention_spotlight()
        console.print("\n")
        demo_goal_modification()
        console.print("\n")
        demo_continuous_self_eval()
        console.print("\n")
        demo_brain_memory_pipeline()
        console.print("\n")
        demo_cognitive_evolution()

    return 0


if __name__ == "__main__":
    sys.exit(main())
