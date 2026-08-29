"""
Codificando.AI
UC-275: Autorreflexión de Agentes — Sistema Avanzado Self-Refine + Reflexion.
Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from config import get_config
from critic import SelfCritic
from evaluator import MetricEvaluator
from memory import ReflectionMemory
from models import ActionTrace, OutcomeObservation
from refiner import SelfRefiner
from reflexion_loop import ReflexionLoop, SelfReflectiveAgent


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta demo del sistema de autorreflexión."""
    config = get_config()

    print("=" * 65)
    print("DEMO: AUTORREFLEXIÓN DE AGENTES (UC-275)")
    print("Sistema Self-Refine + Reflexion para IA Agéntica")
    print("=" * 65)

    # Componentes
    memory = ReflectionMemory(max_episodes=config.memory.max_episodes)
    evaluator = MetricEvaluator(config.evaluation.default_weights)
    critic = SelfCritic()
    refiner = SelfRefiner(max_refinement_steps=config.refiner.max_refinement_steps)

    # --- DEMO 1: Ciclo completo de autorreflexión ---
    print("\n--- 1. Ciclo Completo de Autorreflexión (ReflexionLoop) ---")
    loop = ReflexionLoop(
        agent_id="trading_alpha",
        evaluator=evaluator,
        critic=critic,
        refiner=refiner,
        memory=memory,
        max_iterations=config.refiner.max_iterations,
        convergence_threshold=config.evaluation.convergence_threshold,
    )

    expected = {"correctness": 0.8, "completeness": 0.7, "clarity": 0.8, "efficiency": 0.7}

    # Simulador de acción
    call_count = [0]
    def action_fn(params):
        call_count[0] += 1
        base = 0.5 + call_count[0] * 0.1
        return {k: min(1.0, base + (hash(k) % 10) / 100.0) for k in expected}

    def observe_fn(trace, result):
        return OutcomeObservation(
            trace_id=trace.trace_id,
            actual_outcome=result,
            expected_outcome=expected,
            metrics={k: min(1.0, max(0.0, v)) for k, v in result.items()},
        )

    episode = loop.execute_with_reflection(
        action_fn=action_fn,
        observe_fn=observe_fn,
        action_params={"type": "trade", "risk_tolerance": 0.5, "position_size": 1.0},
        expected_outcome=expected,
        context={"market": "crypto", "timeframe": "1h"},
    )

    print(f"  Episode: {episode.episode_id}")
    print(f"  Outcome: {episode.final_outcome.value if episode.final_outcome else 'N/A'}")
    print(f"  Score:   {episode.final_score}")
    print(f"  Iterations: {episode.iterations}")
    print(f"  Duration: {episode.duration_seconds:.4f}s")
    print(f"  Hash:    {episode.reflection_hash[:32]}...")
    if episode.root_cause:
        print(f"  Root Cause: {episode.root_cause.category.value}")
    print(f"  Refinements: {len(episode.refinements)}")

    # --- DEMO 2: Self-Refine (texto) ---
    print("\n--- 2. Self-Refine (patrón generate→critique→refine) ---")
    sr_agent = SelfReflectiveAgent(
        agent_id="code_agent",
        threshold=0.80,
        max_iterations=3,
    )

    tasks = [
        "Implementa una función que duplique un número",
        "Escribe un detector de anomalías para series temporales",
        "Diseña un sistema de cache LRU con TTL",
    ]

    for task in tasks:
        result = sr_agent.run(task)
        print(f"  Task: {task[:50]}...")
        print(f"    Score: {result['score']}, Accepted: {result['accepted']}, "
              f"Iterations: {result['iterations']}, Outcome: {result['outcome']}")

    # --- DEMO 3: Evaluación standalone ---
    print("\n--- 3. Evaluación multi-criterio standalone ---")
    actual_metrics = {"correctness": 0.9, "completeness": 0.6, "clarity": 0.85, "efficiency": 0.75}
    expected_metrics = {"correctness": 0.8, "completeness": 0.8, "clarity": 0.7, "efficiency": 0.7}

    evaluation = evaluator.evaluate(actual_metrics, expected_metrics)
    print(f"  Outcome: {evaluation.outcome.value}")
    print(f"  Score:   {evaluation.score}")
    print(f"  Needs Reflection: {evaluation.needs_reflection}")
    print(f"  Deviations: {evaluation.deviations}")

    # --- DEMO 4: Análisis de causa raíz ---
    print("\n--- 4. Análisis de causa raíz ---")
    poor_metrics = {"correctness": 0.3, "completeness": 0.2, "clarity": 0.4, "efficiency": 0.3,
                    "prediction_error": 0.5, "model_confidence": 0.3}
    poor_expected = {"correctness": 0.8, "completeness": 0.8, "clarity": 0.7, "efficiency": 0.7,
                     "prediction_error": 0.1, "model_confidence": 0.8}

    poor_eval = evaluator.evaluate(poor_metrics, poor_expected)
    obs = OutcomeObservation(
        trace_id="demo",
        actual_outcome=poor_metrics,
        expected_outcome=poor_expected,
        metrics=poor_metrics,
    )
    root_cause = critic.analyze(poor_eval, obs)
    print(f"  Category: {root_cause.category.value}")
    print(f"  Primary Cause: {root_cause.primary_cause}")
    print(f"  Confidence: {root_cause.confidence}")
    print(f"  Contributing: {root_cause.contributing_factors}")

    # --- DEMO 5: Memoria episódica ---
    print("\n--- 5. Memoria episódica y lecciones aprendidas ---")

    # Ejecutar varios episodios para poblar la memoria
    for i in range(5):
        call_count[0] = i
        ep = loop.execute_with_reflection(
            action_fn=action_fn,
            observe_fn=observe_fn,
            action_params={"type": "trade", "risk_tolerance": 0.3 + i * 0.1},
            expected_outcome=expected,
        )

    stats = memory.get_system_stats()
    print(f"  Total Episodes: {stats['total_episodes']}")
    print(f"  Avg Score: {stats['avg_score']}")
    print(f"  Convergence Rate: {stats['convergence_rate']}")
    print(f"  Success Patterns: {stats['success_patterns']}")
    print(f"  Failure Patterns: {stats['failure_patterns']}")

    lessons = memory.get_lessons_learned("trade")
    print(f"  Lessons (trade): success_rate={lessons['success_rate']}, "
          f"episodes={lessons['total_episodes']}")

    # --- DEMO 6: Status completo ---
    print("\n--- 6. Status del Sistema ---")
    _print_json(stats)

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from api import app
    port = args.port or get_config().port
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-275",
        description="Autorreflexión de Agentes — Sistema Self-Refine + Reflexion"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Run self-reflection demo")

    serve_p = subparsers.add_parser("serve", help="Start the Flask API server")
    serve_p.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"run": cmd_run, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
