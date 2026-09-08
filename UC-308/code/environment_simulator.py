"""
UC-308 — Simulador de entorno externo (sandbox sin red, APIs ni archivos reales).

Ejecuta casos golden contra un entorno controlado y determinista.
Soporta múltiples escenarios de deriva para entrenar y evaluar detectores.
"""

from __future__ import annotations

import hashlib
import math
import random
import time
import uuid
from typing import Any, Dict, Optional

from models_308 import AgentResult, GoldenCase


class SimulatedExternalEnvironment:
    """
    Entorno externo simulado. No realiza llamadas de red ni acceso a disco.
    Cada caso se ejecuta con un RNG determinista derivado del caso + escenario,
    de modo que latencia, tokens y recursos sean reproducibles run a run.
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed if seed is not None else int(time.time() * 1000) % 2**31
        # RNG para ruido de distribución (debe variar entre corridas).
        self.rng = random.Random(self.seed)
        self.scenario = "healthy"
        self.scenario_params: Dict[str, Any] = {}
        self._execution_count = 0

    def _case_rng(self, case: GoldenCase) -> random.Random:
        """RNG base estable por semilla y caso, independiente del escenario."""
        material = f"{self.seed}:{case.id}".encode("utf-8")
        case_seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
        return random.Random(case_seed)

    def set_scenario(
        self,
        scenario: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Configura el escenario de deriva para las próximas ejecuciones."""
        self.scenario = scenario
        self.scenario_params = params or {}

    def reset(self, seed: Optional[int] = None) -> None:
        """Reinicia el entorno con una nueva semilla."""
        self.seed = seed if seed is not None else int(time.time() * 1000) % 2**31
        self.rng = random.Random(self.seed)
        self.scenario = "healthy"
        self.scenario_params = {}
        self._execution_count = 0

    def execute(self, case: GoldenCase) -> AgentResult:
        """Ejecuta un caso golden en el entorno simulado."""
        self._execution_count += 1
        trace_id = f"t-{uuid.uuid4().hex[:8]}"
        case_rng = self._case_rng(case)

        result = AgentResult(
            case_id=case.id,
            tool=case.tool,
            environment=case.environment,
            agent_version=case.agent_version,
            trace_id=trace_id,
            resource_usage={
                "cpu_ms": case_rng.uniform(10, 50),
                "memory_mb": case_rng.uniform(20, 80),
            },
            distribution_params=case.distribution_config,
            evidence={"scenario": self.scenario, "seed": self.seed},
        )

        if case.tool == "data_distribution":
            self._simulate_distribution_case(case, result, case_rng)
        elif case.tool == "api_call":
            self._simulate_api_call(case, result, case_rng)
        elif case.tool == "web_scrape":
            self._simulate_web_scrape(case, result, case_rng)
        elif case.tool == "db_query":
            self._simulate_db_query(case, result, case_rng)
        elif case.tool == "inventory_update":
            self._simulate_inventory_update(case, result, case_rng)
        else:
            self._simulate_generic(case, result, case_rng)

        # Aplicar escenarios transversales que pueden sobreescribir propiedades.
        self._apply_scenario_overrides(case, result, case_rng)

        # Latencia base (aleatoria pero reproducible por caso).
        latency_base = case_rng.uniform(80.0, 180.0)
        if result.timeout:
            result.latency_ms = latency_base + case_rng.uniform(5000.0, 10000.0)
        else:
            result.latency_ms = latency_base

        result.quality_score = self._compute_quality(result)
        return result

    # ------------------------------------------------------------------
    # Simuladores por tipo de herramienta
    # ------------------------------------------------------------------

    def _simulate_api_call(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        result.status = "success"
        result.success = True
        result.output = case.expected_output if case.expected_output is not None else {}
        result.schema_fingerprint = self._schema_fingerprint(result.output)
        result.tokens = rng.uniform(180, 320)
        result.steps = 1
        result.retries = 0
        result.escalations = 0
        result.uc300_blocks = 0
        result.uc290_overrides = 0

    def _simulate_web_scrape(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        result.status = "success"
        result.success = True
        result.output = {
            "html": '<div class="price">120.50</div><span class="stock">42</span>',
            "extracted": case.expected_output,
        }
        result.html_fingerprint = self._html_fingerprint(case.expected_html_selectors or [])
        result.schema_fingerprint = self._schema_fingerprint(result.output)
        result.tokens = rng.uniform(250, 450)
        result.steps = 2
        result.retries = 0
        result.escalations = 0
        result.uc300_blocks = 0
        result.uc290_overrides = 0

    def _simulate_db_query(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        result.status = "success"
        result.success = True
        result.output = case.expected_output if case.expected_output is not None else {}
        result.schema_fingerprint = self._schema_fingerprint(result.output)
        result.tokens = rng.uniform(120, 250)
        result.steps = 1
        result.retries = 0
        result.escalations = 0
        result.uc300_blocks = 0
        result.uc290_overrides = 0

    def _simulate_inventory_update(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        result.status = "success"
        result.success = True
        result.output = case.expected_output if case.expected_output is not None else {"status": "ok"}
        result.schema_fingerprint = self._schema_fingerprint(result.output)
        result.tokens = rng.uniform(150, 300)
        result.steps = 3
        result.retries = 0
        result.escalations = 0
        result.uc300_blocks = 0
        result.uc290_overrides = 0

    def _simulate_generic(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        result.status = "success"
        result.success = True
        result.output = case.expected_output
        result.schema_fingerprint = self._schema_fingerprint(result.output)
        result.tokens = rng.uniform(150, 300)
        result.steps = 1
        result.retries = 0
        result.escalations = 0
        result.uc300_blocks = 0
        result.uc290_overrides = 0

    def _simulate_distribution_case(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        config = case.distribution_config or {}
        dist_type = config.get("type", "numeric")

        if dist_type == "numeric":
            baseline_mean = config.get("baseline_mean", 100.0)
            baseline_std = config.get("baseline_std", 10.0)
            samples = 100
            result.data_samples = [
                rng.gauss(baseline_mean, baseline_std)
                for _ in range(samples)
            ]
            mean = sum(result.data_samples) / len(result.data_samples)
            variance = sum((x - mean) ** 2 for x in result.data_samples) / len(result.data_samples)
            std = math.sqrt(variance)
            result.output = {"mean": mean, "std": std, "samples": samples}
        elif dist_type == "categorical":
            categories = config.get("categories", ["a", "b", "c"])
            probs = config.get("baseline_probs", [1.0 / len(categories)] * len(categories))
            samples = 200
            result.category_counts = {}
            for _ in range(samples):
                cat = rng.choices(categories, weights=probs, k=1)[0]
                result.category_counts[cat] = result.category_counts.get(cat, 0) + 1
            dominant = max(result.category_counts, key=result.category_counts.get)
            result.output = {"dominant": dominant, "counts": result.category_counts}
        else:
            result.output = {"dominant": "unknown"}

        result.status = "success"
        result.success = True
        result.schema_fingerprint = self._schema_fingerprint(result.output)
        result.tokens = rng.uniform(80, 160)
        result.steps = 1
        result.retries = 0
        result.escalations = 0
        result.uc300_blocks = 0
        result.uc290_overrides = 0

    # ------------------------------------------------------------------
    # Escenarios de deriva
    # ------------------------------------------------------------------

    def _apply_scenario_overrides(
        self,
        case: GoldenCase,
        result: AgentResult,
        rng: random.Random,
    ) -> None:
        scenario = self.scenario
        params = self.scenario_params

        if scenario == "healthy":
            return

        if scenario == "api_schema_change" and case.tool == "api_call":
            original = result.output or {}
            drifted = {k: v for k, v in original.items() if k != "price"}
            drifted["current_cost"] = original.get("price", 0.0) * 1.05
            result.output = drifted
            result.schema_fingerprint = self._schema_fingerprint(drifted)
            result.success = False
            result.status = "schema_drift"
            result.error = "API schema drift: expected key 'price' missing, got 'current_cost'"

        if scenario == "html_selector_change" and case.tool == "web_scrape":
            html = '<div class="val">120.50</div><span class="avail">42</span>'
            result.output = {"html": html, "extracted": {}}
            result.html_fingerprint = self._html_fingerprint(["div.val", "span.avail"])
            result.success = False
            result.status = "selector_drift"
            result.error = "HTML selector drift: expected selectors not found"

        if scenario == "data_distribution_shift" and case.tool == "data_distribution":
            config = case.distribution_config or {}
            if config.get("type") == "numeric":
                shift = params.get("shift", 8.0)
                baseline_mean = config.get("baseline_mean", 100.0)
                baseline_std = config.get("baseline_std", 10.0)
                samples = 100
                result.data_samples = [
                    rng.gauss(baseline_mean + shift, baseline_std)
                    for _ in range(samples)
                ]
                mean = sum(result.data_samples) / len(result.data_samples)
                variance = sum((x - mean) ** 2 for x in result.data_samples) / len(result.data_samples)
                std = math.sqrt(variance)
                result.output = {"mean": mean, "std": std, "samples": samples}
            # La variable categórica no se altera para mantener tests estables.
            result.schema_fingerprint = self._schema_fingerprint(result.output)

        if scenario == "latency_regression":
            multiplier = params.get("multiplier", 3.0)
            result.latency_ms = result.latency_ms * multiplier + rng.uniform(50, 150)
            result.resource_usage["cpu_ms"] = result.resource_usage.get("cpu_ms", 30) * multiplier
            result.resource_usage["memory_mb"] = result.resource_usage.get("memory_mb", 50) * multiplier
            result.status = "slow"

        if scenario == "error_regression":
            fail_rate = params.get("fail_rate", 0.5)
            if rng.random() < fail_rate:
                result.success = False
                result.status = "error"
                result.error = f"Simulated error in {case.tool}"
                result.output = None
                result.schema_fingerprint = ""
                result.html_fingerprint = ""

        if scenario == "timeout_regression":
            timeout_rate = params.get("timeout_rate", 0.5)
            if rng.random() < timeout_rate:
                result.timeout = True
                result.success = False
                result.status = "timeout"
                result.error = "Simulated timeout"

        if scenario == "behavioral_regression" and case.tool == "inventory_update":
            result.steps = params.get("steps", 8)
            result.retries = params.get("retries", 4)
            result.escalations = params.get("escalations", 2)
            result.uc300_blocks = params.get("uc300_blocks", 1)
            result.uc290_overrides = params.get("uc290_overrides", 1)
            result.status = "success_with_escalation"

        if scenario == "quality_regression":
            if rng.random() < params.get("fail_rate", 0.4):
                result.success = False
                result.status = "quality_failure"
                result.error = "Simulated quality regression"
            result.quality_score = rng.uniform(0.3, 0.6)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_quality(self, result: AgentResult) -> float:
        if not result.success:
            return 0.0
        q = 1.0
        if result.timeout:
            q -= 0.5
        if result.retries:
            q -= min(result.retries * 0.1, 0.3)
        if result.escalations:
            q -= min(result.escalations * 0.15, 0.4)
        if result.uc300_blocks or result.uc290_overrides:
            q -= 0.2
        if result.latency_ms > 2000:
            q -= 0.2
        return max(0.0, min(1.0, q))

    @staticmethod
    def _schema_fingerprint(output: Any) -> str:
        if isinstance(output, dict):
            return ",".join(sorted(str(k) for k in output.keys()))
        return f"type:{type(output).__name__}"

    @staticmethod
    def _html_fingerprint(selectors: list) -> str:
        return ",".join(sorted(selectors))


if __name__ == "__main__":
    from golden_dataset import build_default_golden_dataset

    ds = build_default_golden_dataset()
    env = SimulatedExternalEnvironment(seed=42)
    print("HEALTHY RUN")
    for case in ds.cases:
        r = env.execute(case)
        print(f"{case.id}: success={r.success} status={r.status} latency={r.latency_ms:.1f}ms")

    print("\nAPI SCHEMA DRIFT RUN")
    env.reset(seed=42)
    env.set_scenario("api_schema_change")
    for case in ds.cases:
        r = env.execute(case)
        if case.tool == "api_call":
            print(f"{case.id}: success={r.success} error={r.error[:60]}")
