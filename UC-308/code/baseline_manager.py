"""
UC-308 — Gestión de baselines por agente, herramienta, entorno y versión.
"""

from __future__ import annotations

import random
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from drift_detectors import _aggregate_results, _group_results_by_tool
from models_308 import AgentResult, Baseline, BaselineMetrics, DriftConfig, EvaluationRun


class BaselineManager:
    """
    Almacena baselines versionados y permite crearlos a partir de ejecuciones
    saludables del golden dataset.
    """

    def __init__(self):
        self.baselines: Dict[Tuple[str, str, str, str], Baseline] = {}

    def set_baseline(self, baseline: Baseline) -> None:
        """Registra o sobrescribe un baseline."""
        self.baselines[baseline.key()] = baseline

    def get_baseline(
        self,
        agent_id: str,
        tool: str,
        environment: str,
        agent_version: str,
    ) -> Optional[Baseline]:
        return self.baselines.get((agent_id, tool, environment, agent_version))

    def list_baselines(self) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self.baselines.values()]

    def get_by_id(self, baseline_id: str) -> Optional[Baseline]:
        for baseline in self.baselines.values():
            if baseline.baseline_id == baseline_id:
                return baseline
        return None

    @staticmethod
    def _deterministic_distribution_samples(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Genera muestras deterministas a partir de parámetros declarados del caso."""
        distribution: Dict[str, Any] = {"params": params}
        if not params:
            return distribution
        rng = random.Random(12345)
        if params.get("type") == "numeric":
            mean = params.get("baseline_mean", 100.0)
            std = params.get("baseline_std", 10.0)
            samples = [rng.gauss(mean, std) for _ in range(1000)]
            distribution["samples"] = samples
        elif params.get("type") == "categorical":
            categories = params.get("categories", [])
            probs = params.get("baseline_probs", [])
            if categories and probs:
                total = 1000
                counts: Dict[str, int] = {}
                for _ in range(total):
                    cat = rng.choices(categories, weights=probs, k=1)[0]
                    counts[cat] = counts.get(cat, 0) + 1
                distribution["category_counts"] = counts
        return distribution

    def record_baseline_from_run(
        self,
        run: EvaluationRun,
        config: DriftConfig,
        label: str = "healthy",
    ) -> List[Baseline]:
        """Crea un baseline por herramienta a partir de una ejecución."""
        created: List[Baseline] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            baseline_id = f"baseline-{uuid.uuid4().hex[:8]}"
            key = (run.agent_id, tool, run.environment, run.agent_version)
            agg = _aggregate_results(results)

            # Schema / HTML: unión de fingerprints observados exitosos.
            ok_results = [r for r in results if r.success]
            schema_fps = sorted({r.schema_fingerprint for r in ok_results if r.schema_fingerprint})
            html_fps = sorted({r.html_fingerprint for r in ok_results if r.html_fingerprint})

            # Distribución: preferimos parámetros declarados del caso.
            distribution: Dict[str, Any] = {}
            representative = next((r for r in ok_results if r.distribution_params), None)
            if representative and representative.distribution_params:
                distribution = self._deterministic_distribution_samples(representative.distribution_params)
            else:
                if any(r.data_samples for r in ok_results):
                    # Fallback: usar la primera muestra real (más ruidoso).
                    first = next((r for r in ok_results if r.data_samples), None)
                    if first:
                        distribution["samples"] = first.data_samples[:]
                if any(r.category_counts for r in ok_results):
                    first = next((r for r in ok_results if r.category_counts), None)
                    if first:
                        distribution["category_counts"] = dict(first.category_counts)

            metrics = BaselineMetrics(
                success_rate=agg["success_rate"],
                quality_score=agg["quality_score"],
                latency_ms_mean=agg["latency_ms_mean"],
                latency_ms_p95=agg["latency_ms_p95"],
                tokens_mean=agg["tokens_mean"],
                error_rate=agg["error_rate"],
                timeout_rate=agg["timeout_rate"],
                resource_mean=agg["resource_mean"],
                schema_fingerprint=schema_fps[0] if schema_fps else "",
                schema_fingerprints=schema_fps,
                html_selector_fingerprint=html_fps[0] if html_fps else "",
                html_selector_fingerprints=html_fps,
                distribution=distribution,
                behavior={
                    "avg_steps": agg["avg_steps"],
                    "avg_retries": agg["avg_retries"],
                    "escalation_rate": agg["escalation_rate"],
                    "uc300_block_rate": agg["uc300_block_rate"],
                    "uc290_override_rate": agg["uc290_override_rate"],
                },
            )

            thresholds = {
                "label": label,
                "source_run_id": run.run_id,
                "dataset_version": run.dataset_version,
                "dataset_hash": run.dataset_hash,
            }

            baseline = Baseline(
                baseline_id=baseline_id,
                agent_id=run.agent_id,
                tool=tool,
                environment=run.environment,
                agent_version=run.agent_version,
                created_at=time.time(),
                source_run_id=run.run_id,
                metrics=metrics,
                thresholds=thresholds,
            )
            self.set_baseline(baseline)
            created.append(baseline)
        return created

    def create_synthetic_baseline(
        self,
        agent_id: str,
        tool: str,
        environment: str,
        agent_version: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Baseline:
        """Crea un baseline manual (útil para tests)."""
        baseline_id = f"synthetic-{uuid.uuid4().hex[:8]}"
        metrics_obj = BaselineMetrics()
        if metrics:
            for k, v in metrics.items():
                if hasattr(metrics_obj, k):
                    setattr(metrics_obj, k, v)
        baseline = Baseline(
            baseline_id=baseline_id,
            agent_id=agent_id,
            tool=tool,
            environment=environment,
            agent_version=agent_version,
            created_at=time.time(),
            source_run_id="synthetic",
            metrics=metrics_obj,
        )
        self.set_baseline(baseline)
        return baseline

    def clear(self) -> None:
        self.baselines.clear()


def build_default_baselines_from_run(
    run: EvaluationRun,
    config: DriftConfig,
) -> BaselineManager:
    """Helper para crear un manager con baselines a partir de una ejecución sana."""
    manager = BaselineManager()
    manager.record_baseline_from_run(run, config)
    return manager
