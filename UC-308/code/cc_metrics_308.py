"""
UC-308 — Champion/Challenger metrics and statistical promotion criteria.

All calculations use the Python stdlib only. Divide-by-zero is guarded.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cc_models_308 import MarketEvent, PaperFill, Prediction, StageMetrics


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b and not math.isnan(b) else default


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _max_drawdown(equity: List[float]) -> float:
    peak = 0.0
    dd = 0.0
    for val in equity:
        peak = max(peak, val)
        if peak > 0:
            dd = max(dd, (peak - val) / peak)
    return dd


class StageMetricsCalculator:
    """Compute prediction + execution + risk metrics for one model/stage."""

    def compute(
        self,
        stage: str,
        records: Sequence[Dict[str, Any]],
    ) -> StageMetrics:
        """
        records: list of {
            "event": MarketEvent,
            "prediction": Prediction,
            "snapshot": PortfolioSnapshot dict,
            "fills": list[PaperFill dict],
        }
        """
        n = len(records)
        if n == 0:
            return StageMetrics(stage=stage, sample_count=0)

        bid_errors: List[float] = []
        ask_errors: List[float] = []
        mid_hits = 0
        dir_hits = 0
        dir_count = 0
        brier_scores: List[float] = []

        previous_mid: Optional[float] = None
        for r in records:
            event = r["event"]
            pred = r["prediction"]
            bid_errors.append(abs(pred.predicted_bid - event.reference_bid))
            ask_errors.append(abs(pred.predicted_ask - event.reference_ask))

            pred_mid = (pred.predicted_bid + pred.predicted_ask) / 2.0
            ref_mid = (event.reference_bid + event.reference_ask) / 2.0
            current_mid = event.mid
            tolerance = event.spread / 2.0 if event.spread > 0 else current_mid * 0.0001
            if abs(pred_mid - ref_mid) <= tolerance:
                mid_hits += 1

            if previous_mid is not None and current_mid != previous_mid:
                predicted_change = pred_mid - current_mid
                actual_change = ref_mid - previous_mid
                if (predicted_change > 0 and actual_change > 0) or (predicted_change < 0 and actual_change < 0):
                    dir_hits += 1
                dir_count += 1
                if pred.confidence is not None:
                    correct = 1.0 if ((predicted_change > 0 and actual_change > 0) or (predicted_change < 0 and actual_change < 0)) else 0.0
                    brier_scores.append((pred.confidence - correct) ** 2)
            previous_mid = current_mid

        fills: List[Dict[str, Any]] = []
        for r in records:
            fills.extend(r.get("fills", []))

        total_intended_qty = 0.0
        total_filled_qty = 0.0
        total_slippage_qty = 0.0
        slippage_weighted = 0.0
        shortfall_weighted = 0.0
        spread_capture_weighted = 0.0
        total_latency = 0.0
        event_by_fill = {
            fill["fill_id"]: record["event"]
            for record in records
            for fill in record.get("fills", [])
        }
        for f in fills:
            qty = f["quantity"]
            side = f["side"]
            total_filled_qty += qty
            total_latency += f["latency_ms"]
            slippage_weighted += f["slippage"] * qty
            total_slippage_qty += qty
            price = f["price"]
            expected = f["expected_price"]
            if side == "buy":
                shortfall_weighted += (price - expected) * qty
            else:
                shortfall_weighted += (expected - price) * qty
            event = event_by_fill.get(f["fill_id"])
            if event is not None:
                reference_mid = (event.reference_bid + event.reference_ask) / 2.0
                spread_capture_weighted += (
                    (reference_mid - price) if side == "buy" else (price - reference_mid)
                ) * qty
        for r in records:
            order = r.get("order")
            if order:
                total_intended_qty += order.get("quantity", 0.0)

        snapshots = [r["snapshot"] for r in records if r.get("snapshot")]
        equity = [s["market_value"] for s in snapshots]
        exposures = [s["exposure"] for s in snapshots]
        returns: List[float] = []
        for i in range(1, len(equity)):
            prev = equity[i - 1]
            if prev > 0:
                returns.append((equity[i] - prev) / prev)

        total_fees = sum(s["realized_pnl"] for s in snapshots) * 0.0
        # fees are not carried on snapshot; we use latest total_pnl and sum fills.
        total_fees = sum(f["fee"] for f in fills)
        total_pnl = snapshots[-1]["total_pnl"] if snapshots else 0.0
        max_dd = _max_drawdown(equity) if equity else 0.0
        avg_exposure = _mean(exposures) if exposures else 0.0

        fill_ratio = _safe_div(total_filled_qty, total_intended_qty, 0.0)
        avg_slippage = _safe_div(slippage_weighted, total_slippage_qty, 0.0)
        implementation_shortfall = _safe_div(shortfall_weighted, total_slippage_qty, 0.0)
        spread_capture = _safe_div(spread_capture_weighted, total_slippage_qty, 0.0)
        avg_latency = _safe_div(total_latency, len(fills), 0.0) if fills else 0.0

        sharpe = 0.0
        sortino = 0.0
        if returns:
            mean_r = _mean(returns)
            std_r = _std(returns)
            if std_r > 1e-12:
                sharpe = _safe_div(mean_r, std_r) * math.sqrt(252)
            downside = [r for r in returns if r < 0]
            if downside:
                downside_std = _std(downside)
                if downside_std > 1e-12:
                    sortino = _safe_div(mean_r, downside_std) * math.sqrt(252)

        var_95 = -_percentile(returns, 0.05) if returns else 0.0

        return StageMetrics(
            stage=stage,
            sample_count=n,
            bid_mae=round(_mean(bid_errors), 9),
            bid_rmse=round(math.sqrt(_mean([e ** 2 for e in bid_errors])), 9),
            ask_mae=round(_mean(ask_errors), 9),
            ask_rmse=round(math.sqrt(_mean([e ** 2 for e in ask_errors])), 9),
            mid_accuracy=round(_safe_div(mid_hits, n, 0.0), 6),
            directional_accuracy=round(_safe_div(dir_hits, dir_count, 0.0), 6),
            calibration_brier=round(_mean(brier_scores), 6) if brier_scores else None,
            fill_ratio=round(fill_ratio, 6),
            avg_slippage=round(avg_slippage, 9),
            implementation_shortfall=round(implementation_shortfall, 9),
            spread_capture=round(spread_capture, 9),
            avg_latency_ms=round(avg_latency, 6),
            total_fees=round(total_fees, 6),
            total_pnl=round(total_pnl, 6),
            sharpe=round(sharpe, 6),
            sortino=round(sortino, 6),
            max_drawdown=round(max_dd, 6),
            var_95=round(var_95, 6),
            avg_exposure=round(avg_exposure, 6),
        )


class PromotionCriteria:
    """Paired statistical comparison and risk gate for stage transitions."""

    def __init__(self, config: Any):
        self.config = config

    def paired_bootstrap_ci(
        self,
        differences: List[float],
        confidence_level: float = 0.95,
        iterations: int = 2000,
        seed: int = 42,
    ) -> Tuple[float, float]:
        if not differences:
            return 0.0, 0.0
        n = len(differences)
        rng = random.Random(seed)
        means: List[float] = []
        for _ in range(iterations):
            sample = [differences[rng.randrange(n)] for _ in range(n)]
            means.append(_mean(sample))
        alpha = 1.0 - confidence_level
        lower = _percentile(means, alpha / 2.0)
        upper = _percentile(means, 1.0 - alpha / 2.0)
        return round(lower, 9), round(upper, 9)

    def paired_t_style(
        self,
        differences: List[float],
    ) -> Dict[str, float]:
        n = len(differences)
        mean_diff = _mean(differences)
        std_diff = _std(differences)
        t_stat = _safe_div(mean_diff, std_diff / math.sqrt(n), 0.0) if n > 1 else 0.0
        return {
            "n": n,
            "mean_diff": round(mean_diff, 9),
            "std_diff": round(std_diff, 9),
            "t_stat": round(t_stat, 6),
        }

    def evaluate(
        self,
        champion_metrics: StageMetrics,
        challenger_metrics: StageMetrics,
        paired_pnl_diff: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Return promotion assessment with paired bootstrap CI and risk gate."""
        sample_count = min(champion_metrics.sample_count, challenger_metrics.sample_count)
        if sample_count < self.config.min_paired_samples:
            return {
                "eligible": False,
                "reason": f"insufficient paired samples: {sample_count} < {self.config.min_paired_samples}",
                "risk_gate_passed": False,
            }

        risk_gate = self._risk_gate(champion_metrics, challenger_metrics)
        if not risk_gate["passed"]:
            return {
                "eligible": False,
                "reason": f"risk gate failed: {risk_gate['reason']}",
                "risk_gate": risk_gate,
            }

        # Prefer paired PnL differences; fallback to prediction error difference.
        if paired_pnl_diff and any(abs(value) > 1e-12 for value in paired_pnl_diff):
            diffs = paired_pnl_diff
        else:
            diffs = [
                (champion_metrics.bid_mae + champion_metrics.ask_mae)
                - (challenger_metrics.bid_mae + challenger_metrics.ask_mae)
                for _ in range(max(1, sample_count))
            ]

        lower, upper = self.paired_bootstrap_ci(
            diffs,
            confidence_level=self.config.confidence_level,
            iterations=self.config.bootstrap_iterations,
            seed=self.config.bootstrap_seed,
        )
        t_style = self.paired_t_style(diffs)

        mean_diff = t_style["mean_diff"]
        superior = mean_diff > self.config.superiority_threshold and lower > 0.0
        non_inferior = mean_diff > self.config.non_inferiority_threshold

        decision = "continue"
        reason = "challenger not statistically superior"
        if superior and non_inferior:
            decision = "promote"
            reason = "challenger is statistically superior and non-inferior"
        elif not non_inferior:
            decision = "reject"
            reason = "challenger is inferior to champion"

        return {
            "eligible": True,
            "decision": decision,
            "reason": reason,
            "sample_count": sample_count,
            "mean_diff": mean_diff,
            "ci_lower": lower,
            "ci_upper": upper,
            "t_style": t_style,
            "superior": superior,
            "non_inferior": non_inferior,
            "risk_gate": risk_gate,
        }

    def _risk_gate(self, champion: StageMetrics, challenger: StageMetrics) -> Dict[str, Any]:
        failures: List[str] = []
        for m in (champion, challenger):
            if m.max_drawdown > self.config.max_drawdown:
                failures.append(f"{m.stage} max_drawdown {m.max_drawdown:.4f} > {self.config.max_drawdown}")
            if m.avg_exposure > self.config.max_exposure:
                failures.append(f"{m.stage} avg_exposure {m.avg_exposure:.2f} > {self.config.max_exposure}")
            if m.var_95 > self.config.max_exposure * 0.25:
                failures.append(f"{m.stage} VaR {m.var_95:.4f}")
        return {"passed": not failures, "reason": "; ".join(failures) if failures else "ok"}


def latest_stage_metrics(
    stage: str,
    records: Sequence[Dict[str, Any]],
) -> StageMetrics:
    return StageMetricsCalculator().compute(stage, records)
