"""
Codificando.AI
UC-272: Negociación y Compartición de Conocimiento entre Agentes.
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
import os
import sys
from typing import Any

from config import get_config
from models import AgentUtilityProfile, EquilibriumCriterion
from orchestrator import NegotiationOrchestrator


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta el escenario de vuelo MAD→CUN con Nash Bargaining."""
    config = get_config()
    orch = NegotiationOrchestrator(config)

    profiles = [
        AgentUtilityProfile(
            agent_id="user_proxy",
            option_utilities={"AA1234": 8.5, "IB5678": 5.0, "UX9012": 7.5, "AF3456": 9.0},
            disagreement_point=3.0,
        ),
        AgentUtilityProfile(
            agent_id="budget_agent",
            option_utilities={"AA1234": 4.0, "IB5678": 9.0, "UX9012": 7.0, "AF3456": 2.0},
            disagreement_point=2.0,
        ),
        AgentUtilityProfile(
            agent_id="sustain_agent",
            option_utilities={"AA1234": 6.0, "IB5678": 4.0, "UX9012": 9.0, "AF3456": 5.0},
            disagreement_point=2.0,
        ),
    ]

    criterion = EquilibriumCriterion(args.criterion)
    outcome = orch.resolve_with_nash("flight_MAD_CUN", profiles, criterion)
    _print_json(outcome.model_dump(mode="json"))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from api import app
    port = args.port or get_config().port
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-272",
        description="Multi-Agent Negotiation & Knowledge Sharing"
    )
    subparsers = parser.add_subparsers(dest="command")

    run_p = subparsers.add_parser("run", help="Run Nash Bargaining flight example")
    run_p.add_argument("--criterion", default="nash",
                       choices=["nash", "kalai_smorodinsky", "weighted_utilitarian"])

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
