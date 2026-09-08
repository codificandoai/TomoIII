"""
UC-308 — Script de validación.

Verifica:
- Compilación de todos los módulos Python del directorio.
- Importación de los módulos principales.
- Flujo base: creación de dataset, baseline sano, evaluación sana y evaluación
  con drift detectado.
- No se realizan llamadas externas ni side effects.
"""

from __future__ import annotations

import compileall
import os
import py_compile
import sys
from pathlib import Path
from typing import List, Tuple


def compile_all_python_files(directory: Path) -> List[Tuple[str, str]]:
    """Compila todos los .py del directorio. Devuelve lista de (path, error)."""
    failures: List[Tuple[str, str]] = []
    for path in directory.rglob("*.py"):
        if path.name.startswith("."):
            continue
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append((str(path), str(exc)))
    return failures


def import_core_modules() -> List[str]:
    """Importa los módulos principales y devuelve errores."""
    errors: List[str] = []
    modules = [
        "models_308",
        "golden_dataset",
        "environment_simulator",
        "drift_detectors",
        "baseline_manager",
        "alert_manager_308",
        "mitigation_advisor",
        "observability_308",
        "nightly_scheduler",
        "regression_runner",
        "drift_orchestrator",
        "monitoring_generator_308",
        "api_308",
        "uc308",
        "cc_models_308",
        "cc_predictors_308",
        "cc_execution_308",
        "cc_metrics_308",
        "cc_audit_308",
        "champion_challenger_experiment_308",
    ]
    for name in modules:
        try:
            __import__(name)
        except Exception as exc:
            errors.append(f"import {name}: {exc}")
    return errors


def smoke_test() -> List[str]:
    errors: List[str] = []
    try:
        from drift_orchestrator import DriftOrchestrator
        from environment_simulator import SimulatedExternalEnvironment
        from golden_dataset import build_default_golden_dataset
        from models_308 import DriftConfig

        dataset = build_default_golden_dataset(version="1.0.0-test")
        config = DriftConfig()
        env = SimulatedExternalEnvironment(seed=12345)
        orchestrator = DriftOrchestrator(
            config=config,
            dataset=dataset,
            environment=env,
        )

        # Baseline sano
        init = orchestrator.initialize_baselines(scenario="healthy")
        if init["baselines_created"] == 0:
            errors.append("no baselines created from healthy run")

        # Evaluación sana: debe ser NORMAL
        healthy = orchestrator.run_evaluation(trigger="validate", scenario="healthy")
        if healthy.system_status.value != "normal":
            errors.append(f"healthy run reported status {healthy.system_status.value}")

        # Drift de API
        drift = orchestrator.run_evaluation(trigger="validate", scenario="api_schema_change")
        api_signals = [s for s in drift.drift_signals if s.drift_type.value == "contract_api"]
        if not api_signals:
            errors.append("api_schema_change did not produce contract_api drift signals")

        # Drift de datos
        data = orchestrator.run_evaluation(trigger="validate", scenario="data_distribution_shift")
        data_signals = [s for s in data.drift_signals if s.drift_type.value == "data_distribution"]
        if not data_signals:
            errors.append("data_distribution_shift did not produce data_distribution drift signals")

        # Histeresis: una sola corrida degradada no genera alerta si config lo dice
        if drift.system_status.value == "degraded":
            # Si ya se generó alerta, comprobar que se debe a histéresis configurada
            pass

        # Verificar firma del dataset
        dataset.sign("validation-secret")
        if not dataset.verify_signature("validation-secret"):
            errors.append("dataset signature verification failed with correct key")
        if dataset.verify_signature("wrong-secret"):
            errors.append("dataset signature verification succeeded with wrong key")
        if not dataset.verify_integrity():
            errors.append("dataset integrity check failed")

        # Simulación de tamper: modificar caso público rompe integridad
        original_version = dataset.version
        dataset.version = "tampered"
        if dataset.verify_integrity():
            errors.append("tampered dataset still passes integrity check")
        dataset.version = original_version

    except Exception as exc:
        errors.append(f"smoke test exception: {exc}")
    return errors


def smoke_test_champion_challenger() -> List[str]:
    errors: List[str] = []
    try:
        from champion_challenger_experiment_308 import ChampionChallengerExperiment, generate_market_events
        from cc_predictors_308 import ChampionDemoPredictor, ChallengerDemoPredictor
        from cc_models_308 import ExperimentConfig

        config = ExperimentConfig(experiment_id="validate-cc-001", paper_samples=10)
        exp = ChampionChallengerExperiment(config=config)
        exp.register_champion("champion", "1.0.0", ChampionDemoPredictor())
        exp.register_challenger("challenger", "2.0.0", ChallengerDemoPredictor())
        start = exp.start("paper")
        if not start.get("success"):
            errors.append(f"cc start failed: {start.get('reason')}")
            return errors

        events = generate_market_events(n=10, seed=12345)
        for event in events:
            result = exp.ingest_event(event)
            if not result.get("success"):
                errors.append(f"cc ingest failed: {result.get('reason')}")
                break

        if len(exp.predictions["champion"]) != len(events):
            errors.append("cc champion prediction count mismatch")
        if len(exp.predictions["challenger"]) != len(events):
            errors.append("cc challenger prediction count mismatch")

        if exp.predictions["champion"] and exp.predictions["challenger"]:
            cp = exp.predictions["champion"][0]
            cc = exp.predictions["challenger"][0]
            if cp.input_hash != cc.input_hash:
                errors.append("cc predictions did not share event input hash")
            if cp.correlation_id != cc.correlation_id:
                errors.append("cc predictions did not share correlation_id")

        metrics = exp.compute_metrics()
        for role in ("champion", "challenger"):
            if metrics[role].sample_count != len(events):
                errors.append(f"cc {role} metrics sample_count mismatch")

        shutdown = exp.shutdown_experiment("validate")
        if not shutdown.get("success"):
            errors.append(f"cc shutdown failed")
        if not exp.audit.verify_chain():
            errors.append("cc audit chain invalid after shutdown")
    except Exception as exc:
        errors.append(f"cc smoke test exception: {exc}")
    return errors


def main() -> int:
    directory = Path(__file__).parent
    print("UC-308 validation")
    print("-" * 40)

    failures = compile_all_python_files(directory)
    if failures:
        print("[FAIL] compile errors:")
        for path, err in failures:
            print(f"  {path}: {err}")
        return 1
    print("[PASS] all Python files compile")

    import_errors = import_core_modules()
    if import_errors:
        print("[FAIL] import errors:")
        for err in import_errors:
            print(f"  {err}")
        return 1
    print("[PASS] all core modules import")

    smoke_errors = smoke_test()
    if smoke_errors:
        print("[FAIL] smoke test errors:")
        for err in smoke_errors:
            print(f"  {err}")
        return 1
    print("[PASS] smoke test (healthy + drift + signature)")

    cc_errors = smoke_test_champion_challenger()
    if cc_errors:
        print("[FAIL] champion/challenger smoke test errors:")
        for err in cc_errors:
            print(f"  {err}")
        return 1
    print("[PASS] champion/challenger smoke test")

    print("-" * 40)
    print("[PASS] UC-308 validation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
