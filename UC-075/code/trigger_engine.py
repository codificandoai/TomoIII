"""
UC-075 — Motor de triggers: decide SI y POR QUÉ reentrenar.

Estrategias:
1. SCHEDULED — intervalo regular para modelos con patrones estables.
2. EVENT_DRIVEN — umbrales de drift/error/latencia/calibración/satisfacción/KPI.
3. ON_DEMAND — cambios de producto, políticas o fuentes de datos.
4. INCREMENTAL — mini-batches en flujo continuo con replay anti-olvido.

El motor NO entrena: produce un RetrainTrigger justificado o una decisión de
bloqueo con violaciones de política/presupuesto (fail-closed).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models_075 import (
    OrchestratorPolicy,
    RetrainStrategy,
    RetrainTrigger,
    TriggerDecision,
)


@dataclass
class _BudgetLedger:
    """Contador interno de reentrenamientos y costo por día."""
    day: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))
    count: int = 0
    cost_usd: float = 0.0
    incremental_count: int = 0

    def roll_day(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day = today
            self.count = 0
            self.cost_usd = 0.0
            self.incremental_count = 0


class TriggerEngine:
    """Evalúa estrategias de reentrenamiento contra la política de gobernanza."""

    def __init__(self, policy: Optional[OrchestratorPolicy] = None) -> None:
        self.policy = policy or OrchestratorPolicy()
        self._ledger = _BudgetLedger()
        self._last_scheduled_run: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Estrategia 1: SCHEDULED
    # ------------------------------------------------------------------
    def scheduled_due(self, agent_id: str, interval_hours: float, now: Optional[float] = None) -> Optional[RetrainTrigger]:
        """Devuelve trigger si el modelo cumple su ciclo programado."""
        now = now or time.time()
        last = self._last_scheduled_run.get(agent_id, 0.0)
        if (now - last) < interval_hours * 3600:
            return None
        return RetrainTrigger(
            strategy=RetrainStrategy.SCHEDULED,
            reason=f"Ciclo programado ({interval_hours}h) cumplido para {agent_id}.",
            business_trigger="periodic_maintenance",
        )

    def mark_scheduled_run(self, agent_id: str, when: Optional[float] = None) -> None:
        self._last_scheduled_run[agent_id] = when or time.time()

    # ------------------------------------------------------------------
    # Estrategia 2: EVENT_DRIVEN
    # ------------------------------------------------------------------
    def evaluate_event(self, metrics: Dict[str, float], domain: str = "default") -> Optional[RetrainTrigger]:
        """Dispara reentrenamiento si alguna métrica supera umbral.

        Métricas aceptadas: drift_score, error_rate,
        latency_degradation_pct, calibration_error, user_satisfaction.
        """
        p = self.policy
        reasons: List[str] = []

        drift = metrics.get("drift_score", 0.0)
        if drift >= p.drift_score_threshold:
            reasons.append(f"drift {drift:.3f} >= {p.drift_score_threshold}")

        err = metrics.get("error_rate", 0.0)
        if err >= p.error_rate_threshold:
            reasons.append(f"error_rate {err:.3f} >= {p.error_rate_threshold}")

        lat = metrics.get("latency_degradation_pct", 0.0)
        if lat >= p.latency_p95_degradation_pct:
            reasons.append(f"latency +{lat:.1f}% >= {p.latency_p95_degradation_pct}%")

        cal = metrics.get("calibration_error", 0.0)
        if cal >= p.calibration_error_threshold:
            reasons.append(f"calibration_error {cal:.3f} >= {p.calibration_error_threshold}")

        sat = metrics.get("user_satisfaction", 1.0)
        if sat < p.user_satisfaction_threshold:
            reasons.append(f"user_satisfaction {sat:.3f} < {p.user_satisfaction_threshold}")

        business_kpi = metrics.get("business_kpi_breach", 0.0)
        if business_kpi:
            reasons.append("business KPI breach")

        if not reasons:
            return None

        return RetrainTrigger(
            strategy=RetrainStrategy.EVENT_DRIVEN,
            reason="; ".join(reasons),
            business_trigger="metric_threshold_breach",
            metrics=dict(metrics),
            domain=domain,
        )

    # ------------------------------------------------------------------
    # Estrategia 3: ON_DEMAND
    # ------------------------------------------------------------------
    def on_demand(
        self,
        change_type: str,
        detail: str,
        new_data: Optional[List[Dict[str, Any]]] = None,
        domain: str = "default",
        estimated_cost_usd: float = 0.0,
    ) -> RetrainTrigger:
        """Trigger manual ante cambio de producto, política o fuente de datos."""
        return RetrainTrigger(
            strategy=RetrainStrategy.ON_DEMAND,
            reason=f"{change_type}: {detail}",
            business_trigger=change_type,
            new_data=list(new_data or []),
            domain=domain,
            estimated_cost_usd=estimated_cost_usd,
        )

    # ------------------------------------------------------------------
    # Estrategia 4: INCREMENTAL
    # ------------------------------------------------------------------
    def incremental(
        self,
        batch: List[Dict[str, Any]],
        replay_buffer: List[Dict[str, Any]],
        domain: str = "default",
    ) -> Optional[RetrainTrigger]:
        """Mini-batch incremental con replay buffer (prevención de olvido).

        Rechaza silenciosamente (None) si no hay datos nuevos. El control
        de olvido catastrófico se valida en el gate de drift del pipeline.
        """
        if not batch:
            return None
        return RetrainTrigger(
            strategy=RetrainStrategy.INCREMENTAL,
            reason=f"Mini-batch incremental ({len(batch)} nuevos, {len(replay_buffer)} replay).",
            business_trigger="continuous_stream",
            new_data=list(batch),
            replay_buffer=list(replay_buffer),
            incremental_batch=True,
            domain=domain,
        )

    # ------------------------------------------------------------------
    # Gobernanza: presupuesto y política (fail-closed)
    # ------------------------------------------------------------------
    def evaluate_policy(self, trigger: RetrainTrigger) -> TriggerDecision:
        """Decide si el trigger cumple política y presupuesto."""
        self._ledger.roll_day()
        violations: List[str] = []
        p = self.policy

        if self._ledger.count >= p.max_retrains_per_day:
            violations.append(f"retrain_cap:{self._ledger.count}/{p.max_retrains_per_day}")

        if trigger.estimated_cost_usd > p.max_retrain_cost_usd:
            violations.append(
                f"budget:{trigger.estimated_cost_usd:.2f}>{p.max_retrain_cost_usd:.2f}"
            )

        if self._ledger.cost_usd + trigger.estimated_cost_usd > p.max_retrain_cost_usd * p.max_retrains_per_day:
            violations.append("daily_budget_exhausted")

        if trigger.strategy == RetrainStrategy.INCREMENTAL:
            if self._ledger.incremental_count >= p.incremental_max_sessions_per_day:
                violations.append("incremental_cap")
            if not trigger.replay_buffer:
                violations.append("incremental_without_replay")

        if violations:
            return TriggerDecision(
                proceed=False,
                reason="Policy/budget gate blocked retraining.",
                policy_violations=violations,
            )

        return TriggerDecision(proceed=True, reason="Policy and budget OK.")

    def register_spend(self, trigger: RetrainTrigger, actual_cost_usd: float) -> None:
        """Registra ejecución y gasto real (llamado por el orquestador)."""
        self._ledger.roll_day()
        self._ledger.count += 1
        self._ledger.cost_usd += actual_cost_usd
        if trigger.strategy == RetrainStrategy.INCREMENTAL:
            self._ledger.incremental_count += 1

    def budget_status(self) -> Dict[str, Any]:
        self._ledger.roll_day()
        p = self.policy
        return {
            "day": self._ledger.day,
            "retrains_used": self._ledger.count,
            "retrains_cap": p.max_retrains_per_day,
            "cost_used_usd": round(self._ledger.cost_usd, 4),
            "cost_cap_usd": p.max_retrain_cost_usd * p.max_retrains_per_day,
            "incremental_used": self._ledger.incremental_count,
            "incremental_cap": p.incremental_max_sessions_per_day,
        }
