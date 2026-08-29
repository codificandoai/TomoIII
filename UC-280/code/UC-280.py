"""UC-280 — Production-grade agentic goal decomposition.

Uses LangGraph-compatible state transitions by default and provides experimental
TDAG and ReAcTree planning strategies without requiring external LLM services.
"""
from __future__ import annotations

import argparse
import json
import sys

from models import PlannerType
from orchestrator import GoalOrchestrator
from store import GoalStore


def run(description: str, planner: str, db_path: str) -> int:
    orchestrator = GoalOrchestrator(GoalStore(db_path))
    goal = orchestrator.create_plan(description, {"source": "cli"}, PlannerType(planner))
    summary = orchestrator.execute(goal.id)
    output = {"plan": orchestrator.plan_view(goal.id), "execution": summary.public_dict(),
              "audit_hash": summary.audit_hash()}
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    return 0


def serve(port: int, db_path: str) -> int:
    import api
    api.orchestrator = GoalOrchestrator(GoalStore(db_path))
    api.app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Agentic hierarchical goal decomposition")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("run")
    demo.add_argument("description", nargs="?", default="Develop and deploy a production analytics API")
    demo.add_argument("--planner", choices=[p.value for p in PlannerType], default="langgraph")
    demo.add_argument("--db", default=":memory:")
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=5280)
    server.add_argument("--db", default="uc280.db")
    args = parser.parse_args(argv)
    return run(args.description, args.planner, args.db) if args.command == "run" else serve(args.port, args.db)


if __name__ == "__main__":
    sys.exit(main())