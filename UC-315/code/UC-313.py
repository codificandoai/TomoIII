"""UC-313 — Plasticidad Sináptica Digital: punto de entrada.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

Uso:
    python UC-313.py --demo          # Ejecuta demostración de plasticidad
    python UC-313.py --server        # Levanta API Flask en el puerto configurado
"""
from __future__ import annotations

import argparse
import sys

from brain import demo_plasticity
from api import app, main as api_main
from compatibility_validator import main as validate_main
from self_awareness_loop import SelfAwarenessLoop


def main() -> int:
    parser = argparse.ArgumentParser(description="UC-313 — Plasticidad Sináptica Digital y Autoconciencia AGI.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true", help="Ejecuta la demostración de plasticidad.")
    group.add_argument("--self-aware", action="store_true", help="Ejecuta el bucle recursivo de autoconciencia AGI.")
    group.add_argument("--validate", action="store_true", help="Valida la compatibilidad del stack AGI completo.")
    group.add_argument("--server", action="store_true", help="Levanta la API REST Flask.")
    args = parser.parse_args()

    if args.demo:
        demo_plasticity()
        return 0
    if args.self_aware:
        loop = SelfAwarenessLoop()
        loop.run_loop(n_episodes=3, symbol="AAPL", approved=True, mode="paper")
        return 0
    if args.validate:
        return validate_main()
    if args.server:
        return api_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
