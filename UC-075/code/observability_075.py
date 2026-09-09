"""
UC-075 — Observabilidad del orquestador (Prometheus + Grafana Stack).

Prometheus (CollectorRegistry por instancia, como UC-325):
  uc075_retrain_triggers_total{strategy}
  uc075_retrain_completed_total{status}
  uc075_gate_verdicts_total{gate,verdict}
  uc075_drift_score
  uc075_pipeline_status{status}            (gauge informativo)
  uc075_retrain_cost_usd
  uc075_run_duration_seconds
  uc075_pending_hitl
  uc075_rollbacks_total

Exportadores:
- render_prometheus() → texto exposition
- to_loki_lines()     → líneas JSON para Loki (auditoría)
- to_tempo_spans()    → spans OTLP-lite por run
- render_grafana_dashboard() → dashboard JSON provisionable
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except Exception:
    PROMETHEUS_AVAILABLE = False

ONLINE_CB_STATES = {"closed": 0.0, "half_open": 0.5, "open": 1.0}


class Observability075:
    """Métricas + exporter + dashboard del orquestador de reentrenamiento."""

    def __init__(self) -> None:
        self.registry: Optional[Any] = None
        self._events: List[Dict[str, Any]] = []  # buffer Loki/Tempo

        if PROMETHEUS_AVAILABLE:
            self.registry = CollectorRegistry()
            self.c_triggers = Counter(
                "uc075_retrain_triggers_total",
                "Triggers de reentrenamiento aceptados",
                ["strategy"],
                registry=self.registry,
            )
            self.c_completed = Counter(
                "uc075_retrain_completed_total",
                "Runs completados por estado final",
                ["status"],
                registry=self.registry,
            )
            self.c_gates = Counter(
                "uc075_gate_verdicts_total",
                "Veredictos de gates",
                ["gate", "verdict"],
                registry=self.registry,
            )
            self.c_rollbacks = Counter(
                "uc075_rollbacks_total",
                "Rollbacks automáticos tras canary failure",
                registry=self.registry,
            )
            self.g_drift = Gauge(
                "uc075_drift_score",
                "Drift score del último run",
                registry=self.registry,
            )
            self.g_status = Gauge(
                "uc075_pipeline_status",
                "Estado del último run (info gauge)",
                ["status"],
                registry=self.registry,
            )
            self.g_pending_hitl = Gauge(
                "uc075_pending_hitl",
                "Runs esperando aprobación humana",
                registry=self.registry,
            )
            self.g_cost = Gauge(
                "uc075_retrain_cost_usd",
                "Costo USD del último run",
                registry=self.registry,
            )
            self.h_duration = Histogram(
                "uc075_run_duration_seconds",
                "Duración del run completo",
                registry=self.registry,
            )
            # online incremental + circuit breaker
            self.g_cb_state = Gauge(
                "uc075_circuit_breaker_state",
                "Estado del circuit breaker (0=closed, 0.5=half_open, 1=open)",
                ["learner"],
                registry=self.registry,
            )
            self.c_quarantine = Counter(
                "uc075_quarantined_microbatches_total",
                "Micro-lotes puestos en cuarentena",
                ["learner", "reason"],
                registry=self.registry,
            )
            self.g_partial_fit_drift = Gauge(
                "uc075_partial_fit_drift_score",
                "Drift score del micro-lote evaluado",
                ["learner", "phase"],
                registry=self.registry,
            )
            self.g_online_acc = Gauge(
                "uc075_online_incremental_accuracy",
                "Accuracy pre/post partial_fit",
                ["learner", "phase"],
                registry=self.registry,
            )

        self._pending_hitl_count = 0

    # ------------------------------------------------------------------
    # Registro de eventos
    # ------------------------------------------------------------------
    def record_trigger(self, strategy: str, drift_score: float) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_triggers.labels(strategy=strategy).inc()
            self.g_drift.set(drift_score)
        self._log_event("uc075_trigger", strategy=strategy, drift_score=drift_score)

    def record_gate(self, gate: str, verdict: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_gates.labels(gate=gate, verdict=verdict).inc()
        self._log_event("uc075_gate", gate=gate, verdict=verdict)

    def record_pending_hitl(self, delta: int) -> None:
        self._pending_hitl_count = max(0, self._pending_hitl_count + delta)
        if PROMETHEUS_AVAILABLE:
            self.g_pending_hitl.set(self._pending_hitl_count)
        self._log_event("uc075_hitl_pending", pending=self._pending_hitl_count)

    def record_completed(
        self,
        status: str,
        duration_sec: float,
        cost_usd: float,
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_completed.labels(status=status).inc()
            self.h_duration.observe(max(duration_sec, 0.0))
            self.g_cost.set(cost_usd)
            for label in (status,):
                self.g_status.labels(status=label).set(1)
        if status == "rolled_back" and PROMETHEUS_AVAILABLE:
            self.c_rollbacks.inc()
        self._log_event(
            "uc075_completed",
            status=status,
            duration_sec=duration_sec,
            cost_usd=cost_usd,
        )

    # ------------------------------------------------------------------
    # Online incremental / circuit breaker
    # ------------------------------------------------------------------
    def record_circuit_breaker_state(self, learner: str, state: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.g_cb_state.labels(learner=learner).set(ONLINE_CB_STATES.get(state, 0.0))
        self._log_event("uc075_circuit_breaker_state", learner=learner, state=state)

    def record_quarantine(
        self,
        learner: str,
        reason: str,
        drift_score: float,
        accuracy_pre: Optional[float],
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_quarantine.labels(learner=learner, reason=reason).inc()
            self.g_partial_fit_drift.labels(learner=learner, phase="quarantine").set(drift_score)
        self._log_event(
            "uc075_quarantine",
            learner=learner,
            reason=reason,
            drift_score=drift_score,
            accuracy_pre=accuracy_pre,
        )

    def record_partial_fit(
        self,
        learner: str,
        drift_score: float,
        accuracy_pre: float,
        accuracy_post: float,
        applied: bool,
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.g_partial_fit_drift.labels(learner=learner, phase="post").set(drift_score)
            self.g_online_acc.labels(learner=learner, phase="pre").set(accuracy_pre)
            self.g_online_acc.labels(learner=learner, phase="post").set(accuracy_post)
        self._log_event(
            "uc075_partial_fit",
            learner=learner,
            drift_score=drift_score,
            accuracy_pre=accuracy_pre,
            accuracy_post=accuracy_post,
            applied=applied,
        )

    # ------------------------------------------------------------------
    # Exporters
    # ------------------------------------------------------------------
    def export_prometheus(self) -> str:
        if not PROMETHEUS_AVAILABLE:
            return "# prometheus_client no disponible\n"
        return generate_latest(self.registry).decode("utf-8")

    def to_loki_lines(self) -> List[str]:
        """Eventos en formato Loki push (JSON lines)."""
        return [
            json.dumps({"ts_ns": int(e.get("timestamp", time.time()) * 1e9), "line": e}, default=str)
            for e in self._events[-500:]
        ]

    def to_tempo_spans(self, run_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Representación tipo span OTLP-lite del run."""
        return {
            "trace_id": run_dict.get("run_id", ""),
            "span_id": uuid.uuid4().hex[:16],
            "name": "uc075.pipeline_run",
            "start_ns": int(run_dict.get("started_at", 0) * 1e9),
            "end_ns": int(run_dict.get("finished_at", 0) * 1e9)
            if run_dict.get("finished_at") else int(time.time() * 1e9),
            "attributes": {
                "strategy": run_dict.get("strategy_used", ""),
                "status": run_dict.get("status", ""),
                "drift_score": run_dict.get("drift_score", 0.0),
                "decision": run_dict.get("decision") or "",
            },
            "links": [run_dict.get("mlflow_run_id", "")],
        }

    # ------------------------------------------------------------------
    def _log_event(self, kind: str, **payload: Any) -> None:
        self._events.append({"kind": kind, "timestamp": time.time(), **payload})
        if len(self._events) > 5000:
            self._events = self._events[-2500:]

    # ------------------------------------------------------------------
    @staticmethod
    def render_grafana_dashboard() -> Dict[str, Any]:
        """Dashboard JSON provisionable (Grafana Stack: prometheus datasource)."""
        def panel(pid: int, title: str, expr: str, grid: Dict[str, int]) -> Dict[str, Any]:
            return {
                "id": pid,
                "title": title,
                "type": "timeseries",
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "gridPos": grid,
                "targets": [{"expr": expr, "legendFormat": title}],
            }

        return {
            "title": "UC-075 — Continuous Training Orchestrator",
            "uid": "uc075-cto",
            "schemaVersion": 39,
            "refresh": "30s",
            "panels": [
                panel(1, "Triggers por estrategia",
                      "sum by (strategy) (rate(uc075_retrain_triggers_total[5m]))",
                      {"x": 0, "y": 0, "w": 8, "h": 8}),
                panel(2, "Runs completados por estado",
                      "sum by (status) (rate(uc075_retrain_completed_total[5m]))",
                      {"x": 8, "y": 0, "w": 8, "h": 8}),
                panel(3, "Veredictos de gates",
                      "sum by (gate, verdict) (rate(uc075_gate_verdicts_total[5m]))",
                      {"x": 16, "y": 0, "w": 8, "h": 8}),
                panel(4, "Drift score", "uc075_drift_score",
                      {"x": 0, "y": 8, "w": 8, "h": 8}),
                panel(5, "Pendientes HITL", "uc075_pending_hitl",
                      {"x": 8, "y": 8, "w": 8, "h": 8}),
                panel(6, "Rollbacks",
                      "sum(rate(uc075_rollbacks_total[15m]))",
                      {"x": 16, "y": 8, "w": 8, "h": 8}),
                panel(7, "Costo por run (USD)", "uc075_retrain_cost_usd",
                      {"x": 0, "y": 16, "w": 12, "h": 8}),
                panel(8, "Duración p95 (s)",
                      "histogram_quantile(0.95, sum(rate(uc075_run_duration_seconds_bucket[5m])) by (le))",
                      {"x": 12, "y": 16, "w": 12, "h": 8}),
            ],
        }
