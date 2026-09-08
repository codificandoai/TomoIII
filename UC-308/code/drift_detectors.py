"""
UC-308 — Detectores de deriva.

Cada detector compara una dimensión de los resultados de una evaluación contra
su baseline. Soporta comparación absoluta y relativa, y emite señales con estado
normal/warning/degraded/critical.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _ks_2sample_statistic(sample1: List[float], sample2: List[float]) -> float:
    """Estadístico D de Kolmogorov-Smirnov two-sample."""
    if not sample1 or not sample2:
        return 0.0
    n1 = len(sample1)
    n2 = len(sample2)
    all_values = sorted(set(sample1) | set(sample2))
    diffs = []
    for v in all_values:
        cdf1 = sum(1 for x in sample1 if x <= v) / n1
        cdf2 = sum(1 for x in sample2 if x <= v) / n2
        diffs.append(abs(cdf1 - cdf2))
    return max(diffs) if diffs else 0.0


def _cramer_von_mises_2sample(sample1: List[float], sample2: List[float]) -> float:
    """Estadístico T de Cramér-von Mises two-sample (versión simplificada)."""
    if not sample1 or not sample2:
        return 0.0
    n1 = len(sample1)
    n2 = len(sample2)
    all_values = sorted(set(sample1) | set(sample2))
    t = 0.0
    for v in all_values:
        cdf1 = sum(1 for x in sample1 if x <= v) / n1
        cdf2 = sum(1 for x in sample2 if x <= v) / n2
        t += (cdf1 - cdf2) ** 2
    return t

from models_308 import (
    AgentResult,
    Baseline,
    DriftSignal,
    DriftStatus,
    DriftType,
    EvaluationRun,
    DriftConfig,
)


def _status_from_thresholds(
    value: float,
    warning: float,
    degraded: float,
    critical: float,
    higher_is_worse: bool = True,
) -> DriftStatus:
    """Devuelve el estado comparando value contra umbrales absolutos."""
    if higher_is_worse:
        if value >= critical:
            return DriftStatus.CRITICAL
        if value >= degraded:
            return DriftStatus.DEGRADED
        if value >= warning:
            return DriftStatus.WARNING
        return DriftStatus.NORMAL
    else:
        if value <= critical:
            return DriftStatus.CRITICAL
        if value <= degraded:
            return DriftStatus.DEGRADED
        if value <= warning:
            return DriftStatus.WARNING
        return DriftStatus.NORMAL


def _relative_delta(current: float, baseline: float) -> float:
    if baseline == 0:
        return float("inf") if current > 0 else 0.0
    return (current - baseline) / baseline


def _aggregate_results(results: Sequence[AgentResult]) -> Dict[str, Any]:
    """Calcula métricas agregadas de una lista de resultados."""
    n = len(results)
    if n == 0:
        return {
            "count": 0,
            "success_rate": 0.0,
            "quality_score": 0.0,
            "error_rate": 0.0,
            "timeout_rate": 0.0,
            "latency_ms_mean": 0.0,
            "latency_ms_p95": 0.0,
            "tokens_mean": 0.0,
            "avg_steps": 0.0,
            "avg_retries": 0.0,
            "escalation_rate": 0.0,
            "uc300_block_rate": 0.0,
            "uc290_override_rate": 0.0,
            "resource_mean": {},
            "data_samples": [],
            "category_counts": defaultdict(int),
        }

    success = sum(1 for r in results if r.success)
    error = sum(1 for r in results if not r.success and not r.timeout)
    timeouts = sum(1 for r in results if r.timeout)
    latencies = sorted(r.latency_ms for r in results)
    p95_index = max(0, int(math.ceil(n * 0.95)) - 1)

    resource_sums: Dict[str, float] = defaultdict(float)
    resource_counts: Dict[str, int] = defaultdict(int)
    for r in results:
        for k, v in r.resource_usage.items():
            resource_sums[k] += v
            resource_counts[k] += 1

    all_samples: List[float] = []
    category_counts: Dict[str, int] = defaultdict(int)
    for r in results:
        if r.data_samples:
            all_samples.extend(r.data_samples)
        if r.category_counts:
            for cat, cnt in r.category_counts.items():
                category_counts[cat] += cnt

    return {
        "count": n,
        "success_rate": success / n,
        "quality_score": sum(r.quality_score for r in results) / n,
        "error_rate": error / n,
        "timeout_rate": timeouts / n,
        "latency_ms_mean": sum(r.latency_ms for r in results) / n,
        "latency_ms_p95": latencies[p95_index],
        "tokens_mean": sum(r.tokens for r in results) / n,
        "avg_steps": sum(r.steps for r in results) / n,
        "avg_retries": sum(r.retries for r in results) / n,
        "escalation_rate": sum(r.escalations for r in results) / n,
        "uc300_block_rate": sum(r.uc300_blocks for r in results) / n,
        "uc290_override_rate": sum(r.uc290_overrides for r in results) / n,
        "resource_mean": {k: resource_sums[k] / resource_counts[k] for k in resource_sums},
        "data_samples": all_samples,
        "category_counts": dict(category_counts),
    }


def _group_results_by_tool(
    results: Sequence[AgentResult],
) -> Dict[str, List[AgentResult]]:
    groups: Dict[str, List[AgentResult]] = defaultdict(list)
    for r in results:
        groups[r.tool].append(r)
    return groups


# ---------------------------------------------------------------------------
# PSI / Jensen-Shannon helpers
# ---------------------------------------------------------------------------

def _psi(expected: List[float], actual: List[float], bins: int = 10) -> float:
    """Population Stability Index entre dos muestras numéricas.

    Usa bordes fijos derivados únicamente de la distribución baseline
    (mean +/- 3 sigma) para que el PSI sea estable ante outliers.
    """
    if not expected or not actual:
        return 0.0
    n = len(expected)
    mean = sum(expected) / n
    variance = sum((x - mean) ** 2 for x in expected) / n
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    min_v = mean - 3 * std
    max_v = mean + 3 * std
    bucket_size = (max_v - min_v) / bins
    if bucket_size == 0:
        return 0.0

    def _proportions(samples: List[float]) -> List[float]:
        counts = [0] * bins
        for s in samples:
            idx = int((s - min_v) / bucket_size)
            if idx < 0:
                idx = 0
            elif idx >= bins:
                idx = bins - 1
            counts[idx] += 1
        total = sum(counts)
        if total == 0:
            return [0.0] * bins
        return [max(c / total, 1e-6) for c in counts]

    e = _proportions(expected)
    a = _proportions(actual)
    psi = 0.0
    for ei, ai in zip(e, a):
        psi += (ai - ei) * math.log(ai / ei)
    return psi


def _js_divergence(p: List[float], q: List[float]) -> float:
    """Jensen-Shannon divergence entre dos distribuciones de igual longitud."""
    if not p or not q or len(p) != len(q):
        return 0.0
    p = [max(x, 1e-9) for x in p]
    q = [max(x, 1e-9) for x in q]
    sp = sum(p)
    sq = sum(q)
    p = [x / sp for x in p]
    q = [x / sq for x in q]
    m = [(pi + qi) / 2.0 for pi, qi in zip(p, q)]
    return (_kl(p, m) + _kl(q, m)) / 2.0


def _kl(p: List[float], q: List[float]) -> float:
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)


def _categorical_psi(
    baseline_counts: Dict[str, int],
    actual_counts: Dict[str, int],
) -> Tuple[float, List[str]]:
    """PSI para variables categóricas."""
    categories = set(baseline_counts.keys()) | set(actual_counts.keys())
    total_b = sum(baseline_counts.values())
    total_a = sum(actual_counts.values())
    if total_b == 0 or total_a == 0:
        return 0.0, []

    psi = 0.0
    drifted: List[str] = []
    for cat in categories:
        e = max(baseline_counts.get(cat, 0) / total_b, 1e-6)
        a = max(actual_counts.get(cat, 0) / total_a, 1e-6)
        psi += (a - e) * math.log(a / e)
        # Si cambia más de un 100% relativo en proporción, marcar categoría.
        if abs(a - e) > 0.05:
            drifted.append(cat)
    return psi, drifted


# ---------------------------------------------------------------------------
# Detectores
# ---------------------------------------------------------------------------

class QualityDriftDetector:
    """Compara tasa de éxito y quality score contra baseline."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline:
                continue
            agg = _aggregate_results(results)
            success_rate = agg["success_rate"]
            quality_score = agg["quality_score"]

            # Success rate
            abs_delta = baseline.metrics.success_rate - success_rate
            rel_delta = _relative_delta(success_rate, baseline.metrics.success_rate)
            status = _status_from_thresholds(
                1.0 - success_rate,  # cuanto más baja, peor
                1.0 - config.success_rate_warning,
                1.0 - config.success_rate_degraded,
                1.0 - config.success_rate_critical,
                higher_is_worse=True,
            )
            if status != DriftStatus.NORMAL:
                signals.append(DriftSignal(
                    run_id=run.run_id,
                    drift_type=DriftType.QUALITY,
                    tool=tool,
                    status=status,
                    score=1.0 - success_rate,
                    absolute_delta=abs_delta,
                    relative_delta=rel_delta,
                    baseline_id=baseline.baseline_id,
                    dimension="success_rate",
                    message=(
                        f"Success rate for {tool} is {success_rate:.2%} "
                        f"(baseline {baseline.metrics.success_rate:.2%}); "
                        f"relative drop {abs(rel_delta):.2%}"
                    ),
                    evidence={"success_rate": success_rate, "baseline": baseline.metrics.success_rate, "tool": tool},
                ))

            # Quality score
            abs_delta_q = baseline.metrics.quality_score - quality_score
            rel_delta_q = _relative_delta(quality_score, baseline.metrics.quality_score)
            status_q = _status_from_thresholds(
                1.0 - quality_score,
                1.0 - config.quality_score_warning,
                1.0 - config.quality_score_degraded,
                1.0,  # critical cuando cae muy bajo
                higher_is_worse=True,
            )
            if status_q != DriftStatus.NORMAL:
                signals.append(DriftSignal(
                    run_id=run.run_id,
                    drift_type=DriftType.QUALITY,
                    tool=tool,
                    status=status_q,
                    score=1.0 - quality_score,
                    absolute_delta=abs_delta_q,
                    relative_delta=rel_delta_q,
                    baseline_id=baseline.baseline_id,
                    dimension="quality_score",
                    message=(
                        f"Quality score for {tool} is {quality_score:.2f} "
                        f"(baseline {baseline.metrics.quality_score:.2f})"
                    ),
                    evidence={"quality_score": quality_score, "baseline": baseline.metrics.quality_score, "tool": tool},
                ))
        return signals


