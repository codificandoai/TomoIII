"""CLI para UC-292 - Sistema Multi-Agente de Trading."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from config import get_config
from graph import build_agent, run_agent
from market_data import SyntheticMarketDataGenerator
from models import MarketTick, NewsItem, Portfolio, TradingRequest


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _ticks_from_json(raw: List[Dict[str, Any]]) -> List[MarketTick]:
    return [MarketTick(**item) for item in raw]


def _news_from_json(raw: List[Dict[str, Any]]) -> List[NewsItem]:
    return [NewsItem(**item) for item in raw]


def cmd_perceive(args: argparse.Namespace) -> int:
    from perception import MarketPerceptionPipeline

    data = _load_json(args.input)
    ticks = _ticks_from_json(data.get("ticks", [data]))
    news = _news_from_json(data.get("news", []))
    symbol = args.symbol or ticks[0].symbol
    pipeline = MarketPerceptionPipeline()
    snapshots = pipeline.perceive(
        request_id="cli-perceive",
        ticks_by_symbol={symbol: ticks},
        news=news,
    )
    _print_json({symbol: snapshots[symbol].to_dict()})
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    from trading_agents import PerceptionAgent, SentimentAnalyst, TechnicalAnalyst
    from perception import MarketPerceptionPipeline

    data = _load_json(args.input)
    ticks = _ticks_from_json(data.get("ticks", [data]))
    news = _news_from_json(data.get("news", []))
    symbol = args.symbol or ticks[0].symbol
    perception = PerceptionAgent(MarketPerceptionPipeline())
    request = TradingRequest(
        symbols=[symbol],
        ticks=ticks,
        news=news,
    )
    snapshots = perception.perceive(request)
    snap = snapshots[symbol]
    t = TechnicalAnalyst().analyze(snap)
    s = SentimentAnalyst().analyze(snap)
    _print_json({
        "snapshot": snap.to_dict(),
        "technical": t.to_dict(),
        "sentiment": s.to_dict(),
    })
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    data = _load_json(args.input)
    request = TradingRequest.from_dict(data)
    final_state = run_agent(request, get_config(), recursion_limit=50)
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") in ("done", "awaiting_confirmation") else 1


def cmd_execute(args: argparse.Namespace) -> int:
    data = _load_json(args.input)
    data["approved"] = True
    request = TradingRequest.from_dict(data)
    final_state = run_agent(request, get_config(), recursion_limit=50)
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") == "done" else 1


def cmd_predict_tick(args: argparse.Namespace) -> int:
    from world_model import TradingWorldModel

    wm = TradingWorldModel(get_config().model)
    data = _load_json(args.input)
    symbol = args.symbol or data.get("symbol", "AAPL")
    ticks = _ticks_from_json(data.get("ticks", [data]))
    if len(ticks) < 2:
        print("Need at least 2 ticks for prediction/feedback", file=sys.stderr)
        return 1

    # Entrenar el cerebro con pares consecutivos de ticks
    for i in range(len(ticks) - 1):
        wm.update_from_tick(
            symbol=symbol,
            current_price=ticks[i].last_price,
            next_price=ticks[i + 1].last_price,
        )

    current = ticks[-1].last_price
    result = wm.predict_next_price(symbol, current)
    _print_json(result)
    return 0


def cmd_brain(args: argparse.Namespace) -> int:
    from central_brain import CentralBrain
    from models import TradingRequest

    brain = CentralBrain(get_config())
    data = _load_json(args.input)
    symbol = args.symbol or data.get("symbol", "AAPL")
    ticks = _ticks_from_json(data.get("ticks", [data]))
    request = TradingRequest(symbols=[symbol], ticks=ticks, news=_news_from_json(data.get("news", [])))
    brain.observe(request)
    _print_json(brain.get_context(symbol))
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from train import train_world_model

    result = train_world_model(
        n_samples=args.samples,
        config=get_config(),
        output_dir=args.output_dir,
    )
    _print_json(result)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    port = args.port or int(os.getenv("UC292_PORT", get_config().port))
    os.environ["UC292_PORT"] = str(port)
    from api import app

    app.run(host="0.0.0.0", port=port, debug=False)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Demo rápido con datos sintéticos."""
    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=cfg.market.seed)
    ticks = gen.generate_ticks("AAPL", n=200)
    news = [
        NewsItem(text="AAPL announces partnership with OpenAI", source="bloomberg"),
    ]
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        news=news,
        portfolio=Portfolio(cash=100_000.0),
        approved=args.approved,
    )
    final_state = run_agent(request, cfg, recursion_limit=50)
    _print_json(final_state.get("final_output"))
    return 0 if final_state.get("status") in ("done", "awaiting_confirmation") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="UC-292", description="Multi-Agent Trading System")
    subparsers = parser.add_subparsers(dest="command")

    perceive_parser = subparsers.add_parser("perceive", help="Procesa ticks y noticias")
    perceive_parser.add_argument("--input", required=True, help="Archivo JSON con ticks/noticias")
    perceive_parser.add_argument("--symbol", help="Símbolo a procesar")

    analyze_parser = subparsers.add_parser("analyze", help="Analiza snapshot técnico y de sentimiento")
    analyze_parser.add_argument("--input", required=True)
    analyze_parser.add_argument("--symbol")

    plan_parser = subparsers.add_parser("plan", help="Genera plan de trading")
    plan_parser.add_argument("--input", required=True, help="Archivo JSON de TradingRequest")

    execute_parser = subparsers.add_parser("execute", help="Ejecuta plan aprobado")
    execute_parser.add_argument("--input", required=True)

    predict_parser = subparsers.add_parser("predict-tick", help="Entrena y predice el siguiente tick")
    predict_parser.add_argument("--input", required=True, help="Archivo JSON con ticks")
    predict_parser.add_argument("--symbol", help="Símbolo")

    brain_parser = subparsers.add_parser("brain", help="Observa el mercado y consulta el cerebro central")
    brain_parser.add_argument("--input", required=True, help="Archivo JSON con ticks/noticias")
    brain_parser.add_argument("--symbol", help="Símbolo")

    train_parser = subparsers.add_parser("train", help="Entrena world model con datos sintéticos")
    train_parser.add_argument("--samples", type=int, default=500)
    train_parser.add_argument("--output-dir", default=None)

    serve_parser = subparsers.add_parser("serve", help="Inicia API Flask")
    serve_parser.add_argument("--port", type=int)

    run_parser = subparsers.add_parser("run", help="Demo completo con datos sintéticos")
    run_parser.add_argument("--approved", action="store_true", help="Autoriza ejecución")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "perceive": cmd_perceive,
        "analyze": cmd_analyze,
        "plan": cmd_plan,
        "execute": cmd_execute,
        "predict-tick": cmd_predict_tick,
        "brain": cmd_brain,
        "train": cmd_train,
        "serve": cmd_serve,
        "run": cmd_run,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
