"""
Codificando.AI
UC-271: Multi-Agent AI on Kubernetes con Seguridad y HPA.
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
import asyncio
import json
import os
import sys
from typing import Any

from config import get_config
from models import AgentProfile, AgentRole, TaskRequest
from supervisor import SupervisorAgent, WorkerAgent
from manifest_generator import ManifestGenerator


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _default_workers() -> list[WorkerAgent]:
    profiles = [
        AgentProfile(name="researcher", role=AgentRole.researcher, skill=0.95, cost=1.2, latency_ms=250, replicas=2, service_account="researcher-sa"),
        AgentProfile(name="coder", role=AgentRole.coder, skill=0.90, cost=1.0, latency_ms=200, replicas=2, service_account="coder-sa"),
        AgentProfile(name="reviewer", role=AgentRole.reviewer, skill=0.92, cost=1.1, latency_ms=180, replicas=1, service_account="reviewer-sa"),
    ]
    return [WorkerAgent(p) for p in profiles]


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta una tarea con el pipeline completo."""
    config = get_config()
    workers = _default_workers()
    supervisor = SupervisorAgent(workers, config)

    request = TaskRequest(task=args.task, resource=args.resource, priority=args.priority)
    result = asyncio.run(supervisor.run_task(request))
    _print_json(result.model_dump(mode="json"))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Inicia el servidor API Flask."""
    from api import app
    port = args.port or get_config().port
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def cmd_manifests(args: argparse.Namespace) -> int:
    """Genera manifiestos K8s."""
    config = get_config()
    profiles = [
        AgentProfile(name="researcher", role=AgentRole.researcher, skill=0.95, cost=1.2, latency_ms=250, replicas=2, service_account="researcher-sa"),
        AgentProfile(name="coder", role=AgentRole.coder, skill=0.90, cost=1.0, latency_ms=200, replicas=2, service_account="coder-sa"),
        AgentProfile(name="reviewer", role=AgentRole.reviewer, skill=0.92, cost=1.1, latency_ms=180, replicas=1, service_account="reviewer-sa"),
    ]
    gen = ManifestGenerator(config)
    manifests = gen.generate_all(profiles)
    for m in manifests:
        _print_json(m.model_dump(mode="json"))
        print("---")
    print(f"\nTotal manifests generated: {len(manifests)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-271",
        description="Multi-Agent AI on Kubernetes with Security & HPA"
    )
    subparsers = parser.add_subparsers(dest="command")

    run_p = subparsers.add_parser("run", help="Run a task through the multi-agent pipeline")
    run_p.add_argument("--task", default="Analyze incident and propose fix")
    run_p.add_argument("--resource", default=None)
    run_p.add_argument("--priority", type=int, default=5)

    serve_p = subparsers.add_parser("serve", help="Start the Flask API server")
    serve_p.add_argument("--port", type=int, default=None)

    subparsers.add_parser("manifests", help="Generate K8s manifests for all agents")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"run": cmd_run, "serve": cmd_serve, "manifests": cmd_manifests}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
