"""
UC-308 — Orquestador del pipeline de evaluación continua y detección de deriva.

Integra golden dataset, simulador de entorno, runner, detectores, baselines,
alert manager y recomendaciones. Consume telemetría de otros UCs de forma
conceptual, sin auto-modificar agentes ni dependencias externas.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from alert_manager_308 import AlertManager
from baseline_manager import BaselineManager
from drift_detectors import ALL_DETECTORS
from environment_simulator import SimulatedExternalEnvironment
from golden_dataset import GoldenDataset
from mitigation_advisor import MitigationAdvisor
from models_308 import (
    Alert,
    DriftConfig,
    DriftSignal,
    DriftStatus,
    EvaluationRun,
    SystemStatus,
)
from observability_308 import ObservabilityManager
from nightly_scheduler import NightlyScheduler
from regression_runner import RegressionRunner


_STATUS_NUMERIC = {
    SystemStatus.NORMAL: 0,
    SystemStatus.WARNING: 1,
    SystemStatus.DEGRADED: 2,
    SystemStatus.CRITICAL: 3,
}

_DRIFT_STATUS_NUMERIC = {
    DriftStatus.NORMAL: 0,
    DriftStatus.WARNING: 1,
    DriftStatus.DEGRADED: 2,
    DriftStatus.CRITICAL: 3,
}


class DriftOrchestrator:
    """Orquesta el pipeline de evaluación continua de UC-308."""

    def __init__(
        self,
        config: Optional[DriftConfig] = None,
        dataset: Optional[GoldenDataset] = None,
        environment: Optional[SimulatedExternalEnvironment] = None,
        baseline_manager: Optional[BaselineManager] = None,
        runner: Optional[RegressionRunner] = None,
        detectors: Optional[Sequence] = None,
        alert_manager: Optional[AlertManager] = None,
        advisor: Optional[MitigationAdvisor] = None,
        observability: Optional[ObservabilityManager] = None,
        scheduler: Optional[NightlyScheduler] = None,
    ):
        self.config = config or DriftConfig()
        self.dataset = dataset or GoldenDataset(version="0.0.0", cases=[])
        self.environment = environment or SimulatedExternalEnvironment(seed=42)
        self.baseline_manager = baseline_manager or BaselineManager()
        self.runner = runner or RegressionRunner(observability or ObservabilityManager())
        self.detectors = list(detectors or ALL_DETECTORS)
        self.advisor = advisor or MitigationAdvisor()
        self.alert_manager = alert_manager or AlertManager(self.advisor)
        self.observability = self.runner.observability
        self.scheduler = scheduler or NightlyScheduler()
        self.history: List[EvaluationRun] = []
        self._telemetry_buffer: List[Dict[str, Any]] = []

    def initialize_baselines(
        self,
        scenario: str = "healthy",
        scenario_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ejecuta una corrida sana y registra un baseline por herramienta."""
        self.environment.reset(seed=self.environment.seed)
        self.environment.set_scenario(scenario, scenario_params)
        run = self.runner.run_evaluation(
            self.dataset,
            self.environment,
            self.config,
            trigger="baseline",
        )
        self.baseline_manager.record_baseline_from_run(run, self.config, label="healthy")
        self.history.append(run)
        return {
            "run_id": run.run_id,
            "baselines_created": len(self.baseline_manager.baselines),
            "baselines": self.baseline_manager.list_baselines(),
        }

    def run_evaluation(
        self,
        trigger: str = "manual",
        scenario: Optional[str] = None,
        scenario_params: Optional[Dict[str, Any]] = None,
    ) -> EvaluationRun:
        """Ejecuta una evaluación completa: run -> detect -> alertar."""
        if scenario is not None:
            self.environment.set_scenario(scenario, scenario_params)

        run = self.runner.run_evaluation(
            self.dataset,
            self.environment,
            self.config,
            trigger=trigger,
        )

        signals = self._detect_drift(run)
        self._enrich_signals(signals)
        run.drift_signals = signals

        system_status, new_alerts = self.alert_manager.evaluate_run(
            run, signals, self.config
        )
        run.system_status = system_status
        run.alert_ids = [a.alert_id for a in new_alerts]
        self._record_observability(run, signals, new_alerts)

        self.history.append(run)
        return run

    def _detect_drift(self, run: EvaluationRun) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        for detector in self.detectors:
            signals.extend(detector.detect(run, self.baseline_manager.baselines, self.config))
        return signals

    def _enrich_signals(self, signals: Sequence[DriftSignal]) -> None:
        for signal in signals:
            baseline = self.baseline_manager.get_by_id(signal.baseline_id)
            tool = baseline.tool if baseline else "unknown"
            signal.tool = tool
            signal.evidence.setdefault("tool", tool)

    def _record_observability(
        self,
        run: EvaluationRun,
        signals: Sequence[DriftSignal],
        alerts: Sequence[Alert],
    ) -> None:
        # Run status
        status_value = _STATUS_NUMERIC.get(run.system_status, 0)
        self.observability.gauge(
            "uc308_run_status",
            status_value,
            {
                "agent_id": self.config.agent_id,
                "environment": self.config.environment,
                "version": self.config.agent_version,
                "status": run.system_status.value,
            },
        )

        # Drift signals
        for signal in signals:
            self.observability.gauge(
                "uc308_drift_score",
                signal.score,
                {
                    "drift_type": signal.drift_type.value,
                    "dimension": signal.dimension,
                    "tool": signal.tool or "unknown",
                },
            )
            self.observability.gauge(
                "uc308_drift_status",
                _DRIFT_STATUS_NUMERIC.get(signal.status, 0),
                {
                    "drift_type": signal.drift_type.value,
                    "status": signal.status.value,
                    "tool": signal.tool or "unknown",
                },
            )

        # Alerts
        for alert in alerts:
            self.observability.increment(
                "uc308_alerts_total",
                1,
                {"severity": alert.status.value},
            )

        # Señales de otros UCs consumidas conceptualmente
        agg = run.aggregate
        self.observability.gauge(
            "uc308_uc300_block_signals_total",
            agg.get("uc300_block_total", 0),
            {"environment": self.config.environment},
        )
        self.observability.gauge(
            "uc308_uc290_override_signals_total",
            agg.get("uc290_override_total", 0),
            {"environment": self.config.environment},
        )
        self.observability.gauge(
            "uc308_uc315_telemetry_received_total",
            0,
            {"source": "uc315"},
        )

    def register_telemetry(self, source: str, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Consume telemetría de UC-315/290/300/162/083/324 de forma conceptual.
        No realiza acciones externas; solo registra métricas y logs.
        """
        self.observability.increment(
            "uc308_telemetry_received_total",
            1,
            {"source": source, "event_type": event_type},
        )
        self.observability.log(
            level="INFO",
            message=f"Telemetry received from {source}: {event_type}",
            extra={"source": source, "event_type": event_type, "payload": payload},
        )
        self._telemetry_buffer.append({
            "timestamp": time.time(),
            "source": source,
            "event_type": event_type,
            "payload": payload,
        })

    def run_if_due(self, now: Optional[float] = None) -> Optional[EvaluationRun]:
        """Ejecuta si el scheduler indica que es hora del nightly run."""
        if self.scheduler.is_due(now):
            run = self.run_evaluation(trigger="nightly")
            self.scheduler.mark_run(now)
            return run
        return None

    def trigger_event(self) -> EvaluationRun:
        """Ejecución por evento."""
        self.scheduler.run_now()
        return self.run_evaluation(trigger="event")

    def get_status(self) -> Dict[str, Any]:
        latest = self.history[-1] if self.history else None
        return {
            "service": "UC-308 Agent Drift Orchestrator",
            "status": "ok",
            "latest_run": latest.to_dict() if latest else None,
            "run_count": len(self.history),
            "baseline_count": len(self.baseline_manager.baselines),
            "active_alerts": len(self.alert_manager.get_active_alerts()),
            "total_alerts": len(self.alert_manager.alerts),
            "scheduler": self.scheduler.to_dict(),
            "observability": self.observability.get_summary(),
        }

    def get_history(self) -> List[Dict[str, Any]]:
        return [run.to_dict() for run in self.history]

    def get_alerts(self) -> Dict[str, Any]:
        return self.alert_manager.to_dict()

    def acknowledge_alert(self, alert_id: str) -> bool:
        return self.alert_manager.acknowledge(alert_id)

    def get_metrics(self) -> str:
        return self.observability.export_prometheus()

    def reset(self) -> None:
        self.history.clear()
        self.baseline_manager.clear()
        self.alert_manager.reset()
        self.observability.reset()
        self._telemetry_buffer.clear()
        self.environment.reset(seed=42)
        self.scheduler = NightlyScheduler(self.scheduler.cron_expr)
