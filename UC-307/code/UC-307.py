"""Codificando.AI — UC-307: Evaluación y evolución de agentes autónomos.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Este módulo implementa un marco de tres niveles para evaluar agentes autónomos:
1. Tasa de éxito de la tarea.
2. Puntuación de calidad (LLM Juez, simulado por defecto).
3. Métricas de eficiencia (tokens, llamadas a herramientas, latencia).

A partir de estas métricas calcula un fitness combinado y, a través de un
orquestador central, decide si el agente:
- Persiste
- Ajusta parámetros
- Se reentrena
- Muta
- Es eliminado
- Genera descendencia (cruce o crecimiento)

Uso:
    python UC-307.py --server          # Levanta la API Flask en 5307 y Prometheus en 8000
    python UC-307.py --demo            # Simula evaluaciones y decisiones evolutivas
    python UC-307.py --eval-file payload.json
"""
from __future__ import annotations

import argparse
import json
import random
import time
from typing import Optional

from prometheus_client import start_http_server
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent_evolution import AgentPopulation, DNAOperators
from api import app
from config import EVOLUTION
from evaluator import AgentPerformanceEvaluator
from metrics import METRICS
from models import AgentDNA, DecisionAction, EfficiencyMetrics, EvaluationInput

console = Console()


def print_evaluation_table(evaluations: list) -> None:
    """Muestra resultados de evaluación en una tabla legible."""
    table = Table(title="UC-307: Evaluación de Agentes Autónomos")
    table.add_column("Agente", style="cyan")
    table.add_column("Éxito", justify="center")
    table.add_column("Calidad", justify="center")
    table.add_column("Eficiencia", justify="center")
    table.add_column("Fitness", justify="center")
    table.add_column("Veredicto", style="bold")
    table.add_column("Acciones")

    for ev in evaluations:
        table.add_row(
            ev.agent_id,
            f"{ev.task_success_rate:.0%}",
            f"{ev.normalized_quality:.2f}",
            f"{ev.efficiency_score:.2f}",
            f"{ev.fitness:.2f}",
            ev.verdict.value,
            ", ".join(a.value for a in ev.actions),
        )
    console.print(table)


def run_demo(evaluator: AgentPerformanceEvaluator, population: AgentPopulation) -> None:
    """Ejecuta una demostración end-to-end con agentes de distinto perfil."""
    console.print(
        Panel(
            "[bold white]Demo UC-307: evaluación de 5 perfiles de agentes y decisiones evolutivas[/bold white]",
            border_style="cyan",
        )
    )

    profiles = [
        ("elite_agent", 0.95, 4.6, {"tokens_used": 900, "tool_calls": 2, "latency_seconds": 0.6}),
        ("decent_agent", 0.75, 3.5, {"tokens_used": 2500, "tool_calls": 4, "latency_seconds": 2.5}),
        ("slow_agent", 0.80, 4.0, {"tokens_used": 8000, "tool_calls": 12, "latency_seconds": 15.0}),
        ("bad_quality_agent", 0.55, 1.8, {"tokens_used": 1200, "tool_calls": 3, "latency_seconds": 1.0}),
        ("terminator_agent", 0.20, 1.2, {"tokens_used": 6000, "tool_calls": 8, "latency_seconds": 8.0}),
    ]

    operators = DNAOperators()
    results = []
    for name, success, quality, eff in profiles:
        dna = operators.default_dna(name)
        population.register(dna)

        payload = EvaluationInput(
            agent_id=name,
            task_success_rate=success,
            quality_score=quality,
            efficiency=EfficiencyMetrics(**eff),
            dna=dna,
        )
        ev = evaluator.evaluate(payload, population_size=population.size())
        results.append(ev)

        # Aplicar evolución según el veredicto principal
        primary = ev.verdict
        if primary in {DecisionAction.MUTATE, DecisionAction.ADJUST_PARAMS, DecisionAction.RETRAIN}:
            mate = population.select_mate(name)
            population.evolve_one(name, primary, reason=ev.reasoning, mate_id=mate.agent_id if mate else None)
        elif primary == DecisionAction.ELIMINATE:
            eliminated = population.eliminate(name)
            if eliminated:
                console.print(f"[red]Eliminado: {name}[/red]")
            # Si población baja, generar reemplazo
            if population.size() < 3:
                new_dna = operators.default_dna()
                population.register(new_dna)
                console.print(f"[green]Nuevo agente aleatorio generado: {new_dna.agent_id}[/green]")

    print_evaluation_table(results)

    console.print(
        Panel(
            f"[bold white]Población final:[/bold white] {population.size()} agentes\n"
            "Métricas Prometheus disponibles en http://localhost:8000/metrics",
            border_style="green",
        )
    )


def run_server(prom_port: int = 8000, api_port: int = 5307) -> None:
    """Levanta el servidor de métricas Prometheus y la API Flask."""
    console.print(
        Panel(
            f"[bold white]Servidor de métricas Prometheus:[/bold white] http://localhost:{prom_port}/metrics\n"
            f"[bold white]API REST UC-307:[/bold white] http://localhost:{api_port}",
            title="⚙️ SERVIDORES ACTIVOS",
            border_style="blue",
        )
    )
    start_http_server(prom_port)
    app.run(host="0.0.0.0", port=api_port, debug=False)


def run_eval_file(path: str) -> None:
    """Carga un JSON de entrada y ejecuta la evaluación por CLI."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    payload = EvaluationInput.model_validate(data)
    evaluator = AgentPerformanceEvaluator()
    ev = evaluator.evaluate(payload)
    print_evaluation_table([ev])
    console.print_json(data=ev.model_dump_json_safe())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="UC-307: Evaluación y evolución de agentes autónomos"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server", action="store_true", help="Levanta Prometheus + Flask API")
    group.add_argument("--demo", action="store_true", help="Ejecuta demo de evaluación/evolución")
    group.add_argument("--eval-file", type=str, help="Archivo JSON con payload de evaluación")
    parser.add_argument("--prom-port", type=int, default=8000, help="Puerto Prometheus")
    parser.add_argument("--api-port", type=int, default=5307, help="Puerto API Flask")

    args = parser.parse_args()

    if args.server:
        run_server(args.prom_port, args.api_port)
    elif args.demo:
        evaluator = AgentPerformanceEvaluator()
        population = AgentPopulation()
        run_demo(evaluator, population)
        # Mantener vivo unos segundos para que Prometheus pueda scrapear si corre
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Demo finalizado.[/yellow]")
    elif args.eval_file:
        run_eval_file(args.eval_file)


if __name__ == "__main__":
    main()
