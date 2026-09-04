"""Codificando.AI — UC-314: Razonamiento Causal y Planificación Recursiva Neuro-Simbólica.

Productos:
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
import time

from causal_model import LLMReasoner, SymbolicCausalModel
from neuro_symbolic_integrator import NeuroSymbolicIntegrator
from tool_registry import ToolRegistry, default_tools


def build_causal_world() -> SymbolicCausalModel:
    """Construye el escenario de dependencias causales del ejemplo de ruptura."""
    scm = SymbolicCausalModel()
    scm.add_dependency("SecurityPolicy", "TokenSession")
    scm.add_dependency("TokenSession", "ApiCache")
    scm.add_dependency("ApiCache", "PricingAPI")
    scm.add_dependency("PricingAPI", "AgentExecutor")
    scm.set_node_state("SecurityPolicy", "FALLO: Rotación forzada por detección de anomalía")
    return scm


def demo_root_cause() -> None:
    """Demostración de trazado de causa raíz LLM + SCM."""
    scm = build_causal_world()
    integrator = NeuroSymbolicIntegrator(scm=scm, tool_registry=ToolRegistry(default_tools()))

    print("\n[UC-314] DEMO: Ruptura de agente y trazado causal neuro-simbólico\n")
    error = "ConnectionTimeout: No se pudo establecer conexión con PricingAPI"
    context = "El agente calculaba precios para el cliente Enterprise-X."
    result = integrator.handle_breakdown("TASK-9281", "PricingAPI", error, context)

    print(f"Tarea: {result['task_id']}")
    print(f"Herramienta fallida: {result['failed_tool']}")
    print(f"Error: {result['error_msg']}")
    print(f"Hipótesis LLM: {result['llm_hypothesis']['reasoning']} (confianza={result['llm_hypothesis']['confidence']})")
    print(f"Trazo causal formal: {' -> '.join(result['formal_causal_trace'])}")
    print(f"Causa raíz real: {result['actual_root_cause']}")
    print(f"¿LLM y SCM coinciden?: {result['llm_scm_agreement']}")
    print(f"¿SCM intervino?: {result['scm_intervention']}")
    print(f"Latencia: {result['latency_seconds']}s\n")


def demo_recursive_planning() -> None:
    """Demostración de planificación recursiva con verificación causal."""
    scm = build_causal_world()
    # Registramos dependencia de servicio de marketing para ilustrar validación causal
    scm.add_dependency("PricingAPI", "MarketingService")
    scm.set_node_state("MarketingService", "OK")

    integrator = NeuroSymbolicIntegrator(scm=scm, tool_registry=ToolRegistry(default_tools()))

    print("\n[UC-314] DEMO: Planificación recursiva de campaña de marketing\n")
    goal = "Incrementar ventas del producto Enterprise-X mediante marketing digital"
    result = integrator.plan_and_evaluate(goal)

    print(f"Objetivo: {result['goal']}")
    print(f"Métricas: {result['metrics']}")
    _print_plan(result["plan"], indent=0)
    print()


def _print_plan(node: dict, indent: int) -> None:
    prefix = "  " * indent
    status = node.get("status")
    tool = node.get("tool_name") or "—"
    print(f"{prefix}- {node['goal']} [{status}] (tool={tool})")
    for child in node.get("children", []):
        _print_plan(child, indent + 1)


def demo_execute_plan() -> None:
    """Demostración de ejecución simulada del plan recursivo."""
    scm = build_causal_world()
    scm.add_dependency("PricingAPI", "MarketingService")
    scm.set_node_state("MarketingService", "OK")

    integrator = NeuroSymbolicIntegrator(scm=scm, tool_registry=ToolRegistry(default_tools()))

    print("\n[UC-314] DEMO: Ejecución simulada del plan recursivo\n")
    goal = "Enviar correo de seguimiento a los leads de la campaña"
    result = integrator.execute_plan(goal)
    print(f"Objetivo: {result['goal']}")
    print(f"Estado final: {result['plan']['status']}")
    print(f"Métricas: {result['metrics']}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-314 — Razonamiento causal y planificación recursiva neuro-simbólica.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo-root-cause", action="store_true", help="Demo de trazado de causa raíz.")
    group.add_argument("--demo-plan", action="store_true", help="Demo de planificación recursiva.")
    group.add_argument("--demo-execute", action="store_true", help="Demo de ejecución simulada del plan.")
    group.add_argument("--server", action="store_true", help="Levantar API REST Flask.")
    args = parser.parse_args()

    if args.demo_root_cause:
        demo_root_cause()
        return 0
    if args.demo_plan:
        demo_recursive_planning()
        return 0
    if args.demo_execute:
        demo_execute_plan()
        return 0
    if args.server:
        from api import main as api_main
        return api_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
