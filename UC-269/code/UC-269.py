"""
Codificando.AI
UC-269: Protocolo Contract Net con métricas para Grafana.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from config import get_config
from contract_net import ContractNetManager, WorkerAgent
from models import TaskAnnouncement, WorkerProfile


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _default_workers() -> list[WorkerAgent]:
    profiles = [
        WorkerProfile(name="researcher", skills=["feature_extraction"], skill_score=0.95, reliability=0.92, cost_factor=1.4, latency_factor=0.8),
        WorkerProfile(name="coder", skills=["classification"], skill_score=0.85, reliability=0.88, cost_factor=1.1, latency_factor=0.6),
        WorkerProfile(name="reviewer", skills=["validation"], skill_score=0.90, reliability=0.95, cost_factor=1.2, latency_factor=0.7),
    ]
    return [WorkerAgent(profile) for profile in profiles]


async def cmd_run(args: argparse.Namespace) -> int:
    workers = _default_workers()
    manager = ContractNetManager(workers, config=get_config())
    task = await manager.announce(args.title, args.description)
    outcome = await manager.run(task)
    _print_json(outcome.model_dump(mode="json"))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from api import app

    port = args.port or int(os.getenv("UC269_PORT", get_config().port))
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-269", description="Contract Net protocol with Grafana audit metrics")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a Contract Net round locally")
    run_parser.add_argument("--title", default="Tarea de ejemplo")
    run_parser.add_argument("--description", default="Extraer características con Fourier y clasificar patrones")

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "run":
        return asyncio.run(cmd_run(args))
    if args.command == "serve":
        return cmd_serve(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