class ToolOperationalDriftDetector:
    """Compara latencia, errores, timeouts y consumo de recursos."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline:
                continue
            agg = _aggregate_results(results)

            # Error rate
            er = agg["error_rate"]
            er_abs = er - baseline.metrics.error_rate
            er_rel = _relative_delta(er, baseline.metrics.error_rate)
            er_status = _status_from_thresholds(
                er,
                config.error_rate_warning,
                config.error_rate_degraded,
                config.error_rate_critical,
                higher_is_worse=True,
            )
            if er_status != DriftStatus.NORMAL:
                signals.append(DriftSignal(
                    run_id=run.run_id,
                    drift_type=DriftType.TOOL_OPERATIONAL,
                    tool=tool,
                    status=er_status,
                    score=er,
                    absolute_delta=er_abs,
                    relative_delta=er_rel,
                    baseline_id=baseline.baseline_id,
                    dimension="error_rate",
                    message=f"Error rate for {tool} is {er:.2%} (baseline {baseline.metrics.error_rate:.2%})",
                    evidence={"error_rate": er, "baseline": baseline.metrics.error_rate, "tool": tool},
                ))

            # Timeout rate
            tr = agg["timeout_rate"]
            tr_abs = tr - baseline.metrics.timeout_rate
            tr_rel = _relative_delta(tr, baseline.metrics.timeout_rate)
            tr_status = _status_from_thresholds(
                tr,
                config.timeout_rate_warning,
                config.timeout_rate_degraded,
                config.timeout_rate_degraded,  # usamos degraded como critical
                higher_is_worse=True,
            )
            if tr_status != DriftStatus.NORMAL:
                signals.append(DriftSignal(
                    run_id=run.run_id,
                    drift_type=DriftType.TOOL_OPERATIONAL,
                    tool=tool,
                    status=tr_status,
                    score=tr,
                    absolute_delta=tr_abs,
                    relative_delta=tr_rel,
                    baseline_id=baseline.baseline_id,
                    dimension="timeout_rate",
                    message=f"Timeout rate for {tool} is {tr:.2%} (baseline {baseline.metrics.timeout_rate:.2%})",
                    evidence={"timeout_rate": tr, "baseline": baseline.metrics.timeout_rate, "tool": tool},
                ))

            # Latency mean
            lat = agg["latency_ms_mean"]
            lat_base = baseline.metrics.latency_ms_mean
            if lat_base > 0:
                lat_rel = _relative_delta(lat, lat_base)
                status = self._latency_status(lat_rel, config)
                if status != DriftStatus.NORMAL:
                    signals.append(DriftSignal(
                        run_id=run.run_id,
                        drift_type=DriftType.TOOL_OPERATIONAL,
                        tool=tool,
                        status=status,
                        score=min(abs(lat_rel), 10.0),
                        absolute_delta=lat - lat_base,
                        relative_delta=lat_rel,
                        baseline_id=baseline.baseline_id,
                        dimension="latency_ms_mean",
                        message=(
                            f"Mean latency for {tool} is {lat:.1f}ms "
                            f"(baseline {lat_base:.1f}ms, +{lat_rel:.2%})"
                        ),
                        evidence={"latency_ms_mean": lat, "baseline": lat_base, "tool": tool},
                    ))

            # Resource usage
            for resource, current in agg["resource_mean"].items():
                base = baseline.metrics.resource_mean.get(resource)
                if not base:
                    continue
                rel = _relative_delta(current, base)
                status = _status_from_thresholds(
                    rel,
                    config.resource_relative_warning,
                    config.resource_relative_degraded,
                    config.resource_relative_degraded,
                    higher_is_worse=True,
                )
                if status != DriftStatus.NORMAL:
                    signals.append(DriftSignal(
                        run_id=run.run_id,
                        drift_type=DriftType.TOOL_OPERATIONAL,
                        tool=tool,
                        status=status,
                        score=min(abs(rel), 10.0),
                        absolute_delta=current - base,
                        relative_delta=rel,
                        baseline_id=baseline.baseline_id,
                        dimension=f"resource_{resource}",
                        message=(
                            f"Resource {resource} for {tool} is {current:.1f} "
                            f"(baseline {base:.1f}, +{rel:.2%})"
                        ),
                        evidence={"resource": resource, "current": current, "baseline": base, "tool": tool},
                    ))
        return signals

    def _latency_status(self, relative: float, config: DriftConfig) -> DriftStatus:
        if relative >= config.latency_relative_critical:
            return DriftStatus.CRITICAL
        if relative >= config.latency_relative_degraded:
            return DriftStatus.DEGRADED
        if relative >= config.latency_relative_warning:
            return DriftStatus.WARNING
        return DriftStatus.NORMAL


class APIContractDriftDetector:
    """Detecta cambios en el contrato / esquema de respuesta de APIs."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            if tool not in ("api_call", "db_query"):
                continue
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline or not baseline.metrics.schema_fingerprints:
                continue

            base_fps = baseline.metrics.schema_fingerprints
            base_fps_set = set(base_fps)
            mismatched = [r for r in results if r.schema_fingerprint and r.schema_fingerprint not in base_fps_set]
            total = len(results)
            if total == 0:
                continue
            ratio = len(mismatched) / total
            if ratio == 0:
                continue

            all_base_keys: set = set()
            for fp in base_fps:
                all_base_keys.update(fp.split(","))

            missing_keys: set = set()
            for r in mismatched:
                actual_keys = set(r.schema_fingerprint.split(","))
                missing_keys.update(all_base_keys - actual_keys)

            status = DriftStatus.WARNING
            if len(missing_keys) >= config.schema_drift_missing_keys_degraded:
                status = DriftStatus.DEGRADED
            elif len(missing_keys) >= config.schema_drift_missing_keys_warning:
                status = DriftStatus.WARNING
            if ratio >= 0.5:
                status = max(status, DriftStatus.DEGRADED, key=lambda s: ["normal", "warning", "degraded", "critical"].index(s.value))

            signals.append(DriftSignal(
                run_id=run.run_id,
                drift_type=DriftType.CONTRACT_API,
                tool=tool,
                status=status,
                score=ratio,
                absolute_delta=len(missing_keys),
                relative_delta=ratio,
                baseline_id=baseline.baseline_id,
                dimension="schema_fingerprint",
                message=(
                    f"API contract drift in {tool}: {len(mismatched)}/{total} responses "
                    f"changed schema; missing keys: {sorted(missing_keys)}"
                ),
                evidence={
                    "baseline_fingerprints": base_fps,
                    "tool": tool,
                    "mismatched": [r.case_id for r in mismatched],
                    "missing_keys": sorted(missing_keys),
                },
            ))
        return signals


