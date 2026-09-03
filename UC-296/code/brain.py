"""UC-295: Cerebro AGI unificado del proyecto de trading multi-agente.

Este archivo es el punto de entrada principal para ejecutar y demostrar el
cerebro completo. A medida que el proyecto crece, cada caso de uso (UC-292,
UC-293, UC-294, UC-295...) añade una capa; `brain.py` las ensambla y expone
modos de ejecución independientes o conjuntos.

Capas actuales:
- UC-292: World Model probabilístico + CentralBrain.
- UC-293: BDI + Filtro Adversarial Juice.
- UC-294: Situational Awareness Middleware (SAM).
- UC-295: ReAct Híbrido con Árbol de Pensamientos (ToT) para predicción ask/bid.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.pretty import pprint

console = Console()


# ---------------------------------------------------------------------------
# Capa UC-294 — SAM standalone
# ---------------------------------------------------------------------------
def demo_sam() -> Dict[str, Any]:
    """Demostración mínima del middleware de situacionalidad (SAM)."""
    from sam import Envelope, MetacognitionModule, SafetySupervisor, SituationalAwarenessMiddleware
    from models import Portfolio, TradingRequest

    console.print(
        Panel(
            "[bold cyan]UC-294 — Situational Awareness Middleware (SAM) Demo[/bold cyan]"
        )
    )

    request = TradingRequest(
        symbols=["AAPL"],
        ticks=[],
        portfolio=Portfolio(cash=100_000.0),
    )
    sam = SituationalAwarenessMiddleware(agent_identity="UC294.Standalone")

    # Simular episodios recientes incluyendo errores
    sam.store_episode("ACTION", "Orden BUY ejecutada sin stop-loss")
    sam.store_episode("OBSERVATION", "ERROR: caída inesperada del 8% en AAPL")
    sam.store_episode("OBSERVATION", "ERROR: slippage superior al 3%")
    sam.store_episode("PERCEPTION", "Competidor X bajó precios")

    workspace = sam.build_workspace(
        request=request,
        snapshots={
            "AAPL": {
                "symbol": "AAPL",
                "latest_price": 150.0,
                "features": {"volatility": 0.06, "rsi": 70.0, "trend_direction": -1},
                "regime": "high_volatility",
            }
        },
        signals=[{"side": "BUY", "confidence": 0.9, "agent": "technical"}],
        alerts=["API de mercado degradada"],
    )
    meta = MetacognitionModule().evaluate(workspace)
    safety = SafetySupervisor().check(
        workspace.selected_hypothesis or {}, request, workspace.perception.get("snapshots", {})
    )

    console.print("[bold]Self-Model:[/bold]")
    pprint(sam.self_model.to_dict())
    console.print("[bold]Metacognition:[/bold]")
    pprint(meta)
    console.print("[bold]Safety:[/bold]")
    pprint(safety)
    console.print("[bold]Envelope ejemplo:[/bold]")
    envelope = Envelope().pack(
        source="global_workspace",
        destination="risk_module",
        message_type="broadcast",
        payload=workspace.to_dict(),
    )
    pprint(envelope)

    return {
        "mode": "sam",
        "self_model": sam.self_model.to_dict(),
        "metacognition": meta,
        "safety": safety,
        "envelope": envelope,
    }


# ---------------------------------------------------------------------------
# Capa UC-292/UC-293 — Trading con BDI + Juice + World Model
# ---------------------------------------------------------------------------
def demo_trading() -> Dict[str, Any]:
    """Demostración del pipeline completo SAM + BDI + Juice + World Model."""
    from agent_core import run_sam_aware_pipeline
    from config import get_config
    from market_data import SyntheticMarketDataGenerator
    from models import Portfolio, TradingRequest

    console.print(
        Panel(
            "[bold cyan]UC-293/UC-294 — Pipeline SAM + BDI + Juice + World Model[/bold cyan]"
        )
    )

    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=100)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
        mode="paper",
        approved=False,
    )

    output = run_sam_aware_pipeline(request, cfg)
    summary: Dict[str, Any] = {
        "mode": "trading",
        "status": output.get("status"),
        "request_id": output.get("request_id"),
        "sam_state": output.get("sam_state"),
        "bdi_state": output.get("bdi_state"),
        "juice_verdict": output.get("juice_verdict"),
        "selected_strategy": output.get("selected_strategy"),
    }
    pprint(summary)
    return summary


# ---------------------------------------------------------------------------
# Capa UC-295 — ReAct Híbrido + Tree of Thoughts (ToT)
# ---------------------------------------------------------------------------
def demo_tot(use_brain: bool = False) -> Dict[str, Any]:
    """Demostración de predicción ask/bid con ReAct Híbrido + ToT."""
    from central_brain import CentralBrain
    from config import get_config
    from market_data import SyntheticMarketDataGenerator
    from react_tot import ReActReasonactToTBrain, TickPredictionEnvironment

    console.print(
        Panel(
            "[bold cyan]UC-295 — ReAct Híbrido + Tree of Thoughts (ToT)[/bold cyan]\n"
            f"Predictor CentralBrain: {use_brain}"
        )
    )

    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=80, start_price=150.0)

    real_brain = CentralBrain(cfg) if use_brain else None
    env = TickPredictionEnvironment(
        brain=real_brain,
        failure_sources=["technical"],
        latency_ms=0.0,
    )
    tot = ReActReasonactToTBrain(env, confidence_threshold=0.5, max_depth=2)

    predictors = ["brain", "technical", "microstructure"] if use_brain else ["world_model", "technical", "microstructure"]
    result = tot.predict(
        symbol="AAPL",
        ticks=ticks,
        news=[],
        predictors=predictors,
    )

    console.print("[bold]Predicción final ask/bid:[/bold]")
    pprint(result.get("final_prediction"))
    console.print("[bold]Resumen del árbol:[/bold]")
    pprint(result.get("tree_summary"))
    console.print("[bold]Traza ReAct:[/bold]")
    for step in result.get("trace", []):
        pprint(step)

    return {"mode": "tot", **result}


# ---------------------------------------------------------------------------
# Cerebro AGI completo — todas las capas unidas
# ---------------------------------------------------------------------------
def demo_full_agi() -> Dict[str, Any]:
    """Ejecuta SAM -> BDI -> Juice -> World Model -> ToT con un único CentralBrain.

    Mantiene la funcionalidad heredada de cada UC y la encadena:
    1. El mismo `CentralBrain` observa el mercado.
    2. `run_sam_aware_pipeline` ejecuta SAM, BDI, Juice y el grafo de trading.
    3. El mismo `CentralBrain` se pasa al árbol de pensamientos ToT para refinar
       la predicción ask/bid del siguiente tick.
    """
    from central_brain import CentralBrain
    from agent_core import run_sam_aware_pipeline
    from config import get_config
    from market_data import SyntheticMarketDataGenerator
    from models import Portfolio, TradingRequest
    from react_tot import ReActReasonactToTBrain, TickPredictionEnvironment

    console.print(
        Panel(
            "[bold white]Cerebro AGI Unificado — SAM + BDI + Juice + World Model + ToT[/bold white]"
        )
    )

    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=100, start_price=150.0)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
        mode="paper",
        approved=False,
    )

    # Fase 1: SAM + BDI + Juice + World Model (reutiliza el mismo cerebro)
    brain = CentralBrain(cfg)
    trading_output = run_sam_aware_pipeline(request, cfg, central_brain=brain)

    console.print("[bold]Fase 1 — Trading pipeline (SAM/BDI/Juice/WM):[/bold]")
    pprint(
        {
            "status": trading_output.get("status"),
            "request_id": trading_output.get("request_id"),
            "selected_strategy": trading_output.get("selected_strategy"),
            "requires_confirmation": trading_output.get("requires_confirmation"),
        }
    )

    # Fase 2: ToT sobre el mismo cerebro para refinar ask/bid del siguiente tick
    env = TickPredictionEnvironment(
        brain=brain,
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
    tot_result = tot.predict(
        symbol="AAPL",
        ticks=ticks,
        news=[],
        predictors=["brain", "technical", "microstructure"],
    )

    console.print("[bold]Fase 2 — ToT ask/bid prediction:[/bold]")
    pprint(tot_result.get("final_prediction"))
    console.print("[bold]Resumen del árbol:[/bold]")
    pprint(tot_result.get("tree_summary"))

    return {
        "mode": "full_agi",
        "trading": {
            "status": trading_output.get("status"),
            "request_id": trading_output.get("request_id"),
            "selected_strategy": trading_output.get("selected_strategy"),
            "sam_state": trading_output.get("sam_state"),
            "bdi_state": trading_output.get("bdi_state"),
            "juice_verdict": trading_output.get("juice_verdict"),
        },
        "tot": {
            "final_prediction": tot_result.get("final_prediction"),
            "tree_summary": tot_result.get("tree_summary"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cerebro AGI unificado del proyecto trading multi-agente."
    )
    parser.add_argument(
        "--mode",
        choices=["sam", "trading", "tot", "full", "all"],
        default="full",
        help=(
            "Modo de ejecución: sam (UC-294 standalone), trading (UC-293/294), "
            "tot (UC-295), full (todas las capas unidas), all (ejecuta todos los demos)."
        ),
    )
    parser.add_argument(
        "--use-brain",
        action="store_true",
        help="En modo tot, usa CentralBrain real como predictor (más lento).",
    )
    args = parser.parse_args(argv)

    if args.mode == "sam":
        demo_sam()
    elif args.mode == "trading":
        demo_trading()
    elif args.mode == "tot":
        demo_tot(use_brain=args.use_brain)
    elif args.mode == "full":
        demo_full_agi()
    elif args.mode == "all":
        demo_sam()
        console.print("\n")
        demo_trading()
        console.print("\n")
        demo_tot(use_brain=False)
        console.print("\n")
        demo_full_agi()

    return 0


if __name__ == "__main__":
    sys.exit(main())
