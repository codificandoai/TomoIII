"""UC-293: Demostración de agente BDI + ReAct + CoT + Filtro Adversarial Juice.

Este script orquesta el núcleo integrador (`agent-core.py`) y también muestra
un ejemplo autónomo de pricing BDI para ilustrar el concepto de Juice.
"""
from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.pretty import pprint

console = Console()


def demo_bdi_pricing() -> None:
    """Ejemplo mínimo BDI de pricing con filtro confrontacional (Juice)."""
    import json
    from dataclasses import dataclass, field
    from typing import Any, Dict, List

    @dataclass
    class Beliefs:
        product_sku: str = "SKU-X1"
        cost: float = 100.0
        current_price: float = 120.0
        competitor_price: float = 90.0
        elasticity: float = -1.8
        inventory_level: str = "LOW"

    @dataclass
    class Desires:
        primary_goal: str = "Maximizar el margen bruto operativo."
        secondary_goal: str = "Mantener la cuota de mercado (no bajar del 15%)."
        hard_constraint: str = "NUNCA vender por debajo del costo."

    @dataclass
    class Intention:
        is_committed: bool = False
        planned_action: str = "HOLD"
        planned_params: Dict[str, Any] = field(default_factory=dict)
        justification: str = ""
        survival_score: int = 0

    class ConfrontationalJuice:
        def evaluate_and_distill(self, beliefs: Beliefs, desires: Desires, draft: Intention) -> Intention:
            price = draft.planned_params.get("price", 0)
            if draft.planned_action == "SET_PRICE" and price <= beliefs.cost:
                return Intention(
                    planned_action="ESCALATE_HUMAN",
                    planned_params=draft.planned_params,
                    justification="JUICE RECHAZADO: el precio propuesto está por debajo del costo.",
                    survival_score=0,
                )
            if draft.planned_action == "SET_PRICE" and beliefs.inventory_level == "LOW" and price < beliefs.current_price:
                return Intention(
                    planned_action="HOLD",
                    planned_params={},
                    justification="JUICE CORREGIDO: inventario bajo + precio menor = pérdida de margen.",
                    survival_score=85,
                )
            return Intention(
                planned_action=draft.planned_action,
                planned_params=draft.planned_params,
                justification="JUICE APROBADO: coherencia perfecta con creencias y deseos.",
                survival_score=100,
            )

    class BDI_PricingAgent:
        def __init__(self) -> None:
            self.beliefs = Beliefs()
            self.desires = Desires()
            self.intention = Intention()
            self.juice_engine = ConfrontationalJuice()
            self.action_history: List[Dict[str, Any]] = []

        def run_reasoning_cycle(self) -> None:
            draft = Intention(
                planned_action="SET_PRICE",
                planned_params={"price": 85.0},
                justification="Igualar al competidor para salvar cuota.",
            )
            distilled = self.juice_engine.evaluate_and_distill(self.beliefs, self.desires, draft)
            if distilled.survival_score >= 80:
                self.intention = distilled
                self.intention.is_committed = True
                console.print(Panel(f"[bold green]APROBADO[/bold green]: {distilled.justification}\nAcción: {distilled.planned_action}", title="BDI Pricing Demo"))
            else:
                console.print(Panel(f"[bold red]RECHAZADO[/bold red]: {distilled.justification}", title="BDI Pricing Demo"))
            self.action_history.append({"action": distilled.planned_action, "justification": distilled.justification})

    agent = BDI_PricingAgent()
    agent.run_reasoning_cycle()


def demo_trading_core() -> None:
    """Demostración completa del núcleo de trading BDI+Juice+World Model."""
    console.print(Panel("[bold cyan]UC-293 — Núcleo de Trading BDI + Juice + World Model[/bold cyan]"))
    from agent_core import run_bdi_trading_pipeline
    from config import get_config
    from market_data import SyntheticMarketDataGenerator
    from models import Portfolio, TradingRequest

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


def main() -> int:
    console.print(Panel("[bold white]UC-293 LLM Juice — Destilación Confrontacional[/bold white]"))
    demo_bdi_pricing()
    console.print("\n")
    demo_trading_core()
    return 0


if __name__ == "__main__":
    sys.exit(main())
