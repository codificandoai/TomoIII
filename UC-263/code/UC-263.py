"""
Codificando.AI
UC-263: Agente de recomendaciones turísticas con Q-Learning vectorial.
El agente aprende por sí mismo qué actividades recomendar a cada tipo de turista
usando embeddings, similitud del coseno y la ecuación de Bellman.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from config import get_config
from graph import recommend, train
from models import TravelerContext


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _build_context(args: argparse.Namespace) -> TravelerContext:
    return TravelerContext(
        user_id=args.user_id or "anonymous",
        age_group=args.age_group,
        group_type=args.group_type,
        season=args.season,
        budget_level=args.budget_level,
        interests=args.interests or [],
        origin=args.origin or "",
        destination=args.destination or "",
        mood=args.mood or "",
    )


def cmd_recommend(args: argparse.Namespace) -> int:
    context = _build_context(args)
    result = recommend(context, get_config())
    _print_json(result)
    return 0


def _default_train_contexts() -> List[Dict[str, Any]]:
    return [
        {
            "user_id": "demo",
            "age_group": "adult",
            "group_type": "solo",
            "season": "winter",
            "budget_level": "medium",
            "interests": ["culture"],
            "mood": "curious",
        },
        {
            "user_id": "demo",
            "age_group": "adult",
            "group_type": "family",
            "season": "summer",
            "budget_level": "medium",
            "interests": ["fun"],
            "mood": "relaxed",
        },
        {
            "user_id": "demo",
            "age_group": "adult",
            "group_type": "couple",
            "season": "autumn",
            "budget_level": "high",
            "interests": ["food"],
            "mood": "romantic",
        },
        {
            "user_id": "demo",
            "age_group": "adult",
            "group_type": "friends",
            "season": "summer",
            "budget_level": "low",
            "interests": ["party"],
            "mood": "party",
        },
    ]


def cmd_train(args: argparse.Namespace) -> int:
    contexts = args.contexts
    if not contexts:
        contexts = _default_train_contexts()
    result = train(contexts, episodes=args.episodes, config=get_config())
    _print_json(result)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC263_PORT", get_config().port))
    os.environ["UC263_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-263", description="RL Vector Travel Recommendations")
    subparsers = parser.add_subparsers(dest="command")

    rec_parser = subparsers.add_parser("recommend", help="Recommend activity for a traveler context")
    rec_parser.add_argument("--user-id", default="anonymous")
    rec_parser.add_argument("--age-group", default="adult")
    rec_parser.add_argument("--group-type", default="solo")
    rec_parser.add_argument("--season", default="summer")
    rec_parser.add_argument("--budget-level", default="medium")
    rec_parser.add_argument("--interests", nargs="+")
    rec_parser.add_argument("--origin")
    rec_parser.add_argument("--destination")
    rec_parser.add_argument("--mood")

    train_parser = subparsers.add_parser("train", help="Train RL agent with sample contexts")
    train_parser.add_argument("--contexts", type=argparse.FileType("r"))
    train_parser.add_argument("--episodes", type=int, default=get_config().rl.episodes)

    serve_parser = subparsers.add_parser("serve", help="Start the Flask API")
    serve_parser.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "train" and args.contexts:
        args.contexts = json.load(args.contexts)

    dispatch = {"recommend": cmd_recommend, "train": cmd_train, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
