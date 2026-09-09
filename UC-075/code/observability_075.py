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
            # LLMOps incident automation
            self.c_incidents = Counter(
                "uc075_incidents_total",
                "Incidentes detectados",
                ["category", "severity", "status"],
                registry=self.registry,
            )
            self.c_incident_escalations = Counter(
                "uc075_incident_escalations_total",
                "Escalaciones a humanos",
                ["category", "reason"],
                registry=self.registry,
            )
            self.c_incident_resolutions = Counter(
                "uc075_incident_resolutions_total",
                "Resoluciones de incidentes",
                ["category", "resolution"],
                registry=self.registry,
            )
            self.h_incident_resolution_seconds = Histogram(
                "uc075_incident_resolution_duration_seconds",
                "Tiempo hasta resolución",
                registry=self.registry,
            )
            self.c_drills = Counter(
                "uc075_drill_runs_total",
                "Simulacros ejecutados",
                ["scenario"],
                registry=self.registry,
            )
            self.g_pending_incidents = Gauge(
                "uc075_pending_incidents",
                "Incidentes esperando humano",
                registry=self.registry,
            )
            self.c_policy_learnings = Counter(
                "uc075_policy_learnings_total",
                "Aprendizajes de política derivados de incidentes",
                ["target"],
                registry=self.registry,
            )
            # adaptive incident response
            self.c_threat_intel_sync = Counter(
                "uc075_threat_intel_sync_total",
                "Sincronizaciones de inteligencia de amenazas",
                registry=self.registry,
            )
            self.g_threat_vectors = Gauge(
                "uc075_threat_vectors_total",
                "Vectores de amenaza conocidos",
                registry=self.registry,
            )
            self.c_golden_dataset_entries = Counter(
                "uc075_golden_dataset_entries_total",
                "Ejemplos añadidos al golden dataset",
                ["category"],
                registry=self.registry,
            )
            self.c_playbook_updates = Counter(
                "uc075_playbook_updates_total",
                "Actualizaciones de playbooks",
                ["playbook_id"],
                registry=self.registry,
            )
            self.h_playbook_update_latency = Histogram(
                "uc075_playbook_update_latency_seconds",
                "Latencia desde propuesta hasta merge de playbook",
                registry=self.registry,
            )
            self.c_chaos_runs = Counter(
                "uc075_chaos_runs_total",
                "Ejecuciones de caos",
                ["scenario_filter", "dry_run"],
                registry=self.registry,
            )
            self.g_chaos_pass_rate = Gauge(
                "uc075_chaos_pass_rate",
                "Tasa de éxito del último caos",
                registry=self.registry,
            )
            self.c_release_validations = Counter(
                "uc075_release_validations_total",
                "Validaciones de release gate",
                ["model_version", "passed"],
                registry=self.registry,
            )
            self.g_release_pass_rate = Gauge(
                "uc075_release_pass_rate",
                "Tasa de éxito del último release gate",
                registry=self.registry,
            )
            self.c_false_negatives = Counter(
                "uc075_false_negatives_total",
                "Falsos negativos post-regla",
                ["category", "rule_id"],
                registry=self.registry,
            )
            self.g_challenge_coverage = Gauge(
                "uc075_challenge_coverage_percent",
                "Cobertura del dataset de desafío",
                registry=self.registry,
            )
            # Incident Command Center (StackStorm + Wiki.js)
            self.c_icc_incidents_reported = Counter(
                "uc075_icc_incidents_reported_total",
                "Incidentes reportados al ICC",
                ["category", "severity"],
                registry=self.registry,
            )
            self.c_icc_actions_submitted = Counter(
                "uc075_icc_actions_submitted_total",
                "Acciones enviadas a StackStorm",
                ["action", "scope"],
                registry=self.registry,
            )
            self.c_icc_actions_executed = Counter(
                "uc075_icc_actions_executed_total",
                "Acciones ejecutadas por StackStorm",
                ["action", "status"],
                registry=self.registry,
            )
            self.c_icc_actions_rejected = Counter(
                "uc075_icc_actions_rejected_total",
                "Acciones rechazadas por falta de autorización",
                ["action", "reason"],
                registry=self.registry,
            )
            self.c_icc_postmortems = Counter(
                "uc075_icc_postmortems_total",
                "Postmortems creados en Wiki.js",
                ["incident_id"],
                registry=self.registry,
            )
            self.c_icc_runbook_syncs = Counter(
                "uc075_icc_runbook_syncs_total",
                "Sincronizaciones de runbooks a Wiki.js",
                ["category", "version"],
                registry=self.registry,
            )
            self.g_icc_open_incidents = Gauge(
                "uc075_icc_open_incidents",
                "Incidentes abiertos en ICC",
                registry=self.registry,
            )

        self._pending_hitl_count = 0
        self._pending_incidents_count = 0
        self._icc_open_incidents = 0

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
    # LLMOps incident automation
    # ------------------------------------------------------------------
    def record_incident(
        self,
        category: str,
        severity: str,
        status: str,
        confidence: float,
        escalated: bool,
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_incidents.labels(category=category, severity=severity, status=status).inc()
        self._log_event(
            "uc075_incident_detected",
            category=category,
            severity=severity,
            status=status,
            confidence=confidence,
            escalated=escalated,
        )

    def record_incident_escalation(
        self,
        category: str,
        reasons: List[str],
    ) -> None:
        self._pending_incidents_count += 1
        if PROMETHEUS_AVAILABLE:
            self.g_pending_incidents.set(self._pending_incidents_count)
            for reason in reasons:
                self.c_incident_escalations.labels(category=category, reason=reason).inc()
        self._log_event(
            "uc075_incident_escalated",
            category=category,
            reasons=reasons,
        )

    def record_incident_resolution(
        self,
        category: str,
        resolution: str,
        duration_seconds: float,
    ) -> None:
        self._pending_incidents_count = max(0, self._pending_incidents_count - 1)
        if PROMETHEUS_AVAILABLE:
            self.g_pending_incidents.set(self._pending_incidents_count)
            self.c_incident_resolutions.labels(category=category, resolution=resolution).inc()
            self.h_incident_resolution_seconds.observe(max(duration_seconds, 0.0))
        self._log_event(
            "uc075_incident_resolved",
            category=category,
            resolution=resolution,
            duration_seconds=duration_seconds,
        )

    def record_drill(self, scenario: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_drills.labels(scenario=scenario).inc()
        self._log_event("uc075_drill_run", scenario=scenario)

    def record_policy_learning(self, target: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_policy_learnings.labels(target=target).inc()
        self._log_event("uc075_policy_learning", target=target)

    # ------------------------------------------------------------------
    # Adaptive incident response
    # ------------------------------------------------------------------
    def record_threat_intel_sync(self, new_vectors: int) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_threat_intel_sync.inc()
            self.g_threat_vectors.set(new_vectors)
        self._log_event("uc075_threat_intel_sync", new_vectors=new_vectors)

    def record_golden_dataset_entry(self, category: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_golden_dataset_entries.labels(category=category).inc()
        self._log_event("uc075_golden_dataset_entry", category=category)

    def record_playbook_update(
        self,
        playbook_id: str,
        version: str,
        latency_seconds: float,
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_playbook_updates.labels(playbook_id=playbook_id).inc()
            self.h_playbook_update_latency.observe(max(latency_seconds, 0.0))
        self._log_event(
            "uc075_playbook_update",
            playbook_id=playbook_id,
            version=version,
            latency_seconds=latency_seconds,
        )

    def record_chaos_run(
        self,
        scenario_filter: str,
        pass_rate: float,
        dry_run: bool,
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_chaos_runs.labels(
                scenario_filter=scenario_filter or "all",
                dry_run="true" if dry_run else "false",
            ).inc()
            self.g_chaos_pass_rate.set(pass_rate)
        self._log_event(
            "uc075_chaos_run",
            scenario_filter=scenario_filter,
            pass_rate=pass_rate,
            dry_run=dry_run,
        )

    def record_release_validation(
        self,
        model_version: str,
        passed: bool,
        pass_rate: float,
        coverage: float,
    ) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_release_validations.labels(
                model_version=model_version,
                passed="true" if passed else "false",
            ).inc()
            self.g_release_pass_rate.set(pass_rate)
            self.g_challenge_coverage.set(coverage)
        self._log_event(
            "uc075_release_validation",
            model_version=model_version,
            passed=passed,
            pass_rate=pass_rate,
            coverage=coverage,
        )

    def record_false_negative(self, category: str, rule_id: str = "") -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_false_negatives.labels(category=category, rule_id=rule_id or "unknown").inc()
        self._log_event("uc075_false_negative", category=category, rule_id=rule_id)

    # ------------------------------------------------------------------
    # Incident Command Center (StackStorm + Wiki.js)
    # ------------------------------------------------------------------
    def record_icc_incident_reported(self, category: str, severity: str) -> None:
        self._icc_open_incidents += 1
        if PROMETHEUS_AVAILABLE:
            self.c_icc_incidents_reported.labels(category=category, severity=severity).inc()
            self.g_icc_open_incidents.set(self._icc_open_incidents)
        self._log_event("uc075_icc_incident_reported", category=category, severity=severity)

    def record_icc_action_submitted(self, action: str, scope: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_icc_actions_submitted.labels(action=action, scope=scope).inc()
        self._log_event("uc075_icc_action_submitted", action=action, scope=scope)

    def record_icc_action_executed(self, action: str, status: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_icc_actions_executed.labels(action=action, status=status).inc()
        self._log_event("uc075_icc_action_executed", action=action, status=status)

    def record_icc_action_rejected(self, action: str, reason: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_icc_actions_rejected.labels(action=action, reason=reason).inc()
        self._log_event("uc075_icc_action_rejected", action=action, reason=reason)

    def record_icc_postmortem_created(self, incident_id: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_icc_postmortems.labels(incident_id=incident_id).inc()
        self._log_event("uc075_icc_postmortem_created", incident_id=incident_id)

    def record_icc_runbook_sync(self, category: str, version: str) -> None:
        if PROMETHEUS_AVAILABLE:
            self.c_icc_runbook_syncs.labels(category=category, version=version).inc()
        self._log_event("uc075_icc_runbook_sync", category=category, version=version)

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
                panel(9, "Incidentes por categoría",
                      "sum by (category, severity) (rate(uc075_incidents_total[5m]))",
                      {"x": 0, "y": 24, "w": 8, "h": 8}),
                panel(10, "Escalaciones a humanos",
                      "sum by (category, reason) (rate(uc075_incident_escalations_total[5m]))",
                      {"x": 8, "y": 24, "w": 8, "h": 8}),
                panel(11, "Incidentes pendientes de humano",
                      "uc075_pending_incidents",
                      {"x": 16, "y": 24, "w": 8, "h": 8}),
                panel(12, "MTTR incidentes (s)",
                      "histogram_quantile(0.95, sum(rate(uc075_incident_resolution_duration_seconds_bucket[5m])) by (le))",
                      {"x": 0, "y": 32, "w": 12, "h": 8}),
                panel(13, "Simulacros ejecutados",
                      "sum by (scenario) (rate(uc075_drill_runs_total[5m]))",
                      {"x": 12, "y": 32, "w": 6, "h": 8}),
                panel(14, "Aprendizajes de política",
                      "sum by (target) (rate(uc075_policy_learnings_total[5m]))",
                      {"x": 18, "y": 32, "w": 6, "h": 8}),
                panel(15, "Latencia de actualización de playbooks",
                      "histogram_quantile(0.95, sum(rate(uc075_playbook_update_latency_seconds_bucket[5m])) by (le))",
                      {"x": 0, "y": 40, "w": 8, "h": 8}),
                panel(16, "Tasa de éxito en caos",
                      "uc075_chaos_pass_rate",
                      {"x": 8, "y": 40, "w": 8, "h": 8}),
                panel(17, "Pass rate release gate",
                      "uc075_release_pass_rate",
                      {"x": 16, "y": 40, "w": 8, "h": 8}),
                panel(18, "Cobertura dataset de desafío",
                      "uc075_challenge_coverage_percent",
                      {"x": 0, "y": 48, "w": 8, "h": 8}),
                panel(19, "Vectores de amenaza conocidos",
                      "uc075_threat_vectors_total",
                      {"x": 8, "y": 48, "w": 8, "h": 8}),
                panel(20, "Acciones ICC ejecutadas",
                      "sum by (action, status) (rate(uc075_icc_actions_executed_total[5m]))",
                      {"x": 16, "y": 48, "w": 8, "h": 8}),
                panel(21, "Acciones ICC rechazadas",
                      "sum by (action, reason) (rate(uc075_icc_actions_rejected_total[5m]))",
                      {"x": 0, "y": 56, "w": 8, "h": 8}),
                panel(22, "Postmortems y syncs de runbook",
                      "sum(rate(uc075_icc_postmortems_total[5m])) + sum(rate(uc075_icc_runbook_syncs_total[5m]))",
                      {"x": 8, "y": 56, "w": 8, "h": 8}),
                panel(23, "Incidentes abiertos en ICC",
                      "uc075_icc_open_incidents",
                      {"x": 16, "y": 56, "w": 8, "h": 8}),
            ],
        }
