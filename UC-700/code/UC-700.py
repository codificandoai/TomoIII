"""
Codificando.AI
UC-700: Autosanación avanzada del entrenamiento distribuido con agentic AI.

Referencia de negocio:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: ETL (batch-online-offline).
- cloudatasecure.com: Vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Este archivo sirve como punto de entrada CLI para ejecutar el pipeline de
autosanación sin levantar la API REST.  También genera los dashboards de
Grafana en disco.

Uso:
    python UC-700.py simulate --node N-R-A-1
    python UC-700.py dashboards
    python UC-700.py api  # inicia Flask
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from config import AgentConfig
from grafana_dashboards import write_dashboards
from orchestrator import SelfHealingOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc700")


def _incident_to_json(incident) -> str:
    import json
    from dataclasses import asdict

    d = asdict(incident)
    for k in ("created_at", "resolved_at"):
        if d.get(k) and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    return json.dumps(d, indent=2, ensure_ascii=False, default=str)


def cmd_simulate(args: argparse.Namespace) -> int:
    config = AgentConfig()
    orchestrator = SelfHealingOrchestrator(config=config, dry_run=True)
    orchestrator.build_default_cluster()
    incident = orchestrator.run_pipeline(
        node_id=args.node,
        device_id=f"{args.node}-gpu-0" if not args.device else args.device,
        inject_failure=True,
        operator_id=args.operator,
    )
    print(_incident_to_json(incident))
    return 0


def cmd_dashboards(_args: argparse.Namespace) -> int:
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboards")
    paths = write_dashboards(output_dir)
    logger.info("Dashboards generados en %s: %s", output_dir, paths)
    return 0


def cmd_api(_args: argparse.Namespace) -> int:
    from api import app

    port = int(os.environ.get("UC700_PORT", "5000"))
    logger.info("Iniciando API REST en 0.0.0.0:%s", port)
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-700 Self-Healing Training CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sim = sub.add_parser("simulate", help="Simula un incidente de fallo de memoria GPU")
    p_sim.add_argument("--node", default="N-R-A-1")
    p_sim.add_argument("--device", default=None)
    p_sim.add_argument("--operator", default=None)
    p_sim.set_defaults(func=cmd_simulate)

    p_dash = sub.add_parser("dashboards", help="Genera dashboards de Grafana")
    p_dash.set_defaults(func=cmd_dashboards)

    p_api = sub.add_parser("api", help="Inicia la API REST Flask")
    p_api.set_defaults(func=cmd_api)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
