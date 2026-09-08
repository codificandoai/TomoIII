#!/usr/bin/env python3
"""UC-309 CLI: demo, API and validation runner."""
from __future__ import annotations

import argparse
import compileall
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

from observability_orchestrator import ObservabilityOrchestrator
from models_309 import CanonicalEvent, EventType, Outcome, ModelRequestMeta, UC300Auth, UC290Decision, UC324Containment
from agent_observer import observe_step, observe_function
from api_309 import create_app


def demo():
    """Run a small end-to-end demonstration."""
    from privacy_guard import PrivacyGuard
    orch = ObservabilityOrchestrator(privacy=PrivacyGuard(sample_rate=1.0, forced_capture=True))
    trace_id = "demo-trace-1"

    # Start trace
    orch.emit({
        "trace_id": trace_id,
        "span_id": trace_id,
        "agent_id": "uc315",
        "agent_version": "1.0",
        "step": 0,
        "event_type": "trace_start",
        "timestamp_ns": int(time.time() * 1e9),
    })

    # Model request
    orch.emit({
        "trace_id": trace_id,
        "span_id": "span-1",
        "parent_span_id": trace_id,
        "agent_id": "uc315",
        "step": 1,
        "event_type": "model_request",
        "model_request_meta": {
            "model": "claude-3",
            "model_provider": "anthropic",
            "tools_declared": ["search", "update_price"],
        },
    })

    # Thought / action proposed
    orch.emit({
        "trace_id": trace_id,
        "span_id": "span-1",
        "parent_span_id": trace_id,
        "agent_id": "uc315",
        "step": 2,
        "event_type": "thought_summary",
        "structured_reasoning_summary": "Se propone ajustar el precio según evidencia de mercado.",
    })

    # UC-300 authorization
    orch.emit({
        "trace_id": trace_id,
        "span_id": "span-1",
        "parent_span_id": trace_id,
        "step": 3,
        "event_type": "uc300_authorization",
        "uc300": {
            "tool_name": "update_price",
            "policy_verdict": "allowed",
            "authorized": True,
            "toctou_check": True,
            "approved_action_hash": "abc123",
        },
    })

    # Tool call + observation
    with observe_step(orch.emit, trace_id, parent_span_id=trace_id, step=4, agent_id="uc315") as step:
        step.propose_action({"tool": "update_price", "sku": "SKU-001"}, summary="Autorizado")
        step.observe({"status": "ok", "new_price": 120.5}, tokens=42)

    # UC-290 decision
    orch.emit({
        "trace_id": trace_id,
        "span_id": "span-2",
        "parent_span_id": trace_id,
        "agent_id": "uc315",
        "step": 5,
        "event_type": "uc290_decision",
        "uc290": {
            "decision_id": "dec-1",
            "risk_score": 0.1,
            "override": False,
            "escalation": False,
        },
    })

    # Final outcome
    orch.emit({
        "trace_id": trace_id,
        "span_id": trace_id,
        "parent_span_id": None,
        "agent_id": "uc315",
        "step": 6,
        "event_type": "final_outcome",
        "final_outcome": "success",
        "latency_ms": 250.0,
        "input_tokens": 320,
        "output_tokens": 91,
        "estimated_cost_usd": 0.0005,
    })

    print(f"Demo trace stored: {trace_id}")
    print(f"Status: {orch.status()}")
    print(f"Validation: {orch.validate_trace(trace_id, role='auditor')}")
    print(f"Prometheus sample:\n{orch.export_prometheus_text()[:800]}")
    return 0


def run_api(args):
    app = create_app()
    app.run(host=args.host, port=args.port, debug=False)
    return 0


def _validate_json_yaml(code_dir: str) -> List[str]:
    errors: List[str] = []
    for root, _dirs, files in os.walk(code_dir):
        for f in files:
            p = os.path.join(root, f)
            if f.endswith(".json"):
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        json.load(fh)
                except Exception as e:
                    errors.append(f"JSON parse error {p}: {e}")
            if f.endswith(".yml") or f.endswith(".yaml"):
                try:
                    import yaml
                    with open(p, "r", encoding="utf-8") as fh:
                        yaml.safe_load(fh)
                except ImportError:
                    pass
                except Exception as e:
                    errors.append(f"YAML parse error {p}: {e}")
    return errors


def validate_all():
    """Compile all Python, parse JSON/YAML and run a smoke test."""
    code_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Compiling Python in {code_dir} ...")
    ok = compileall.compile_dir(code_dir, quiet=True, force=True)
    if not ok:
        print("compileall failed")
        return 1

    print("Parsing JSON/YAML artifacts ...")
    errors = _validate_json_yaml(code_dir)
    if errors:
        for e in errors:
            print(e)
        return 1

    print("Running smoke test (demo) ...")
    try:
        demo()
    except Exception as e:
        print(f"Demo failed: {e}")
        return 1

    print("Validation OK.")
    return 0


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="UC-309 observability")
    sub = parser.add_subparsers(dest="command")

    p_demo = sub.add_parser("demo", help="Run demo trace")
    p_validate = sub.add_parser("validate", help="Compile and validate artifacts")
    p_api = sub.add_parser("api", help="Start Flask API")
    p_api.add_argument("--host", default="0.0.0.0")
    p_api.add_argument("--port", type=int, default=8500)

    args = parser.parse_args(argv)
    if args.command == "demo":
        return demo()
    if args.command == "validate":
        return validate_all()
    if args.command == "api":
        return run_api(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
