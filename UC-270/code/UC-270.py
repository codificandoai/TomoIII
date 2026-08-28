"""
Codificando.AI
UC-270: Resolución de Conflictos entre Agentes (OVADARE + NegMAS + AutoGen).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from config import get_config
from conflict_resolver import ConflictManager
from models import AgentProfile, ResourceClaim


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta un escenario de conflicto de ejemplo."""
    config = get_config()
    manager = ConflictManager(config)

    claims = [
        ResourceClaim(agent_name="planner", resource_id=args.resource, need=args.need_a, priority=args.priority_a, flexibility=0.7, willingness=0.8),
        ResourceClaim(agent_name="optimizer", resource_id=args.resource, need=args.need_b, priority=args.priority_b, flexibility=0.4, willingness=0.6),
    ]
    profiles = {
        "planner": AgentProfile(name="planner", priority=args.priority_a, flexibility=0.7, negotiation_skill=0.8, reputation=0.9),
        "optimizer": AgentProfile(name="optimizer", priority=args.priority_b, flexibility=0.4, negotiation_skill=0.6, reputation=0.7),
    }

    outcomes = manager.resolve_all(claims, profiles)
    for outcome in outcomes:
        _print_json(outcome.model_dump(mode="json"))
    if not outcomes:
        print("No conflicts detected.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from api import app

    port = args.port or int(os.getenv("UC270_PORT", get_config().port))
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-270", description="Conflict Resolution for Multi-Agent Systems")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a conflict resolution scenario")
    run_parser.add_argument("--resource", default="GPU_1")
    run_parser.add_argument("--need-a", type=float, default=0.9)
    run_parser.add_argument("--need-b", type=float, default=0.8)
    run_parser.add_argument("--priority-a", type=int, default=8)
    run_parser.add_argument("--priority-b", type=int, default=8)

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API server")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"run": cmd_run, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
