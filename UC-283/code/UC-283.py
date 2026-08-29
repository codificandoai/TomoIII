"""UC-283 — Governed self-correcting pricing loop."""
from __future__ import annotations

import argparse
import json
import sys

from memory import LessonMemory
from models import MarketContext
from self_correction import GovernedPricingLoop


def run(apply: bool, approved: bool, db: str) -> int:
    context = MarketContext("TRACKPRICE-283", 249.99, 150, 245, 5.5)
    result = GovernedPricingLoop(LessonMemory(db)).execute(context, apply, approved)
    output = result.public_dict(); output["audit_hash"] = result.audit_hash()
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    return 0


def serve(port: int) -> int:
    from api import app
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Governed pricing self-correction")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("run"); demo.add_argument("--apply", action="store_true")
    demo.add_argument("--approved", action="store_true"); demo.add_argument("--db", default=":memory:")
    server = commands.add_parser("serve"); server.add_argument("--port", type=int, default=5283)
    args = parser.parse_args(argv)
    return run(args.apply, args.approved, args.db) if args.command == "run" else serve(args.port)


if __name__ == "__main__": sys.exit(main())