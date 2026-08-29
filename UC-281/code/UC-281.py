"""UC-281 — Synchronized multi-framework TrackPrice agent system."""
from __future__ import annotations

import argparse
import json
import sys

from models import ExecutionMode, MarketState
from orchestrator import TrackPriceFederatedOrchestrator


def demo(mode: str, execute: bool) -> int:
    state = MarketState("TRACKPRICE-281", 249.99, 150, 245, 5000, 20000,
                        headlines=["Cloud demand expansion", "Chip shortage pressures costs"])
    pipeline = TrackPriceFederatedOrchestrator(state, ExecutionMode(mode))
    run = pipeline.run(execute=execute, idempotency_key="cli-demo")
    result = run.public_dict(); result["audit_hash"] = run.audit_hash()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def serve(port: int) -> int:
    from api import app
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Federated agent framework orchestration for TrackPrice")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--mode", choices=[m.value for m in ExecutionMode], default="auto")
    run.add_argument("--execute", action="store_true")
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=5281)
    args = parser.parse_args(argv)
    return demo(args.mode, args.execute) if args.command == "run" else serve(args.port)


if __name__ == "__main__": sys.exit(main())