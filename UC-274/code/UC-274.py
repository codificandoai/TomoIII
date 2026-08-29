"""
Codificando.AI
UC-274: Web3 Multi-Agent Blockchain — Ecosistema Descentralizado BFT.
Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from config import get_config
from marketplace import EnergyMarketplace


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta demo del ecosistema Web3 multi-agente."""
    config = get_config()
    mp = EnergyMarketplace(config)

    print("=" * 65)
    print("DEMO: WEB3 MULTI-AGENT BLOCKCHAIN (UC-274)")
    print("Ecosistema Descentralizado Byzantine-Fault-Tolerant")
    print("=" * 65)

    # 1. Registrar agentes prosumidores
    print("\n--- 1. Registrar agentes prosumidores ---")
    agents = [
        ("solar_farm_alpha", 5_000_000, {"role": "prosumer", "energy": "solar"}),
        ("wind_farm_beta", 5_000_000, {"role": "prosumer", "energy": "wind"}),
        ("household_gamma", 2_000_000, {"role": "consumer"}),
        ("battery_delta", 3_000_000, {"role": "storage"}),
    ]
    for name, balance, meta in agents:
        result = mp.register_agent(name, balance, meta)
        print(f"  {name}: address={result['address'][:16]}... DID={result['did']}")

    # 2. Crear ofertas de energía
    print("\n--- 2. Crear ofertas de energia ---")
    offer1 = mp.create_energy_offer("solar_farm_alpha", "sell", 50.0, 800, "solar")
    offer2 = mp.create_energy_offer("wind_farm_beta", "sell", 30.0, 900, "wind")
    print(f"  Solar offer: {offer1['offer_id']}")
    print(f"  Wind offer: {offer2['offer_id']}")

    # 3. Match trade (compra de energía)
    print("\n--- 3. Match trade (compra P2P) ---")
    trade = mp.match_trade("household_gamma", offer1["offer_id"], 20.0)
    if "error" not in trade:
        print(f"  Trade: {trade['trade_id']} ({trade['status']}) total={trade['total_wei']} wei")
    else:
        print(f"  Trade error: {trade['error']}")

    # 4. Confirmar entrega (oracle)
    print("\n--- 4. Confirmar entrega (oracle) ---")
    if "error" not in trade:
        delivery = mp.confirm_delivery(trade["trade_id"])
        print(f"  Delivery: {delivery.get('status', delivery.get('error'))}")
        if "seller_received" in delivery:
            print(f"  Seller received: {delivery['seller_received']} wei, fee: {delivery['fee']} wei")

    # 5. Escrow
    print("\n--- 5. Escrow condicional ---")
    escrow = mp.create_escrow("battery_delta", "solar_farm_alpha", 100_000, "deliver 10 kWh")
    print(f"  Escrow: {escrow.get('escrow_id', escrow.get('error'))} ({escrow.get('status', '')})")

    # 6. Reputación
    print("\n--- 6. Reputacion on-chain ---")
    mp.record_trade_reputation("solar_farm_alpha", True)
    mp.record_trade_reputation("household_gamma", True)
    mp.record_trade_reputation("battery_delta", False)

    for name in ["solar_farm_alpha", "household_gamma", "battery_delta"]:
        rep = mp.get_reputation(name)
        print(f"  {name}: rep={rep.get('reputation', 'N/A')} trades={rep.get('total_trades', 0)}")

    # 7. Endorsement
    print("\n--- 7. Endorsement ---")
    endorse = mp.endorse_agent("solar_farm_alpha", "wind_farm_beta", 0.8)
    print(f"  Endorsement: {endorse.get('target', 'N/A')[:16]}... new_rep={endorse.get('new_reputation')}")

    # 8. Blockchain status
    print("\n--- 8. Blockchain Status ---")
    status = mp.get_chain_status()
    _print_json(status)

    # 9. Marketplace status
    print("\n--- 9. Marketplace Status ---")
    mkt = mp.get_marketplace_status()
    _print_json(mkt)

    # 10. Verificar cadena
    print("\n--- 10. Verificar integridad de la cadena ---")
    verify = mp.verify_chain()
    print(f"  Chain valid: {verify['valid']}, height: {verify['block_height']}")

    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from api import app
    port = args.port or get_config().port
    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-274",
        description="Web3 Multi-Agent Blockchain — Ecosistema Descentralizado BFT"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Run Web3 marketplace demo")

    serve_p = subparsers.add_parser("serve", help="Start the Flask API server")
    serve_p.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {"run": cmd_run, "serve": cmd_serve}
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
