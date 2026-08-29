"""
Codificando.AI
UC-277: Memoria Multi-Turno a Largo Plazo para Agentes.
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
import time
from typing import Any

from config import get_config
from memory_system import MultiLayerMemorySystem
from models import GoalStatus, MemoryImportance


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta demo del sistema de memoria multi-turno."""
    print("=" * 70)
    print("DEMO: MEMORIA MULTI-TURNO A LARGO PLAZO (UC-277)")
    print("5 Capas: Working -> Episodic -> Semantic -> Procedural -> Goal")
    print("=" * 70)

    ms = MultiLayerMemorySystem(agent_id="demo_agent")

    # --- DEMO 1: Working Memory ---
    print("\n--- 1. Memoria de Trabajo (Working Memory) ---")
    ms.working.put("user_name", "Carlos", priority=0.9)
    ms.working.put("current_task", "analisis de portfolio", priority=0.8)
    ms.working.put("risk_level", "moderado", priority=0.7)
    print(f"  Session: {ms.working.session_id}")
    print(f"  Items: {ms.working.get_context_snapshot()['items']}")

    # --- DEMO 2: Episodic Memory (multi-sesion) ---
    print("\n--- 2. Memoria Episodica (Multi-Sesion) ---")
    interactions = [
        ("Usuario solicito analisis de BTC/USD con horizonte semanal",
         "trade", ["btc", "analysis"], MemoryImportance.HIGH, 0.5),
        ("Agente detecto patron de soporte en 42000 USD",
         "analysis", ["btc", "pattern"], MemoryImportance.HIGH, 0.7),
        ("Usuario indico preferencia por operaciones conservadoras",
         "preference", ["risk", "conservative"], MemoryImportance.CRITICAL, 0.3),
        ("Sesion de backtesting con estrategia momentum resultó positiva",
         "backtest", ["momentum", "success"], MemoryImportance.MEDIUM, 0.8),
        ("Usuario pregunto sobre diversificacion ETH/SOL",
         "interaction", ["eth", "sol", "diversification"], MemoryImportance.MEDIUM, 0.2),
    ]

    for summary, ep_type, tags, importance, sentiment in interactions:
        ep_id = ms.store_interaction(
            summary=summary, episode_type=ep_type,
            tags=tags, importance=importance, sentiment=sentiment,
        )
        print(f"  Stored: {ep_id[:12]}... | {ep_type:12s} | {summary[:50]}...")

    # --- DEMO 3: Recall Semantico ---
    print("\n--- 3. Recall Semantico ---")
    queries = ["BTC analisis precio", "preferencias de riesgo", "estrategias exitosas"]
    for q in queries:
        results = ms.recall(q, top_k=2)
        eps = results.get("episodic", [])
        print(f"  Query: '{q}'")
        for ep in eps:
            print(f"    -> {ep['summary'][:60]}... [{ep['importance']}]")

    # --- DEMO 4: Semantic Memory (hechos permanentes) ---
    print("\n--- 4. Memoria Semantica (Hechos Permanentes) ---")
    facts = [
        "El usuario prefiere operaciones conservadoras con stop-loss",
        "BTC tiene soporte historico en 42000 USD",
        "Estrategia momentum funciona mejor en mercados alcistas",
        "El usuario invierte max 5% del portfolio por operacion",
    ]
    for fact in facts:
        node_id = ms.semantic.add_fact(ms.agent_id, fact)
        print(f"  Fact: {node_id[:25]}... | {fact[:55]}...")

    # Consulta semantica
    print("\n  Query semantica: 'gestion de riesgo'")
    sem_results = ms.semantic.query(ms.agent_id, "gestion de riesgo", top_k=3)
    for r in sem_results:
        print(f"    -> {r['content'][:55]}... [conf={r['confidence']:.2f}]")

    # --- DEMO 5: Procedural Memory (habilidades) ---
    print("\n--- 5. Memoria Procedural (Habilidades Aprendidas) ---")
    skills = [
        ("Analisis Tecnico BTC", "Identificar soportes y resistencias en BTC/USD",
         "trading", {"timeframe": "4h", "indicators": ["RSI", "MACD"]}),
        ("Risk Management", "Calcular position size con max 2% de riesgo",
         "risk", {"max_risk_pct": 2.0, "use_atr": True}),
        ("Backtesting Momentum", "Ejecutar backtest de estrategia momentum",
         "research", {"lookback": 20, "threshold": 0.05}),
    ]
    for name, desc, category, params in skills:
        skill_id = ms.procedural.learn_skill(
            ms.agent_id, name, desc, category, params
        )
        print(f"  Learned: {name:25s} | {category:10s} | mastery={ms.procedural.skills[skill_id].mastery_level}")

    # Recupera mejor skill para contexto
    best = ms.procedural.retrieve_best(ms.agent_id, "analizar precio BTC", top_k=1)
    if best:
        print(f"\n  Best skill for 'analizar precio BTC': {best[0].name}")

    # --- DEMO 6: Goal Memory (metas a largo plazo) ---
    print("\n--- 6. Memoria de Objetivos (Metas a Largo Plazo) ---")
    goals_data = [
        ("Alcanzar 10% ROI mensual", "Generar retornos consistentes del 10% mensual", 0.8),
        ("Dominar analisis tecnico", "Mejorar precision de predicciones tecnicas", 0.6),
        ("Reducir drawdown max a 5%", "Mantener drawdown maximo bajo 5%", 0.9),
    ]
    for title, desc, priority in goals_data:
        goal_id = ms.goals.create_goal(ms.agent_id, title, desc, priority=priority)
        ms.goals.update_progress(goal_id, 0.3, "Progreso inicial registrado")
        print(f"  Goal: {title:35s} | priority={priority} | progress=0.3")

    # --- DEMO 7: Consolidacion ---
    print("\n--- 7. Consolidacion (Episodic -> Semantic) ---")
    result = ms.consolidate()
    print(f"  Episodes processed: {result['episodes_processed']}")
    print(f"  Consolidated to semantic: {result['consolidated_to_semantic']}")

    # --- DEMO 8: Multi-sesion ---
    print("\n--- 8. Multi-Sesion (Persistencia) ---")
    session_1 = ms.working.session_id
    print(f"  Session 1: {session_1}")

    session_2 = ms.new_session()
    print(f"  Session 2: {session_2}")
    ms.store_interaction("Nueva sesion: usuario retoma analisis BTC", episode_type="session_start")

    # Recupera episodios de sesion anterior
    old_episodes = ms.episodic.recall_by_session(session_1)
    print(f"  Episodes in session 1: {len(old_episodes)}")
    new_episodes = ms.episodic.recall_by_session(session_2)
    print(f"  Episodes in session 2: {len(new_episodes)}")

    # --- DEMO 9: Estadisticas ---
    print("\n--- 9. Estadisticas del Sistema ---")
    stats = ms.get_system_stats()
    _print_json({k: v for k, v in stats.items() if k != "working_memory"})

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Inicia servidor API Flask."""
    from api import app
    port = args.port or get_config().port
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-277",
        description="Memoria Multi-Turno a Largo Plazo para Agentes"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Run memory system demo")
    serve_p = subparsers.add_parser("serve", help="Start Flask API server")
    serve_p.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"run": cmd_run, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
