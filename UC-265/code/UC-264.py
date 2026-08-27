"""
Codificando.AI
UC-264: Model-Based Multi-Agent Travel Planner.
El agente construye un world model interno, simula múltiples planes
y selecciona el mejor antes de actuar.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from config import get_config
from graph import run_agent
from models import TravelPlanRequest


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_plan(args: argparse.Namespace) -> int:
    preferences: Dict[str, Any] = {}
    if args.airline:
        preferences["airline"] = args.airline
    if args.hotel_chain:
        preferences["hotel_chain"] = args.hotel_chain
    if args.direct:
        preferences["direct_only"] = True

    request = TravelPlanRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        return_date=args.return_date,
        travelers=args.travelers,
        budget=args.budget,
        currency=args.currency,
        preferences=preferences,
        constraints=args.constraints or [],
        confirm_irreversible=args.confirm,
        predict_delays=args.predict,
        user_id=args.user_id,
    )
    final_state = run_agent(request, get_config(), recursion_limit=50)
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") in ("done", "awaiting_confirmation") else 1


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC264_PORT", get_config().port))
    os.environ["UC264_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-264", description="Model-Based Travel Planner")
    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan", help="Plan a trip using the model-based agent")
    plan_parser.add_argument("--origin", required=True)
    plan_parser.add_argument("--destination", required=True)
    plan_parser.add_argument("--departure-date", required=True)
    plan_parser.add_argument("--return-date")
    plan_parser.add_argument("--travelers", type=int, default=1)
    plan_parser.add_argument("--budget", type=float)
    plan_parser.add_argument("--currency", default="USD")
    plan_parser.add_argument("--user-id", default="anonymous")
    plan_parser.add_argument("--airline")
    plan_parser.add_argument("--hotel-chain")
    plan_parser.add_argument("--direct", action="store_true")
    plan_parser.add_argument("--constraints", nargs="+")
    plan_parser.add_argument("--confirm", action="store_true", help="Authorize irreversible bookings")
    plan_parser.add_argument("--predict", action="store_true", help="Enable delay prediction")

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"plan": cmd_plan, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
