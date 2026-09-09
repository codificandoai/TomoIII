#!/usr/bin/env python3
"""
UC-703 — CLI de demostración del AGI Agent Runtime & Orchestrator.

Ejemplos:
    python UC-703.py demo-all
    python UC-703.py run-objective "Investigar tendencias de mercado en Latam"
    python UC-703.py run-objective "Remediar disco lleno en servidor prod"
    python UC-703.py run-objective "Enviar resumen a Slack"
    python UC-703.py run-objective "Migrar base de datos AWS (tarea de 2 horas)"
    python UC-703.py api [--port 5703]
    python UC-703.py tests
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent_runtime_orchestrator import AgentRuntimeOrchestrator


def print_task(task: Any) -> None:
    print(json.dumps(task.to_dict(), indent=2, default=str))


def demo_all() -> None:
    orchestrator = AgentRuntimeOrchestrator()
    scenarios = [
        ("Investigar tendencias de mercado en Latam", "local analysis + memory"),
        ("Remediar disco lleno en servidor prod", "StackStorm infra playbook"),
        ("Enviar resumen a Slack", "n8n SaaS connector"),
        ("Migrar base de datos AWS (tarea de 2 horas)", "Temporal long-running workflow"),
    ]
    for desc, kind in scenarios:
        print(f"\n=== Demo: {kind} ===")
        task = orchestrator.submit_objective(
            description=desc,
            agent_id="demo-agent",
            tenant_id="demo",
            requested_by="demo-user",
        )
        orchestrator.plan_task(task.task_id)
        orchestrator.approve_all_steps(task.task_id)
        orchestrator.execute_task(task.task_id)
        print_task(task)
    print("\n=== Runtime status ===")
    print(json.dumps(orchestrator.runtime_status(), indent=2, default=str))


def run_objective(description: str) -> None:
    orchestrator = AgentRuntimeOrchestrator()
    task = orchestrator.submit_objective(
        description=description,
        agent_id="cli-agent",
        tenant_id="cli",
        requested_by="cli-user",
    )
    orchestrator.plan_task(task.task_id)
    orchestrator.approve_all_steps(task.task_id)
    orchestrator.execute_task(task.task_id)
    print_task(task)


def run_api(port: int = 5703) -> None:
    from api_703 import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=False)


def run_tests() -> int:
    import subprocess
    return subprocess.call(
        [sys.executable, "-m", "pytest", "tests", "-q"],
        cwd=str(Path(__file__).parent),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-703 AGI Agent Runtime")
    parser.add_argument(
        "command",
        choices=["demo-all", "run-objective", "api", "tests"],
    )
    parser.add_argument("--description", type=str, default="", help="Objetivo a ejecutar")
    parser.add_argument("--port", type=int, default=5703, help="Puerto API")
    args = parser.parse_args()

    if args.command == "demo-all":
        demo_all()
    elif args.command == "run-objective":
        desc = args.description or input("Objetivo: ")
        run_objective(desc)
    elif args.command == "api":
        run_api(args.port)
    elif args.command == "tests":
        return run_tests()
    return 0


if __name__ == "__main__":
    sys.exit(main())
