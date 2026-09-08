"""
UC-308 — CLI de demostración y API para Agent Drift / Environmental Degradation.

Subcomandos:
  api     : lanza el servidor Flask en el puerto por defecto 5308.
  run     : ejecuta una evaluación del golden dataset y muestra el JSON.
  demo    : muestra escenarios healthy, drift y supresión por ventanas.
  validate: ejecuta validación rápida de módulos y flujo base.

Toda ejecución es simulada: no se realizan llamadas de red, ni se escriben
archivos reales, ni se modifican prompts/código/políticas/selectores.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from drift_orchestrator import DriftOrchestrator
from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import build_default_golden_dataset
from models_308 import DriftConfig, SystemStatus


SEED = 42


def _build_orchestrator(seed: int = SEED) -> DriftOrchestrator:
    dataset = build_default_golden_dataset(version="1.0.0")
    environment = SimulatedExternalEnvironment(seed=seed)
    config = DriftConfig()
    return DriftOrchestrator(
        config=config,
        dataset=dataset,
        environment=environment,
    )


def cmd_api(args: argparse.Namespace) -> int:
    import api_308
    print(f"Starting UC-308 API on {args.host}:{args.port}")
    api_308.app.run(host=args.host, port=args.port, debug=False)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    orchestrator = _build_orchestrator(seed=args.seed)
    print("Initializing baselines from healthy run...")
    orchestrator.initialize_baselines(scenario="healthy")
    print(f"Running evaluation with scenario={args.scenario!r}...")
    run = orchestrator.run_evaluation(
        trigger="cli",
        scenario=args.scenario,
    )
    print(json.dumps(run.to_dict(), indent=2, default=str))
    return 0 if run.system_status == SystemStatus.NORMAL else 1


def cmd_demo(args: argparse.Namespace) -> int:
    orchestrator = _build_orchestrator(seed=args.seed)
    print("=== UC-308 Agent Drift / Environmental Degradation Demo ===\n")

    print("[1] Healthy baseline run")
    init = orchestrator.initialize_baselines(scenario="healthy")
    print(f"    Baselines created: {init['baselines_created']}")
    healthy_run = orchestrator.history[-1]
    print(f"    Success rate: {healthy_run.aggregate['success_rate']:.2%}")
    print(f"    Quality score: {healthy_run.aggregate['quality_score']:.3f}")
    print(f"    System status: {healthy_run.system_status.value}\n")

    scenarios = [
        ("API schema drift", "api_schema_change"),
        ("HTML selector drift", "html_selector_change"),
        ("Data distribution shift", "data_distribution_shift"),
        ("Latency regression", "latency_regression"),
        ("Behavioral regression", "behavioral_regression"),
        ("Quality regression", "quality_regression"),
    ]

    for title, scenario in scenarios:
        print(f"[2.{scenario}] {title}")
        run = orchestrator.run_evaluation(trigger="demo", scenario=scenario)
        print(f"    Success rate: {run.aggregate['success_rate']:.2%}")
        print(f"    System status: {run.system_status.value}")
        print(f"    Drift signals: {len(run.drift_signals)}")
        for signal in run.drift_signals[:3]:
            print(f"      - {signal.drift_type.value}: {signal.status.value} ({signal.message[:70]})")
        print()

    print("[3] Consecutive-window alert suppression")
    print("    Running healthy run twice more to clear hysteresis...")
    for _ in range(2):
        orchestrator.run_evaluation(trigger="demo", scenario="healthy")
    degraded_runs = orchestrator.alert_manager.run_history[-2:]
    print(f"    Last two statuses: {[r[2].value for r in degraded_runs]}")
    active = orchestrator.alert_manager.get_active_alerts()
    print(f"    Active alerts after consecutive healthy runs: {len(active)}\n")

    print("[4] Metrics preview (first 10 lines)")
    lines = orchestrator.get_metrics().splitlines()
    for line in lines[:10]:
        print(f"    {line}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    import validate_uc308
    return validate_uc308.main()


def cmd_champion_challenger(args: argparse.Namespace) -> int:
    from champion_challenger_experiment_308 import ChampionChallengerExperiment, generate_market_events
    from cc_predictors_308 import ChampionDemoPredictor, ChallengerDemoPredictor
    from cc_models_308 import ExperimentConfig

    print("=== UC-308 Champion/Challenger Experiment Demo ===")
    config = ExperimentConfig(
        experiment_id="demo-cc-001",
        symbol="DEMO",
        min_paired_samples=30,
        walk_forward_samples=30,
        shadow_samples=30,
        paper_samples=30,
    )
    exp = ChampionChallengerExperiment(config=config)
    exp.register_champion("champion", "1.0.0", ChampionDemoPredictor())
    exp.register_challenger("challenger", "2.0.0", ChallengerDemoPredictor())
    print(f"Experiment {exp.experiment_id} registered champion and challenger.")

    stage_samples = {
        "historical": config.min_paired_samples,
        "walk_forward": config.walk_forward_samples,
        "shadow": config.shadow_samples,
        "paper": config.paper_samples,
    }
    total_samples = sum(stage_samples.values())
    all_events = generate_market_events(symbol=config.symbol, n=total_samples, seed=args.seed)
    cursor = 0
    stages = ("historical", "walk_forward", "shadow", "paper")
    for i, stage in enumerate(stages):
        if i == 0:
            result = exp.start(stage)
        else:
            result = exp.transition(stage)
        if not result.get("success"):
            print(f"Start/transition to {stage} failed: {result.get('reason')}")
            return 1
        n = stage_samples[stage]
        events = all_events[cursor:cursor + n]
        cursor += n
        for event in events:
            exp.ingest_event(event)
        gate = exp.evaluate_stage_gate()
        metrics = exp.compute_metrics()
        print(f"\n[{stage}] events={len(events)} gate={gate.get('gate') or gate.get('reason')}")
        for role in ("champion", "challenger"):
            m = metrics[role]
            print(f"  {role}: bid_mae={m.bid_mae:.4f} ask_mae={m.ask_mae:.4f} pnl={m.total_pnl:.2f} drawdown={m.max_drawdown:.4f}")
        if exp.state in ("rejected", "contained"):
            print(f"Experiment ended in state {exp.state}")
            break
        if exp.state == "awaiting_approval":
            break

    rec = exp.recommend_promotion()
    print(f"\nRecommendation: action={rec.recommended_action} report_hash={rec.report_hash[:16]}...")
    print(f"  reason: {rec.reason}")

    # Simulate explicit human approval.
    approval = exp.approve_promotion(
        rec.report_hash,
        reviewer_id="human-operator-1",
        request_id="demo-req-001",
        ttl_seconds=3600.0,
    )
    print(f"Approval result: success={approval.get('success')} state={exp.state} reason={approval.get('reason', '')}")

    # Shutdown and reconcile.
    shutdown = exp.shutdown_experiment("demo-complete")
    print(f"Shutdown final_state={shutdown['final_state']} events_ingested={shutdown['reconciliation']['events_ingested']}")
    print(f"Audit chain valid: {exp.audit.verify_chain()}")
    return 0


def main(argv: list = sys.argv[1:]) -> int:
    parser = argparse.ArgumentParser(
        prog="UC-308",
        description="Agent Drift / Environmental Degradation orchestration CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_api = sub.add_parser("api", help="Run Flask API server")
    p_api.add_argument("--host", default="0.0.0.0")
    p_api.add_argument("--port", type=int, default=5308)

    p_run = sub.add_parser("run", help="Run a single evaluation")
    p_run.add_argument("--scenario", default="healthy", help="Drift scenario to inject")
    p_run.add_argument("--seed", type=int, default=SEED, help="Random seed for reproducibility")

    p_demo = sub.add_parser("demo", help="Run interactive demonstration scenarios")
    p_demo.add_argument("--seed", type=int, default=SEED, help="Random seed for reproducibility")

    p_validate = sub.add_parser("validate", help="Run validation checks")

    p_cc = sub.add_parser("champion-challenger", help="Run Champion/Challenger experiment demo")
    p_cc.add_argument("--seed", type=int, default=SEED, help="Random seed for reproducibility")

    args = parser.parse_args(argv)

    commands = {
        "api": cmd_api,
        "run": cmd_run,
        "demo": cmd_demo,
        "validate": cmd_validate,
        "champion-challenger": cmd_champion_challenger,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
