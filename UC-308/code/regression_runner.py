"""
UC-308 — Regression runner del golden dataset.

Ejecuta los casos golden de forma secuencial en un entorno simulado y
registra métricas en el observability manager. No utiliza red, APIs ni
archivos reales.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import GoldenDataset
from models_308 import AgentResult, DriftConfig, EvaluationRun
from observability_308 import ObservabilityManager


class RegressionRunner:
    """Ejecuta el golden dataset y produce una EvaluationRun reproducible."""

    def __init__(self, observability: ObservabilityManager):
        self.observability = observability

    def run_evaluation(
        self,
        dataset: GoldenDataset,
        environment: SimulatedExternalEnvironment,
        config: DriftConfig,
        trigger: str = "manual",
    ) -> EvaluationRun:
        start = time.time()
        run = EvaluationRun(
            trigger=trigger,
            dataset_version=dataset.version,
            dataset_hash=dataset.compute_hash(),
            agent_id=config.agent_id,
            environment=config.environment,
            agent_version=config.agent_version,
            evidence={"seed": environment.seed, "scenario": environment.scenario},
        )

        self.observability.increment("uc308_eval_runs_total", 1, {"trigger": trigger})

        results: List[AgentResult] = []
        for case in dataset.cases:
            result = environment.execute(case)
            results.append(result)
            self.observability.increment(
                "uc308_task_results_total",
                1,
                {"tool": result.tool, "status": result.status},
            )
            self.observability.observe_histogram(
                "uc308_latency_seconds",
                result.latency_ms / 1000.0,
                {"tool": result.tool},
            )
            self.observability.increment(
                "uc308_tokens_total",
                result.tokens,
                {"tool": result.tool},
            )
            for resource, value in result.resource_usage.items():
                self.observability.increment(
                    "uc308_resource_usage_total",
                    value,
                    {"tool": result.tool, "resource": resource},
                )

        run.results = results
        run.aggregate = self._aggregate(results)
        run.duration_ms = (time.time() - start) * 1000

        # Métricas globales
        self.observability.gauge(
            "uc308_success_rate",
            run.aggregate["success_rate"],
            {
                "agent_id": config.agent_id,
                "environment": config.environment,
                "version": config.agent_version,
            },
        )
        self.observability.gauge(
            "uc308_quality_score",
            run.aggregate["quality_score"],
            {
                "agent_id": config.agent_id,
                "environment": config.environment,
                "version": config.agent_version,
            },
        )
        self.observability.gauge(
            "uc308_run_status",
            0,  # se actualizará tras detección de deriva
            {
                "agent_id": config.agent_id,
                "environment": config.environment,
                "version": config.agent_version,
            },
        )

        return run

    @staticmethod
    def _aggregate(results: List[AgentResult]) -> Dict[str, Any]:
        n = len(results)
        if n == 0:
            return {
                "count": 0,
                "success_rate": 0.0,
                "quality_score": 0.0,
                "error_rate": 0.0,
                "timeout_rate": 0.0,
                "avg_latency_ms": 0.0,
                "total_tokens": 0.0,
                "avg_steps": 0.0,
                "avg_retries": 0.0,
                "avg_escalations": 0.0,
                "uc300_block_total": 0,
                "uc290_override_total": 0,
            }
        success = sum(1 for r in results if r.success)
        errors = sum(1 for r in results if not r.success and not r.timeout)
        timeouts = sum(1 for r in results if r.timeout)
        return {
            "count": n,
            "success_rate": success / n,
            "quality_score": sum(r.quality_score for r in results) / n,
            "error_rate": errors / n,
            "timeout_rate": timeouts / n,
            "avg_latency_ms": sum(r.latency_ms for r in results) / n,
            "total_tokens": sum(r.tokens for r in results),
            "avg_steps": sum(r.steps for r in results) / n,
            "avg_retries": sum(r.retries for r in results) / n,
            "avg_escalations": sum(r.escalations for r in results) / n,
            "uc300_block_total": sum(r.uc300_blocks for r in results),
            "uc290_override_total": sum(r.uc290_overrides for r in results),
        }
