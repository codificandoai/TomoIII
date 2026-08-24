"""Codificando.AI - UC-258: Meta-framework de agentes adaptativos.

CLI para ejecutar los tres entornos y la API Flask.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List

from agent.adaptive_agent import AdaptiveAgent
from config import CONFIG
from environments.chess_env import ChessboardEnvironment
from environments.stock_env import StockMarketEnvironment
from environments.travel_env import TravelEnvironment
from models import TravelRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uc258-cli")


def cmd_chess(args: argparse.Namespace) -> int:
    agent = AdaptiveAgent(config=CONFIG.agent)
    env = ChessboardEnvironment()
    trace = agent.run(env, objective="find_checkmate", max_iterations=args.iterations)
    print(json.dumps(trace.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_travel(args: argparse.Namespace) -> int:
    req = TravelRequest(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.departure_date,
        return_date=args.return_date,
        travelers=args.travelers,
        budget=args.budget,
        currency=args.currency,
        preferences=json.loads(args.preferences) if args.preferences else {},
        constraints=args.constraints or [],
    )
    agent = AdaptiveAgent(config=CONFIG.agent)
    env = TravelEnvironment(request=req)
    trace = agent.run(env, objective=req, max_iterations=args.iterations)
    output = {
        "trace": trace.to_dict(),
        "itinerary": env.itinerary.to_dict(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_stock(args: argparse.Namespace) -> int:
    agent = AdaptiveAgent(config=CONFIG.agent)
    env = StockMarketEnvironment(seed=args.seed)
    for i in range(args.steps):
        trace = agent.run(env, objective="maximize_return", max_iterations=1)
        logger.info("Step %d reward=%.4f", i + 1, trace.reward)
    final = env.get_observation().to_dict()
    pnl = (env.portfolio["cash"] + env.portfolio["shares"] * env.price) - 10000.0
    print(json.dumps({"final_observation": final, "pnl": round(pnl, 2)}, ensure_ascii=False, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    os.environ["UC258_PORT"] = str(args.port)
    import api as api_module  # noqa: F401
    from api import app

    logger.info("Servidor UC-258 iniciado en http://0.0.0.0:%d", args.port)
    app.run(host="0.0.0.0", port=args.port, debug=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="UC-258",
        description="Meta-framework de agentes adaptativos para ajedrez, viajes y bolsa.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    chess = sub.add_parser("chess", help="Ejecuta agente en tablero de ajedrez.")
    chess.add_argument("--iterations", type=int, default=5)

    travel = sub.add_parser("travel", help="Planifica un viaje en Komerzio.com.")
    travel.add_argument("--origin", default="Madrid")
    travel.add_argument("--destination", default="París")
    travel.add_argument("--departure-date", default="2026-07-15")
    travel.add_argument("--return-date", default="2026-07-18")
    travel.add_argument("--travelers", type=int, default=1)
    travel.add_argument("--budget", type=float, default=1200.0)
    travel.add_argument("--currency", default="USD")
    travel.add_argument("--preferences", default="{}")
    travel.add_argument("--constraints", nargs="*")
    travel.add_argument("--iterations", type=int, default=20)

    stock = sub.add_parser("stock", help="Ejecuta agente en mercado bursátil.")
    stock.add_argument("--steps", type=int, default=5)
    stock.add_argument("--seed", type=int, default=42)

    serve = sub.add_parser("serve", help="Levanta la API Flask.")
    serve.add_argument("--port", type=int, default=int(os.getenv("UC258_PORT", "5258")))

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "chess": cmd_chess,
        "travel": cmd_travel,
        "stock": cmd_stock,
        "serve": cmd_serve,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
