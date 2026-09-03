"""Codificando.AI
UC-295: Demostración de la capa ReAct Híbrido con Árbol de Pensamientos (ToT)
para la predicción del siguiente ask/bid de un tick bursátil.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Este script ilustra cómo el agente supera la limitación del ReAct lineal:
1. Expande en paralelo varias "APIs de predicción" (world_model, técnico,
   microestructura, sentimiento, ensemble).
2. Poda las ramas que fallan (TIMEOUT / sin resultados / baja confianza).
3. Retrocede (backtracking) a predictores de contingencia.
4. Sintetiza un veredicto consensuado ask/bid.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from central_brain import CentralBrain
from config import get_config
from market_data import SyntheticMarketDataGenerator
from react_tot import (
    ReActReasonactToTBrain,
    TickPredictionEnvironment,
    ToTNodeState,
)
from rich.console import Console
from rich.panel import Panel
from rich.pretty import pprint
from rich.tree import Tree

console = Console()


def _build_rich_tree(tree_dict: Dict[str, Any]) -> Tree:
    """Convierte el árbol serializado en un Rich.Tree para la terminal."""

    def _color(state: str) -> str:
        return {
            ToTNodeState.SUCCESS.value: "green",
            ToTNodeState.PRUNED_FAILED.value: "red",
            ToTNodeState.BACKTRACKED.value: "yellow",
            ToTNodeState.EXPLORING.value: "blue",
        }.get(state, "white")

    obs = tree_dict.get("observation") or {}
    summary = f"[bold]{tree_dict['id']}[/bold] | {tree_dict['action']} -> [{_color(tree_dict['state'])}]{tree_dict['state']}[/{_color(tree_dict['state'])}]"
    if tree_dict.get("score") is not None:
        summary += f" (score={tree_dict['score']:.4f})"
    if obs.get("predicted_mid"):
        summary += (
            f" | ask={obs['predicted_ask']:.4f} bid={obs['predicted_bid']:.4f} "
            f"conf={obs['confidence']:.2f}"
        )
    if obs.get("error"):
        summary += f" | error={obs['error']}"

    root = Tree(summary)
    for child in tree_dict.get("children", []):
        _add_child(root, child)
    return root


def _add_child(parent: Tree, node: Dict[str, Any]) -> None:
    color = {
        ToTNodeState.SUCCESS.value: "green",
        ToTNodeState.PRUNED_FAILED.value: "red",
        ToTNodeState.BACKTRACKED.value: "yellow",
        ToTNodeState.EXPLORING.value: "blue",
    }.get(node["state"], "white")
    obs = node.get("observation") or {}
    label = f"{node['id']} | {node['action']} -> [{color}]{node['state']}[/{color}]"
    if node.get("score") is not None:
        label += f" (score={node['score']:.4f})"
    if obs.get("predicted_mid"):
        label += (
            f" | ask={obs['predicted_ask']:.4f} bid={obs['predicted_bid']:.4f} "
            f"conf={obs['confidence']:.2f}"
        )
    if obs.get("error"):
        label += f" | [red]{obs['error']}[/red]"
    branch = parent.add(label)
    for child in node.get("children", []):
        _add_child(branch, child)


def run_tot_demo(
    failure_source: Optional[str] = "technical",
    use_brain: bool = False,
) -> Dict[str, Any]:
    """Ejecuta el cerebro híbrido ReAct+ToT sobre ticks sintéticos de AAPL."""
    console.print(
        Panel(
            "[bold cyan]UC-295 — ReAct Híbrido + Tree of Thoughts (ToT)[/bold cyan]\n"
            f"Predictor CentralBrain: {use_brain} | Simulated failure: {failure_source or 'none'}",
            border_style="cyan",
        )
    )

    gen = SyntheticMarketDataGenerator(seed=42)
    ticks = gen.generate_ticks("AAPL", n=80, start_price=150.0)

    real_brain = CentralBrain(get_config()) if use_brain else None
    env = TickPredictionEnvironment(
        brain=real_brain,
        failure_sources=[failure_source] if failure_source else [],
        latency_ms=0.0,
    )
    tot_brain = ReActReasonactToTBrain(
        env,
        confidence_threshold=0.5,
        max_depth=2,
    )

    predictors = ["brain", "technical", "microstructure"] if use_brain else ["world_model", "technical", "microstructure"]
    result = tot_brain.predict(
        symbol="AAPL",
        ticks=ticks,
        news=[],
        predictors=predictors,
    )

    console.print("\n[bold white]PREDICCIÓN FINAL ASK/BID:[/bold white]")
    pprint(result.get("final_prediction"))

    console.print("\n[bold white]RESUMEN DEL ÁRBOL:[/bold white]")
    pprint(result.get("tree_summary"))

    console.print("\n[bold white]TRAZA REACT (Thought → Action → Observation):[/bold white]")
    for step in result.get("trace", []):
        marker = {
            "thought": "💡",
            "action": "🔧",
            "observation": "👁",
            "backtrack": "↩️",
            "synthesis": "🧠",
        }.get(step["type"], "•")
        console.print(f"{marker} [{step['type'].upper()}] {step['content']}")

    console.print("\n[bold white]ÁRBOL DE PENSAMIENTOS VISUAL:[/bold white]")
    console.print(_build_rich_tree(result.get("tree", {})))

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="UC-295 — ReAct Híbrido con Tree of Thoughts para ask/bid."
    )
    parser.add_argument(
        "--failure",
        default="technical",
        help="Predictor a simular como fallido (TIMEOUT).",
    )
    parser.add_argument(
        "--use-brain",
        action="store_true",
        help="Usa CentralBrain real como predictor (más lento, requiere ticks).",
    )
    parser.add_argument(
        "--no-failure",
        action="store_true",
        help="No simular fallos; mostrar ejecución con todas las ramas exitosas.",
    )
    args = parser.parse_args()

    failure = None if args.no_failure else args.failure
    run_tot_demo(failure_source=failure, use_brain=args.use_brain)