class HTMLInterfaceDriftDetector:
    """Detecta cambios en selectores HTML / interfaz web."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            if tool != "web_scrape":
                continue
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline or not baseline.metrics.html_selector_fingerprints:
                continue

            base_fps = baseline.metrics.html_selector_fingerprints
            base_fps_set = set(base_fps)
            all_base_selectors: set = set()
            for fp in base_fps:
                all_base_selectors.update(fp.split(","))

            mismatched = [r for r in results if r.html_fingerprint and r.html_fingerprint not in base_fps_set]
            total = len(results)
            if total == 0:
                continue
            ratio = len(mismatched) / total
            if ratio == 0:
                continue

            missing = set()
            for r in mismatched:
                missing.update(all_base_selectors - set(r.html_fingerprint.split(",")))

            status = DriftStatus.WARNING
            if len(missing) >= config.html_selector_missing_degraded:
                status = DriftStatus.DEGRADED
            elif len(missing) >= config.html_selector_missing_warning:
                status = DriftStatus.WARNING

            signals.append(DriftSignal(
                run_id=run.run_id,
                drift_type=DriftType.HTML_INTERFACE,
                tool=tool,
                status=status,
                score=ratio,
                absolute_delta=len(missing),
                relative_delta=ratio,
                baseline_id=baseline.baseline_id,
                dimension="html_selector_fingerprint",
                message=(
                    f"HTML interface drift in {tool}: {len(mismatched)}/{total} pages "
                    f"changed selectors; missing: {sorted(missing)}"
                ),
                evidence={
                    "baseline_fingerprints": base_fps,
                    "tool": tool,
                    "mismatched": [r.case_id for r in mismatched],
                    "missing_selectors": sorted(missing),
                },
            ))
        return signals


class DataDistributionDriftDetector:
    """Detecta cambios en distribuciones de datos (PSI / JS)."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            if tool != "data_distribution":
                continue
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline or not baseline.metrics.distribution:
                continue

            agg = _aggregate_results(results)
            dist_params = baseline.metrics.distribution.get("params")

            current_samples = agg["data_samples"]
            base_samples = baseline.metrics.distribution.get("samples")
            if dist_params and dist_params.get("type") == "numeric":
                rng = random.Random(12345)
                base_mean_param = dist_params.get("baseline_mean", 100.0)
                base_std_param = dist_params.get("baseline_std", 10.0)
                base_samples = [rng.gauss(base_mean_param, base_std_param) for _ in range(1000)]

            if base_samples and current_samples:
                psi_value = _psi(base_samples, current_samples, bins=10)
                current_mean = sum(current_samples) / len(current_samples)
                base_mean = sum(base_samples) / len(base_samples)
                base_std = dist_params.get("baseline_std") if dist_params else None
                if base_std is None:
                    n = len(base_samples)
                    base_std = (sum((x - base_mean) ** 2 for x in base_samples) / n) ** 0.5
                mean_shift_z = abs(current_mean - base_mean) / max(base_std, 1e-9)

                # El score principal es el desplazamiento de media normalizado
                # (estable ante muestreo); PSI se reporta como evidencia adicional.
                status = _status_from_thresholds(
                    mean_shift_z,
                    config.psi_warning,
                    config.psi_degraded,
                    config.psi_degraded * 2,
                    higher_is_worse=True,
                )
                if status != DriftStatus.NORMAL:
                    signals.append(DriftSignal(
                        run_id=run.run_id,
                        drift_type=DriftType.DATA_DISTRIBUTION,
                        tool=tool,
                        status=status,
                        score=mean_shift_z,
                        absolute_delta=current_mean - base_mean,
                        relative_delta=_relative_delta(current_mean, base_mean),
                        baseline_id=baseline.baseline_id,
                        dimension="numeric_distribution",
                        message=(
                            f"Numeric distribution drift in {tool}: z={mean_shift_z:.3f}, "
                            f"PSI={psi_value:.3f} (mean {current_mean:.2f} vs baseline {base_mean:.2f})"
                        ),
                        evidence={
                            "psi": psi_value,
                            "mean_shift_z": mean_shift_z,
                            "current_mean": current_mean,
                            "baseline_mean": base_mean,
                            "baseline_std": base_std,
                            "tool": tool,
                        },
                    ))

            current_counts = agg["category_counts"]
            base_counts = baseline.metrics.distribution.get("category_counts")
            if dist_params and dist_params.get("type") == "categorical":
                rng = random.Random(12345)
                categories = dist_params.get("categories", [])
                probs = dist_params.get("baseline_probs", [])
                if categories and probs:
                    base_counts = {}
                    for _ in range(1000):
                        cat = rng.choices(categories, weights=probs, k=1)[0]
                        base_counts[cat] = base_counts.get(cat, 0) + 1

            if base_counts and current_counts:
                psi_value, drifted = _categorical_psi(base_counts, current_counts)
                status = _status_from_thresholds(
                    psi_value,
                    config.psi_warning,
                    config.psi_degraded,
                    config.psi_degraded * 2,
                    higher_is_worse=True,
                )
                if status != DriftStatus.NORMAL:
                    signals.append(DriftSignal(
                        run_id=run.run_id,
                        drift_type=DriftType.DATA_DISTRIBUTION,
                        tool=tool,
                        status=status,
                        score=psi_value,
                        absolute_delta=0.0,
                        relative_delta=0.0,
                        baseline_id=baseline.baseline_id,
                        dimension="categorical_distribution",
                        message=(
                            f"Categorical distribution drift in {tool}: PSI={psi_value:.3f}; "
                            f"changed categories: {drifted}"
                        ),
                        evidence={
                            "psi": psi_value,
                            "baseline_counts": base_counts,
                            "current_counts": current_counts,
                            "drifted_categories": drifted,
                            "tool": tool,
                        },
                    ))
        return signals


