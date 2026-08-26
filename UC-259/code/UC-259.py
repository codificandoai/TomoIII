"""
Codificando.AI
UC-259: Agentic Flight Planner con LangGraph.

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
from models import FlightPlanRequest
from world_simulator import WorldSimulator


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_plan(args: argparse.Namespace) -> int:
    config = get_config()
    world = WorldSimulator(config.world)
    preferences: Dict[str, Any] = {}
    if args.seat:
        preferences["seat"] = args.seat
    if args.direct_flight:
        preferences["direct_flight"] = True
    if args.optimize_for:
        preferences["optimize_for"] = args.optimize_for
    if args.meeting_time:
        preferences["meeting_time"] = args.meeting_time
    if args.hotel_stars:
        preferences["hotel_stars"] = args.hotel_stars

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
    )

    final_state = run_agent(
        req,
        config.agent,
        world,
        recursion_limit=args.recursion_limit,
    )
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") == "done" else 1


def cmd_simulate(args: argparse.Namespace) -> int:
    config = get_config()
    world = WorldSimulator(config.world)
    world.inject_event(args.item_id, args.event_type, delay_minutes=args.delay_minutes, reason=args.reason)
    print(f"Event {args.event_type} injected for {args.item_id}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC259_PORT", get_config().port))
    os.environ["UC259_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-259", description="Agentic Flight Planner")
    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan", help="Run the agentic travel planner")
    plan_parser.add_argument("--origin", required=True, help="Origin city")
    plan_parser.add_argument("--destination", required=True, help="Destination city")
    plan_parser.add_argument("--departure-date", required=True, help="Departure date YYYY-MM-DD")
    plan_parser.add_argument("--return-date", help="Return date YYYY-MM-DD")
    plan_parser.add_argument("--travelers", type=int, default=1)
    plan_parser.add_argument("--budget", type=float, help="Maximum budget")
    plan_parser.add_argument("--currency", default="USD")
    plan_parser.add_argument("--seat", help="Seat preference, e.g. window")
    plan_parser.add_argument("--direct-flight", action="store_true", help="Prefer direct flights")
    plan_parser.add_argument("--optimize-for", choices=["cheapest", "fastest", "direct"], help="Optimization strategy")
    plan_parser.add_argument("--meeting-time", help="Meeting time HH:MM")
    plan_parser.add_argument("--hotel-stars", type=int, help="Minimum hotel stars")
    plan_parser.add_argument(
        "--constraints",
        nargs="+",
        help="Constraints such as max_layover_hours=3",
    )
    plan_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Authorize irreversible bookings (flights, hotels)",
    )
    plan_parser.add_argument(
        "--recursion-limit",
        type=int,
        default=50,
        help="LangGraph recursion limit",
    )

    simulate_parser = subparsers.add_parser("simulate", help="Inject a world event for testing")
    simulate_parser.add_argument("--item-id", required=True)
    simulate_parser.add_argument("--event-type", required=True, choices=["DELAYED", "CANCELLED", "OVERBOOKED"])
    simulate_parser.add_argument("--delay-minutes", type=int, default=180)
    simulate_parser.add_argument("--reason", default="Simulated disruption")

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int, help="Port to listen on")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"plan": cmd_plan, "simulate": cmd_simulate, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
