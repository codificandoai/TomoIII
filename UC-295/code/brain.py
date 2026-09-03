"""UC-294: Situational Awareness Middleware (SAM) para trading de ticks.

Demuestra:
1. Un standalone SAM con Self-Model, memoria episódica y workspace global.
2. El pipeline completo SAM + BDI + Juice + World Model vía agent_core.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.pretty import pprint

console = Console()


def standalone_sam_demo() -> None:
    """Demostración mínima del middleware de situacionalidad."""
    from sam import SituationalAwarenessMiddleware, MetacognitionModule, SafetySupervisor, Envelope
    from models import TradingRequest, Portfolio

    request = TradingRequest(
        symbols=["AAPL"],
        ticks=[],
        portfolio=Portfolio(cash=100_000.0),
    )
    sam = SituationalAwarenessMiddleware(agent_identity="UC294.Standalone")

    # Simular episodios recientes incluyendo un error
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

    console.print(Panel("[bold cyan]UC-294 — Situational Awareness Middleware (SAM) Demo[/bold cyan]"))
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


def pipeline_demo() -> None:
    """Demostración del pipeline SAM + BDI + Juice + World Model."""
    from agent_core import run_sam_aware_pipeline
    from config import get_config
    from market_data import SyntheticMarketDataGenerator
    from models import Portfolio, TradingRequest

    console.print(Panel("[bold cyan]UC-294 — Pipeline SAM-aware completo[/bold cyan]"))
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
    # Imprimir solo resumen clave para no saturar consola
    summary: Dict[str, Any] = {
        "status": output.get("status"),
        "request_id": output.get("request_id"),
        "sam_state": output.get("sam_state"),
        "bdi_state": output.get("bdi_state"),
        "juice_verdict": output.get("juice_verdict"),
        "selected_strategy": output.get("selected_strategy"),
    }
    pprint(summary)


def main() -> int:
    console.print(Panel("[bold white]UC-294 — Situational Awareness Middleware + AGI Trading[/bold white]"))
    standalone_sam_demo()
    console.print("\n")
    pipeline_demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
