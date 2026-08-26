"""
Codificando.AI
UC-261: Agente BDI adaptativo con memoria de patrones y control gate.

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
from typing import Any, Dict

from config import get_config
from graph import run_agent
from memory import PatternMemoryDB
from models import FlightPlanRequest


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_plan(args: argparse.Namespace) -> int:
    config = get_config()
    preferences: Dict[str, Any] = {}
    if args.seat:
        preferences["seat"] = args.seat
    if args.direct_flight:
        preferences["direct_flight"] = True
    if args.optimize_for:
        preferences["optimize_for"] = args.optimize_for
    if args.meeting_time:
        preferences["meeting_time"] = args.meeting_time
    if args.hotel_chain:
        preferences["hotel_chain"] = args.hotel_chain
    if args.dietary:
        preferences["dietary"] = args.dietary

    req = FlightPlanRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        return_date=args.return_date,
        travelers=args.travelers,
        budget=args.budget,
        currency=args.currency or config.world.default_currency,
        preferences=preferences,
        constraints=args.constraints or [],
        confirm_irreversible=args.confirm,
        predict_delays=not args.no_predict,
        enable_learning=not args.no_learning,
        user_id=args.user_id,
        auto_approve_all=args.auto_approve_all,
    )

    final_state = run_agent(req, config, recursion_limit=args.recursion_limit)
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") == "done" else 1


def cmd_profile(args: argparse.Namespace) -> int:
    config = get_config()
    memory = PatternMemoryDB(config.memory.path)
    profile = memory.get_profile(args.user_id)
    _print_json(profile.to_dict())
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC261_PORT", get_config().port))
    os.environ["UC261_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-261", description="Adaptive BDI Flight Agent")
    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan", help="Run the adaptive BDI travel agent")
    plan_parser.add_argument("--origin", required=True)
    plan_parser.add_argument("--destination", required=True)
    plan_parser.add_argument("--departure-date", required=True)
    plan_parser.add_argument("--return-date")
    plan_parser.add_argument("--travelers", type=int, default=1)
    plan_parser.add_argument("--budget", type=float)
    plan_parser.add_argument("--currency", default="USD")
    plan_parser.add_argument("--user-id", default="anonymous")
    plan_parser.add_argument("--seat")
    plan_parser.add_argument("--direct-flight", action="store_true")
    plan_parser.add_argument("--optimize-for", choices=["cheapest", "fastest", "direct"])
    plan_parser.add_argument("--meeting-time")
    plan_parser.add_argument("--hotel-chain")
    plan_parser.add_argument("--dietary")
    plan_parser.add_argument("--constraints", nargs="+")
    plan_parser.add_argument("--confirm", action="store_true", help="Authorize irreversible bookings")
    plan_parser.add_argument("--no-predict", action="store_true", help="Disable delay prediction")
    plan_parser.add_argument("--no-learning", action="store_true", help="Disable experience learning")
    plan_parser.add_argument("--auto-approve-all", action="store_true", help="Auto-approve all recommendations (demo)")
    plan_parser.add_argument("--recursion-limit", type=int, default=50)

    profile_parser = subparsers.add_parser("profile", help="Show user profile and learned patterns")
    profile_parser.add_argument("--user-id", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"plan": cmd_plan, "profile": cmd_profile, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
