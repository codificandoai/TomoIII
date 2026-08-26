"""
Codificando.AI
UC-262: IA Genérica evolutiva con memoria a largo plazo, razonamiento,
autorreflexión, colaboración y meta-aprendizaje.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from config import get_config
from graph import run_agent
from memory import LongTermMemory
from models import TravelRequest


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_plan(args: argparse.Namespace) -> int:
    config = get_config()
    preferences: Dict[str, Any] = {}
    if args.airline:
        preferences["airline"] = args.airline
    if args.seat:
        preferences["seat"] = args.seat
    if args.hotel_chain:
        preferences["hotel_chain"] = args.hotel_chain
    if args.dietary:
        preferences["dietary"] = args.dietary

    long_term_goals = args.goals or []
    constraints = args.constraints or []

    req = TravelRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        return_date=args.return_date,
        travelers=args.travelers,
        budget=args.budget,
        currency=args.currency,
        preferences=preferences,
        constraints=constraints,
        long_term_goals=long_term_goals,
        confirm_irreversible=args.confirm,
        predict_delays=args.predict,
        enable_learning=not args.no_learning,
        user_id=args.user_id,
        human_feedback=args.human_feedback,
        approved_alternative=args.approved_alternative,
    )

    final_state = run_agent(req, config, recursion_limit=50)
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") == "done" else 1


def cmd_memory(args: argparse.Namespace) -> int:
    config = get_config()
    memory = LongTermMemory(config.memory.path)
    profile = memory.get_profile(args.user_id)
    _print_json(profile.to_dict())
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC262_PORT", get_config().port))
    os.environ["UC262_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-262", description="Generic AI Evolutionary Copilot")
    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan", help="Run the generic AI copilot")
    plan_parser.add_argument("--origin", required=True)
    plan_parser.add_argument("--destination", required=True)
    plan_parser.add_argument("--departure-date", required=True)
    plan_parser.add_argument("--return-date")
    plan_parser.add_argument("--travelers", type=int, default=1)
    plan_parser.add_argument("--budget", type=float)
    plan_parser.add_argument("--currency", default="USD")
    plan_parser.add_argument("--user-id", default="anonymous")
    plan_parser.add_argument("--airline")
    plan_parser.add_argument("--seat")
    plan_parser.add_argument("--hotel-chain")
    plan_parser.add_argument("--dietary")
    plan_parser.add_argument("--goals", nargs="+")
    plan_parser.add_argument("--constraints", nargs="+")
    plan_parser.add_argument("--confirm", action="store_true", help="Authorize irreversible bookings")
    plan_parser.add_argument("--predict", action="store_true", help="Enable delay prediction")
    plan_parser.add_argument("--no-learning", action="store_true", help="Disable meta-learning")
    plan_parser.add_argument("--human-feedback", default="")
    plan_parser.add_argument("--approved-alternative", default="")

    memory_parser = subparsers.add_parser("memory", help="Show user long-term memory")
    memory_parser.add_argument("--user-id", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"plan": cmd_plan, "memory": cmd_memory, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
