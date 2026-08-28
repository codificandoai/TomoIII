"""
Codificando.AI
UC-268: Comunicación segura entre agentes con A2A.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any

from config import get_config
from models import FlightClass, FlightSearchRequest, Message, Part, Task


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_serve(args: argparse.Namespace) -> int:
    from a2a_server import app

    port = args.port or int(os.getenv("UC268_PORT", get_config().port))
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    from a2a_client import A2AClient

    client = A2AClient(get_config())
    try:
        card = client.discover(args.agent_url)
        _print_json(card.model_dump())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_send_task(args: argparse.Namespace) -> int:
    from a2a_client import A2AClient

    client = A2AClient(get_config())
    # Construye una tarea A2A con una búsqueda de vuelos como payload JSON
    search = FlightSearchRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=datetime.strptime(args.departure_date, "%Y-%m-%d"),
        passengers=args.passengers,
        cabin_class=FlightClass(args.cabin_class),
        max_price_usd=Decimal(args.max_price),
    )
    task = Task(
        messages=[
            Message(
                role="user",
                parts=[Part(type="json", content=search.model_dump(mode="json"))],
            )
        ]
    )
    try:
        response = client.send_task(
            args.agent_url,
            task,
            token=args.token,
            api_key=args.api_key,
        )
        _print_json(response.model_dump())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-268", description="Secure A2A Multi-Agent Communication")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the A2A Flask server")
    serve_parser.add_argument("--port", type=int)

    discover_parser = subparsers.add_parser("discover", help="Fetch an Agent Card")
    discover_parser.add_argument("--agent-url", required=True)

    send_parser = subparsers.add_parser("send-task", help="Send an A2A task to an agent")
    send_parser.add_argument("--agent-url", required=True)
    send_parser.add_argument("--origin", required=True)
    send_parser.add_argument("--destination", required=True)
    send_parser.add_argument("--departure-date", required=True)
    send_parser.add_argument("--passengers", type=int, default=1)
    send_parser.add_argument("--cabin-class", default="economy")
    send_parser.add_argument("--max-price", required=True)
    send_parser.add_argument("--token")
    send_parser.add_argument("--api-key")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "serve": cmd_serve,
        "discover": cmd_discover,
        "send-task": cmd_send_task,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
