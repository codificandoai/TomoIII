"""agent-core.py — Núcleo integrador BDI + Juice + World Model para UC-293.

Expone el orquestador que combina:
- Percepción de mercado (ticks, noticias, indicadores técnicos).
- World model neuronal para predicción de ticks y simulación.
- Agente BDI con Beliefs, Desires e Intentions.
- Filtro adversarial Confrontational Juice (ReAct + CoT).
- Grafo LangGraph de trading con compuerta de riesgo y ejecución.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import AppConfig, get_config
from graph import build_agent, run_agent
from market_data import SyntheticMarketDataGenerator
from models import (
    BDIBeliefs,
    BDIDesires,
    BDIIntention,
    BDIState,
    CandidateStrategy,
    CoTStep,
    JuiceVerdict,
    MarketSnapshot,
    Portfolio,
    TradingRequest,
)


def build_bdi_from_request(
    request: TradingRequest,
    selected_strategy: Optional[Dict[str, Any]] = None,
    signals: Optional[List[Dict[str, Any]]] = None,
    evaluations: Optional[List[Dict[str, Any]]] = None,
    snapshots: Optional[Dict[str, Any]] = None,
) -> BDIState:
    """Construye el estado BDI completo a partir de una solicitud y estado parcial.

    Útil para exponer el estado BDI vía API sin ejecutar todo el pipeline.
    """
    from bdi import BDIBuilder, BDIStateBuilder
    from central_brain import CentralBrain

    symbol = request.symbols[0] if request.symbols else "AAPL"
    portfolio = request.portfolio or Portfolio()
    brain = CentralBrain(request.config if hasattr(request, "config") else get_config())
    snap_data = (snapshots or {}).get(symbol, {})
    if not snap_data:
        snap_data = brain.observe(request).get(symbol)
        if snap_data is None:
            raise ValueError(f"No se pudo construir snapshot para {symbol}")
    else:
        snap_data = MarketSnapshot(**snap_data)

    beliefs = BDIBuilder.build_beliefs(
        symbol=symbol,
        snapshot=snap_data,
        portfolio_cash=portfolio.cash,
        portfolio_position=portfolio.positions.get(symbol, 0.0),
        world_model=brain.world_model,
        cost_basis=portfolio.average_cost.get(symbol, snap_data.latest_price * 0.95),
    )
    desires = BDIBuilder.build_desires(request, request.constraints)

    intention: Optional[BDIIntention] = None
    if selected_strategy:
        cot_trace = BDIBuilder.build_cot_trace(signals or [], evaluations or [], selected_strategy)
        intention = BDIBuilder.build_intention(
            CandidateStrategy(**selected_strategy),
            cot_trace=cot_trace,
        )
    else:
        intention = BDIIntention(justification="Sin estrategia seleccionada todavía.")

    return BDIStateBuilder.build(beliefs=beliefs, desires=desires, draft=intention)


def run_bdi_trading_pipeline(
    request: TradingRequest,
    config: Optional[AppConfig] = None,
    recursion_limit: int = 50,
) -> Dict[str, Any]:
    """Ejecuta el pipeline completo de trading BDI + Juice + World Model."""
    cfg = config or get_config()
    final_state = run_agent(request, cfg, recursion_limit=recursion_limit)
    return final_state.get("final_output") or {}


def main() -> int:
    """Demostración rápida del núcleo BDI+Juice."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.pretty import pprint

    console = Console()
    console.print(Panel("[bold cyan]UC-293 — BDI + Juice + World Model Core Demo[/bold cyan]"))

    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
        mode="paper",
        approved=False,
    )

    output = run_bdi_trading_pipeline(request, cfg)
    pprint(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