class BehavioralDriftDetector:
    """Detecta cambios en comportamiento del agente: pasos, reintentos, escalaciones."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)
        for tool, results in groups.items():
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline or not baseline.metrics.behavior:
                continue
            agg = _aggregate_results(results)
            b = baseline.metrics.behavior

            dims = [
                ("avg_steps", agg["avg_steps"]),
                ("avg_retries", agg["avg_retries"]),
                ("escalation_rate", agg["escalation_rate"]),
                ("uc300_block_rate", agg["uc300_block_rate"]),
                ("uc290_override_rate", agg["uc290_override_rate"]),
            ]

            for dim, current in dims:
                base = b.get(dim)
                if base is None:
                    continue
                rel = _relative_delta(current, base)
                # Cuando el baseline es 0, usar delta absoluto para evitar ratios infinitos.
                if base == 0:
                    status = _status_from_thresholds(
                        current,
                        config.behavioral_relative_warning,
                        config.behavioral_relative_degraded,
                        config.behavioral_relative_degraded,
                        higher_is_worse=True,
                    )
                    rel = float("inf") if current > 0 else 0.0
                else:
                    status = _status_from_thresholds(
                        rel,
                        config.behavioral_relative_warning,
                        config.behavioral_relative_degraded,
                        config.behavioral_relative_degraded,
                        higher_is_worse=True,
                    )
                if status != DriftStatus.NORMAL:
                    rel_str = f"{rel:.2%}" if rel != float("inf") else "inf"
                    signals.append(DriftSignal(
                        run_id=run.run_id,
                        drift_type=DriftType.BEHAVIORAL,
                        tool=tool,
                        status=status,
                        score=min(abs(rel), 10.0),
                        absolute_delta=current - base,
                        relative_delta=rel,
                        baseline_id=baseline.baseline_id,
                        dimension=dim,
                        message=(
                            f"Behavioral drift in {tool}: {dim}={current:.3f} "
                            f"(baseline {base:.3f}, +{rel_str})"
                        ),
                        evidence={"dimension": dim, "current": current, "baseline": base, "tool": tool},
                    ))
        return signals


# ---------------------------------------------------------------------------
# Fábrica
# ---------------------------------------------------------------------------

class ConceptDriftDetector:
    """Detecta deriva conceptual usando KS/CvM sobre predicciones del modelo."""

    def detect(
        self,
        run: EvaluationRun,
        baselines: Dict[Tuple[str, str, str, str], Baseline],
        config: DriftConfig,
    ) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        groups = _group_results_by_tool(run.results)

        for tool, results in groups.items():
            key = (run.agent_id, tool, run.environment, run.agent_version)
            baseline = baselines.get(key)
            if not baseline:
                continue

            current_scores: List[float] = []
            for r in results:
                scores = (r.evidence or {}).get("prediction_scores")
                if scores:
                    current_scores.extend(float(s) for s in scores)

            if not current_scores:
                continue

            base_scores = (baseline.metrics.distribution or {}).get("concept_predictions")
            if not base_scores:
                base_scores = (baseline.metrics.behavior or {}).get("concept_predictions")
            if not base_scores:
                continue

            base_scores = [float(s) for s in base_scores]
            ks_stat = _ks_2sample_statistic(base_scores, current_scores)
            cvm_stat = _cramer_von_mises_2sample(base_scores, current_scores)

            # Umbralas: KS D > warning/degraded/critical
            status = _status_from_thresholds(
                ks_stat,
                config.concept_drift_warning,
                config.concept_drift_degraded,
                config.concept_drift_critical,
                higher_is_worse=True,
            )
            if status != DriftStatus.NORMAL:
                n_base = len(base_scores)
                n_current = len(current_scores)
                base_mean = sum(base_scores) / n_base
                current_mean = sum(current_scores) / n_current
                signals.append(DriftSignal(
                    run_id=run.run_id,
                    drift_type=DriftType.CONCEPT,
                    tool=tool,
                    status=status,
                    score=ks_stat,
                    absolute_delta=current_mean - base_mean,
                    relative_delta=_relative_delta(current_mean, base_mean),
                    baseline_id=baseline.baseline_id,
                    dimension="prediction_distribution",
                    message=(
                        f"Concept drift in {tool}: KS D={ks_stat:.3f}, "
                        f"CvM T={cvm_stat:.3f} "
                        f"(n_base={n_base}, n_current={n_current}, "
                        f"mean {current_mean:.3f} vs {base_mean:.3f})"
                    ),
                    evidence={
                        "ks_statistic": ks_stat,
                        "cvm_statistic": cvm_stat,
                        "base_count": n_base,
                        "current_count": n_current,
                        "base_mean": base_mean,
                        "current_mean": current_mean,
                        "tool": tool,
                    },
                ))
        return signals


ALL_DETECTORS = [
    QualityDriftDetector(),
    ToolOperationalDriftDetector(),
    APIContractDriftDetector(),
    HTMLInterfaceDriftDetector(),
    DataDistributionDriftDetector(),
    BehavioralDriftDetector(),
    ConceptDriftDetector(),
]
