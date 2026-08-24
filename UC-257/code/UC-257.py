"""Codificando.AI - UC-257: Agente autónomo vs. asistente dependiente para viajes.

CLI para ejecutar:
  - asistente dependiente (Semantic Kernel / fallback determinista)
  - agente autónomo (AutoGen / orquestador interno)
  - servidor API Flask
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List

from agent_orchestrator import TravelAgentOrchestrator
from autogen_adapter import AutoGenAdapter
from config import CONFIG, AppConfig
from models import TripRequest
from semantic_kernel_adapter import SemanticKernelAdapter
from travel_services import BookingManager, TravelInventory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uc257-cli")


def _orchestrator(config: AppConfig = CONFIG):
    inventory = TravelInventory()
    bookings = BookingManager(inventory)
    return TravelAgentOrchestrator(inventory, bookings, config.agent)


def cmd_assistant(args: argparse.Namespace) -> int:
    config = AppConfig()
    orchestrator = _orchestrator(config)
    adapter = SemanticKernelAdapter(config, orchestrator)
    trip = None
    if args.trip:
        trip = _trip_from_json(args.trip)
    result = adapter.chat(args.user_id, args.message, state=None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    config = AppConfig()
    orchestrator = _orchestrator(config)
    adapter = AutoGenAdapter(config, orchestrator)
    request = TripRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        return_date=args.return_date,
        travelers=args.travelers,
        budget=args.budget,
        meeting_ids=args.meeting_ids or [],
    )
    result = adapter.run(request)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    config = AppConfig()
    orchestrator = _orchestrator(config)
    request = TripRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        return_date=args.return_date,
        travelers=args.travelers,
        budget=args.budget,
        meeting_ids=args.meeting_ids or [],
    )
    # Ejecutar plan autónomo primero
    result = orchestrator.plan_and_execute(request)
    request_id = request.request_id

    # Cancelar el vuelo seleccionado para forzar recuperación
    state = orchestrator._states[request_id]
    if state.selected_flight:
        flight = state.selected_flight
        flight.status = "cancelled"
        plan = orchestrator.planner.create_plan(request)
        plan.actions = []
        recovery = orchestrator.planner.handle_disruption(plan, flight)
        for action in recovery:
            orchestrator._execute_action(action, state)
        state.log.extend(recovery)
        summary = orchestrator._build_summary(state)
        result = {
            "request_id": request_id,
            "event": "flight_cancelled",
            "state": state.to_dict(),
            "summary": summary,
            "notifications": state.notifications,
        }
    else:
        result = {"error": "No había vuelo seleccionado para cancelar"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_api(args: argparse.Namespace) -> int:
    os.environ["UC257_PORT"] = str(args.port)
    import api as api_module  # noqa: F401
    from api import app

    logger.info("Servidor UC-257 iniciado en http://0.0.0.0:%d", args.port)
    app.run(host="0.0.0.0", port=args.port, debug=False)
    return 0


def _trip_from_json(s: str) -> TripRequest:
    data = json.loads(s)
    return TripRequest(
        origin=data["origin"],
        destination=data["destination"],
        departure_date=data["departure_date"],
        return_date=data.get("return_date"),
        travelers=data.get("travelers", 1),
        budget=data.get("budget"),
        meeting_ids=data.get("meeting_ids", []),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="UC-257",
        description="Sistema de agentes autónomos de viajes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    assistant = sub.add_parser("assistant", help="Asistente dependiente (un turno).")
    assistant.add_argument("--user-id", default="user-1")
    assistant.add_argument("--message", required=True)
    assistant.add_argument("--trip", help="JSON del TripRequest")

    agent = sub.add_parser("agent", help="Agente autónomo: planificar y ejecutar viaje.")
    agent.add_argument("--origin", required=True)
    agent.add_argument("--destination", required=True)
    agent.add_argument("--departure-date", required=True)
    agent.add_argument("--return-date")
    agent.add_argument("--travelers", type=int, default=1)
    agent.add_argument("--budget", type=float, default=None)
    agent.add_argument("--meeting-ids", nargs="*")

    simulate = sub.add_parser("simulate", help="Ejecuta agente y simula cancelación de vuelo.")
    simulate.add_argument("--origin", default="Madrid")
    simulate.add_argument("--destination", default="París")
    simulate.add_argument("--departure-date", default="2026-07-15")
    simulate.add_argument("--return-date", default="2026-07-18")
    simulate.add_argument("--travelers", type=int, default=1)
    simulate.add_argument("--budget", type=float, default=500.0)
    simulate.add_argument("--meeting-ids", nargs="*", default=["meet-15"])

    api_cmd = sub.add_parser("serve", help="Levanta la API Flask.")
    api_cmd.add_argument("--port", type=int, default=int(os.getenv("UC257_PORT", "5257")))

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "assistant": cmd_assistant,
        "agent": cmd_agent,
        "simulate": cmd_simulate,
        "serve": cmd_api,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
