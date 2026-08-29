"""
Codificando.AI
UC-276: Solicitud Recursiva — Recursive Prompting para Flujos de Trabajo Agénticos.
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
from models import QualityCriteria, RefinementStrategy
from quality import QualityEvaluator
from recursive_prompter import RecursivePrompter, RSILoop
from refiner import Refiner
from stagnation import StagnationDetector


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta demo del sistema de recursive prompting."""
    config = get_config()

    print("=" * 70)
    print("DEMO: SOLICITUD RECURSIVA — RECURSIVE PROMPTING (UC-276)")
    print("Ciclo: GENERATE -> EVALUATE -> REFINE -> COMMIT")
    print("=" * 70)

    # Criterios de calidad
    criteria = [
        QualityCriteria(name=name, weight=v["weight"],
                        min_threshold=v["min_threshold"], target=v["target"])
        for name, v in config.quality.default_criteria.items()
    ]

    # --- DEMO 1: Ciclo Recursivo Completo ---
    print("\n--- 1. Ciclo Recursivo Completo (RecursivePrompter) ---")
    prompter = RecursivePrompter(
        agent_id="research_agent",
        criteria=criteria,
        max_iterations=config.refiner.max_iterations,
        target_score=config.quality.target_score,
        min_acceptable_score=config.quality.min_acceptable_score,
    )

    input_text = (
        "El machine learning es un subcampo de la inteligencia artificial "
        "que permite a los sistemas aprender de datos sin ser programados "
        "explícitamente. Utiliza algoritmos para identificar patrones en "
        "conjuntos de datos y hacer predicciones. Las aplicaciones incluyen "
        "reconocimiento de imágenes, procesamiento de lenguaje natural, "
        "sistemas de recomendación y detección de fraude. El deep learning, "
        "una variante del machine learning, usa redes neuronales profundas "
        "para modelar abstracciones complejas en los datos."
    )

    session = prompter.run(
        input_data=input_text,
        task_description="Genera un resumen ejecutivo claro y conciso",
        context={"audience": "ejecutivos", "objective": "decisión de inversión"},
    )

    print(f"  Session: {session.session_id}")
    print(f"  Status: {session.status.value}")
    print(f"  Final Score: {session.final_score:.4f}")
    print(f"  Iterations: {session.total_iterations}")
    print(f"  Duration: {session.total_duration_seconds:.4f}s")
    print(f"  Convergence: {session.convergence_reason}")
    print(f"  Hash: {session.session_hash[:32]}...")
    print(f"  Trajectory: {session.improvement_trajectory}")
    if session.final_version:
        print(f"  Final Content: {session.final_version.content[:100]}...")

    # --- DEMO 2: Refinamiento individual ---
    print("\n--- 2. Refinamiento Individual (8 estrategias) ---")
    refiner = Refiner()
    evaluator = QualityEvaluator(criteria)

    from models import RecursiveVersion
    test_content = (
        "El machine learning permite a los sistemas aprender de datos "
        "y hacer predicciones sin programación explícita utilizando algoritmos "
        "que identifican patrones complejos en grandes conjuntos de datos."
    )
    version = RecursiveVersion.create(iteration=0, content=test_content)

    for strategy in [RefinementStrategy.CLARIFY, RefinementStrategy.CONCISE,
                     RefinementStrategy.RESTRUCTURE, RefinementStrategy.EXPAND]:
        quality = evaluator.evaluate(version, input_text)
        refined = refiner.refine(version, quality, "Resumen ejecutivo", strategy)
        refined_v = RecursiveVersion.create(iteration=1, content=refined, strategy=strategy)
        refined_q = evaluator.evaluate(refined_v, input_text)
        delta = refined_q.overall_score - quality.overall_score
        print(f"  {strategy.value:14s} | Original: {quality.overall_score:.3f} | "
              f"Refined: {refined_q.overall_score:.3f} | Delta: {delta:+.3f}")

    # --- DEMO 3: RSI Loop (Recursive Self-Improvement) ---
    print("\n--- 3. RSI Loop (Gödel Agent Pattern) ---")
    rsi = RSILoop(agent_id="code_agent", max_cycles=5, improvement_threshold=0.03)

    rsi_result = rsi.run_cycle(
        task="Optimiza un resumen de machine learning",
        current_output=test_content,
    )

    print(f"  Agent: {rsi_result['agent_id']}")
    print(f"  Baseline Score: {rsi_result['baseline_score']}")
    print(f"  Final Score: {rsi_result['final_score']}")
    print(f"  Improvement: {rsi_result['total_improvement']}")
    print(f"  Cycles Run: {rsi_result['cycles_run']}")
    print(f"  Accepted Changes: {rsi_result['accepted_changes']}")
    print(f"  Logic Version: {rsi_result['logic_version']}")

    # --- DEMO 4: Detección de Estancamiento ---
    print("\n--- 4. Detección de Estancamiento ---")
    detector = StagnationDetector.from_config()

    trajectories = {
        "Progresiva": [0.5, 0.6, 0.7, 0.8, 0.85],
        "Plateau": [0.5, 0.55, 0.56, 0.56, 0.565],
        "Oscilación": [0.6, 0.62, 0.61, 0.62, 0.61],
        "Degradación": [0.5, 0.6, 0.7, 0.55],
    }

    for name, traj in trajectories.items():
        is_stag, reason = detector.is_stagnated(traj)
        print(f"  {name:14s} | Stagnated: {is_stag:5} | {reason[:60] if reason else 'OK'}")

    # --- DEMO 5: Evaluación Multi-criterio ---
    print("\n--- 5. Evaluación Multi-criterio ---")
    texts = [
        ("Corto y claro", "ML es IA que aprende de datos."),
        ("Largo y detallado", input_text),
        ("Con conectores", "Primero, ML es IA. Además, usa algoritmos. Finalmente, hace predicciones."),
    ]

    for label, text in texts:
        v = RecursiveVersion.create(iteration=0, content=text)
        q = evaluator.evaluate(v, input_text)
        print(f"  {label:18s} | Score: {q.overall_score:.3f} | Level: {q.quality_level.value:12s} | "
              f"Issues: {len(q.issues)} | Strengths: {len(q.strengths)}")

    # --- DEMO 6: Estadísticas ---
    print("\n--- 6. Estadísticas del Prompter ---")
    # Ejecutar sesiones adicionales para poblar estadísticas
    for i in range(4):
        prompter.run(
            input_data=f"Texto de prueba número {i+1} con contenido variado sobre tecnología y datos.",
            task_description=f"Resumen breve {i+1}",
        )

    stats = prompter.get_stats()
    _print_json(stats)

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Inicia servidor API Flask."""
    from api import app
    port = args.port or get_config().port
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-276",
        description="Solicitud Recursiva — Recursive Prompting para Flujos Agénticos"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Run recursive prompting demo")

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
