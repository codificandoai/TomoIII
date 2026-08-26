"""
Codificando.AI
UC-260: Agente BDI de viajes con predictor de retrasos y aprendizaje.

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
from external_api import FlightDelayPredictor
from graph import run_agent
from models import FlightPlanRequest
from world_simulator import WorldSimulator


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_plan(args: argparse.Namespace) -> int:
    config = get_config()
    world = WorldSimulator(config.world)
    predictor = FlightDelayPredictor(config.predictor)
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
        predict_delays=not args.no_predict,
        enable_learning=not args.no_learning,
    )

    final_state = run_agent(
        req,
        config.agent,
        world,
        predictor,
        recursion_limit=args.recursion_limit,
    )
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") == "done" else 1


def cmd_predict(args: argparse.Namespace) -> int:
    config = get_config()
    predictor = FlightDelayPredictor(config.predictor)
    items = [
        {
            "item_type": "flight",
            "id": f.get("NROVUELO", f"FL-{i}"),
            "details": {
                "airline": f.get("OPERA", ""),
                "origin": f.get("SIGLAORI", ""),
                "destination": f.get("SIGLAPOS", ""),
                "departure": f"2026-{int(f.get('MES',1)):02d}-{int(f.get('DIA',1)):02d}T08:00:00",
                "arrival": f"2026-{int(f.get('MES',1)):02d}-{int(f.get('DIA',1)):02d}T10:00:00",
                "flight_number": f.get("NROVUELO", ""),
                "cabin_class": f.get("CLASEVUELO", "Y"),
                "aircraft_type": f.get("TIPOPLANO", "B738"),
            },
        }
        for i, f in enumerate(args.flights)
    ]
    result = predictor.predict(items)
    _print_json(result)
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    config = get_config()
    world = WorldSimulator(config.world)
    world.inject_event(args.item_id, args.event_type, delay_minutes=args.delay_minutes, reason=args.reason)
    print(f"Event {args.event_type} injected for {args.item_id}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC260_PORT", get_config().port))
    os.environ["UC260_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def _parse_flight_arg(arg: str) -> Dict[str, Any]:
    """Parsea '--flight OPERA=AA,MES=4,DIA=20,...' en un dict."""
    result: Dict[str, Any] = {}
    for pair in arg.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        if v.isdigit():
            v = int(v)
        result[k.strip()] = v
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-260", description="BDI Flight Agent")
    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan", help="Run the BDI travel agent")
    plan_parser.add_argument("--origin", required=True)
    plan_parser.add_argument("--destination", required=True)
    plan_parser.add_argument("--departure-date", required=True)
    plan_parser.add_argument("--return-date")
    plan_parser.add_argument("--travelers", type=int, default=1)
    plan_parser.add_argument("--budget", type=float)
    plan_parser.add_argument("--currency", default="USD")
    plan_parser.add_argument("--seat")
    plan_parser.add_argument("--direct-flight", action="store_true")
    plan_parser.add_argument("--optimize-for", choices=["cheapest", "fastest", "direct"])
    plan_parser.add_argument("--meeting-time")
    plan_parser.add_argument("--hotel-stars", type=int)
    plan_parser.add_argument("--constraints", nargs="+")
    plan_parser.add_argument("--confirm", action="store_true", help="Authorize irreversible bookings")
    plan_parser.add_argument("--no-predict", action="store_true", help="Disable delay prediction")
    plan_parser.add_argument("--no-learning", action="store_true", help="Disable experience learning")
    plan_parser.add_argument("--recursion-limit", type=int, default=50)

    predict_parser = subparsers.add_parser("predict", help="Call the flight delay predictor")
    predict_parser.add_argument("--flight", action="append", required=True, help="Key=value pairs separated by commas")

    simulate_parser = subparsers.add_parser("simulate", help="Inject a world event")
    simulate_parser.add_argument("--item-id", required=True)
    simulate_parser.add_argument("--event-type", required=True, choices=["DELAYED", "CANCELLED", "OVERBOOKED"])
    simulate_parser.add_argument("--delay-minutes", type=int, default=180)
    simulate_parser.add_argument("--reason", default="Simulated disruption")

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "predict":
        args.flights = [_parse_flight_arg(f) for f in args.flight]

    dispatch = {"plan": cmd_plan, "predict": cmd_predict, "simulate": cmd_simulate, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
