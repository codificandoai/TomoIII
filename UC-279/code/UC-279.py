"""UC-279 — TrackPrice.ai Pricing Digital Twins.

Commands:
    python UC-279.py run --steps 5
    python UC-279.py serve --port 5279
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from core import TrackPriceDigitalTwin
from models import MarketState, PricingPolicy, ScenarioType


def run_demo(steps: int, scenario: str) -> int:
    state = MarketState(
        sku="TRACKPRICE-DEMO-001", current_price=249.99, unit_cost=150.0,
        competitor_price=245.0, current_demand=5000, inventory=50000,
    )
    twin = TrackPriceDigitalTwin(state, PricingPolicy(), seed=42)
    results = twin.simulate(steps, ScenarioType(scenario), auto_execute=True)
    output = {
        "twin_id": twin.twin_id,
        "sku": state.sku,
        "cycles": [{
            "cycle_id": result.cycle_id,
            "recommendation": asdict(result.recommendation),
            "executed": result.executed,
            "audit_hash": result.audit_hash(),
        } for result in results],
        "final_state": twin.state.public_dict(),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


def serve(port: int) -> int:
    from api import app
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="TrackPrice.ai pricing digital twin")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run deterministic simulation")
    run.add_argument("--steps", type=int, default=5)
    run.add_argument("--scenario", choices=[s.value for s in ScenarioType], default="baseline")
    server = commands.add_parser("serve", help="Serve Flask API and dashboard")
    server.add_argument("--port", type=int, default=5279)
    args = parser.parse_args(argv)
    return run_demo(args.steps, args.scenario) if args.command == "run" else serve(args.port)


if __name__ == "__main__":
    sys.exit(main())