"""
Codificando.AI
UC-702: Disponibilidad de recursos subutilizados (CPU, GPU, memoria, disco)
en tiempo real — on-premise y en la nube (spot / free-tier) — con
sumarización a un pool compartido, dashboards Grafana y detección de
interrupción de instancias spot.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Este archivo es el punto de entrada CLI que expone:
  - snapshot puntual de recursos del nodo local
  - agente de nodo (telemetría continua + vigilancia spot en background)
  - vigilancia de interrupción de instancia spot en primer plano
  - resumen de capacidad del clúster vía API
  - generación de dashboards Grafana
  - inicio de la API REST Flask (incluye el frontend unificado)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from grafana_dashboards import write_dashboards
from models import ProviderKind
from node_agent import NodeAgent, build_node_info
from resource_monitor import ResourceMonitor
from spot_watcher import AWSSpotWatcher


def cmd_monitor(args: argparse.Namespace) -> int:
    from underutilization import evaluate
    from config import MonitorConfig

    monitor = ResourceMonitor()
    snapshot = monitor.snapshot()
    config = MonitorConfig()
    capacity = evaluate(snapshot, config.thresholds)
    print(json.dumps({
        "snapshot": snapshot.to_dict(),
        "available_capacity": capacity.to_dict(),
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    agent = NodeAgent(api_base_url=args.api)
    print(f"Agente iniciado para nodo {agent.info.node_id} -> {agent.api_base_url}", file=sys.stderr)
    agent.start_spot_watch_background()
    agent.run_telemetry_loop(max_iterations=args.iterations)
    return 0


def cmd_spot_watch(args: argparse.Namespace) -> int:
    info = build_node_info(args.node_id)
    watcher = AWSSpotWatcher(info.node_id)
    event = watcher.run(max_iterations=args.iterations)
    if event:
        print(json.dumps(event.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps({"interrupted": False, "node_id": info.node_id}))
    return 0


def cmd_dashboards(_args: argparse.Namespace) -> int:
    output_dir = os.path.join(os.path.dirname(__file__), "dashboards")
    paths = write_dashboards(output_dir)
    print("Dashboards generados:")
    for p in paths:
        print(f"  - {p}")
    return 0


def cmd_api(args: argparse.Namespace) -> int:
    from api import app

    port = args.port or int(os.environ.get("UC702_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-702 Underutilized Capacity & Spot Watch CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_monitor = sub.add_parser("monitor", help="Imprime una foto instantánea de recursos del nodo local")
    p_monitor.set_defaults(func=cmd_monitor)

    p_agent = sub.add_parser("agent", help="Ejecuta el agente de nodo (telemetría + vigilancia spot)")
    p_agent.add_argument("--api", default=None, help="URL base de la API central (default: UC702_API_BASE_URL o localhost:5000)")
    p_agent.add_argument("--iterations", type=int, default=None, help="Número de iteraciones (uso en pruebas); infinito si se omite")
    p_agent.set_defaults(func=cmd_agent)

    p_spot = sub.add_parser("spot-watch", help="Vigila interrupción de instancia spot en primer plano (AWS)")
    p_spot.add_argument("--node-id", default=None, help="Identificador del nodo")
    p_spot.add_argument("--iterations", type=int, default=None, help="Límite de sondeos (uso en pruebas)")
    p_spot.set_defaults(func=cmd_spot_watch)

    p_dash = sub.add_parser("dashboards", help="Genera dashboards de Grafana")
    p_dash.set_defaults(func=cmd_dashboards)

    p_api = sub.add_parser("api", help="Inicia la API REST Flask y el frontend unificado")
    p_api.add_argument("--port", type=int, default=None)
    p_api.set_defaults(func=cmd_api)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
