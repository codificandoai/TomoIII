"""Codificando.AI — UC-315: Núcleo cognitivo-orquestador común + SkillRegistry por dominio.

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
import json

from domain_policy import PolicyRegistry
from domain_skills import build_default_registry
from general_orchestrator import GeneralOrchestrator
from safety_supervisor_315 import SafetySupervisor315


def _make_orchestrator() -> GeneralOrchestrator:
    return GeneralOrchestrator(
        skill_registry=build_default_registry(),
        safety=SafetySupervisor315(PolicyRegistry()),
    )


def demo_skills() -> None:
    """Muestra el catálogo de skills con contratos explícitos."""
    orch = _make_orchestrator()
    print("\n[UC-315] Skills registrados por dominio\n")
    for domain in orch.skills.domains():
        print(f"Dominio: {domain}")
        for skill in orch.skills.list_skills(domain):
            print(f"  - {skill['name']} (risk={skill['risk_level']}, action={skill['action_class']})")
            print(f"    purpose: {skill['purpose']}")
            print(f"    preconditions: {skill['preconditions']}")
            print(f"    permissions: {skill['permissions']} | roles: {skill['required_roles']}")
    print()


def demo_flight_to_rail_generalization() -> None:
    """Demuestra generalización semántica: la plantilla de vuelo adapta a tren."""
    orch = _make_orchestrator()
    print("\n[UC-315] DEMO: Generalización semántica — plantilla de reserva de transporte\n")

    # 1. Reserva de vuelo
    goal_flight = "Reservar un vuelo de Madrid a Barcelona para mañana"
    plan_flight = orch.build_plan(goal_flight, "reservations")
    print(f"Objetivo: {goal_flight}")
    print(f"Plantilla usada: {plan_flight.template}")
    for step in plan_flight.steps:
        print(f"  -> {step.skill_name}")

    # 2. Reserva de tren: misma plantilla, skills distintas
    goal_rail = "Reservar un tren de Madrid a Barcelona para mañana"
    plan_rail = orch.build_plan(goal_rail, "reservations")
    print(f"\nObjetivo: {goal_rail}")
    print(f"Plantilla usada: {plan_rail.template}")
    for step in plan_rail.steps:
        print(f"  -> {step.skill_name}")

    print("\nNota: Se reutiliza la estructura abstracta del plan, pero no credenciales, datos ni código.")


def demo_trading_isolation() -> None:
    """Demuestra que el dominio trading usa skills y políticas separadas."""
    orch = _make_orchestrator()
    print("\n[UC-315] DEMO: Aislamiento operacional del dominio trading\n")
    goal = "Enviar orden de compra de AAPL con límite 150.30"
    plan = orch.build_plan(goal, "trading")
    print(f"Objetivo: {goal}")
    print(f"Plantilla usada: {plan.template}")
    for step in plan.steps:
        print(f"  -> {step.skill_name}")

    # Estado con aprobación de riesgo y permisos explícitos de ejecución
    domain_state = {"risk_approved": True, "circuit_breaker_open": True}
    executed = orch.validate_and_execute(
        plan,
        user_roles=["trader", "market.order.send"],
        domain_state=domain_state,
        auto_approve=True,
    )
    print(f"\nEstado del plan: {executed.status}")
    for step in executed.steps:
        print(f"  {step.skill_name}: {step.status}")
        if step.safety_decision:
            print(f"    safety: allowed={step.safety_decision['allowed']} issues={step.safety_decision['issues']}")


def demo_safety_blocks_unauthorized() -> None:
    """Muestra que un usuario sin permisos no puede ejecutar transacciones."""
    orch = _make_orchestrator()
    print("\n[UC-315] DEMO: Safety Supervisor bloquea acción no autorizada\n")
    goal = "Comprar un billete de avión de Madrid a Barcelona"
    plan = orch.build_plan(goal, "reservations")
    executed = orch.validate_and_execute(
        plan,
        user_roles=["anonymous"],
        domain_state={"availability_confirmed": True, "user_consent": True},
        auto_approve=False,
    )
    print(f"Objetivo: {goal}")
    print(f"Estado del plan: {executed.status}")
    for step in executed.steps:
        print(f"  {step.skill_name}: {step.status}")
        if step.safety_decision:
            print(f"    issues: {step.safety_decision['issues']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-315 — Núcleo orquestador común + SkillRegistry por dominio.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo-skills", action="store_true", help="Listar skills por dominio.")
    group.add_argument("--demo-flight-to-rail", action="store_true", help="Generalización semántica vuelo -> tren.")
    group.add_argument("--demo-trading", action="store_true", help="Aislamiento operacional de trading.")
    group.add_argument("--demo-safety", action="store_true", help="Bloqueo de acciones no autorizadas.")
    group.add_argument("--server", action="store_true", help="Levantar API REST Flask.")
    args = parser.parse_args()

    if args.demo_skills:
        demo_skills()
        return 0
    if args.demo_flight_to_rail:
        demo_flight_to_rail_generalization()
        return 0
    if args.demo_trading:
        demo_trading_isolation()
        return 0
    if args.demo_safety:
        demo_safety_blocks_unauthorized()
        return 0
    if args.server:
        from api import main as api_main
        return api_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
