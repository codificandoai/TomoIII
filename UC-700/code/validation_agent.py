"""UC-700 — Agente de validación post-recuperación.

Paso 8: Validar que el entrenamiento continúa correctamente.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from config import AgentConfig, HealthState
from models import TelemetrySnapshot, TrainingJob


class ValidationAgent:
    """Paso 8: Validar que el entrenamiento continúa correctamente."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def validate(
        self,
        job: TrainingJob,
        snapshots: List[TelemetrySnapshot],
        baseline: Optional[Dict[str, float]] = None,
    ) -> Dict[str, any]:
        if not snapshots:
            return {"valid": False, "reason": "no_snapshots", "checks": []}

        latest = snapshots[-1]
        metrics = latest.metrics
        checks = []

        loss = metrics.get("training_loss", 0.0)
        loss_ok = abs(loss - job.loss_baseline) / max(1e-6, job.loss_baseline) <= (
            self.config.thresholds.validation_loss_delta_pct / 100.0
        )
        checks.append({
            "check": "loss_within_range",
            "value": loss,
            "baseline": job.loss_baseline,
            "passed": loss_ok,
        })

        samples = metrics.get("training_samples_per_sec", 0.0)
        samples_ok = samples >= job.samples_per_sec_baseline * 0.85
        checks.append({
            "check": "throughput_sufficient",
            "value": samples,
            "baseline": job.samples_per_sec_baseline,
            "passed": samples_ok,
        })

        step_time = metrics.get("training_step_time_ms", 0.0)
        step_ok = step_time < 300
        checks.append({
            "check": "step_time_normal",
            "value": step_time,
            "threshold_ms": 300,
            "passed": step_ok,
        })

        grad = metrics.get("training_grad_norm", 0.0)
        grad_ok = 0.1 < grad < 100.0
        checks.append({
            "check": "gradients_not_corrupt",
            "value": grad,
            "passed": grad_ok,
        })

        workers_sync = len(snapshots) >= 2
        checks.append({
            "check": "workers_synchronized",
            "value": len(snapshots),
            "passed": workers_sync,
        })

        valid = all(c["passed"] for c in checks)
        return {
            "valid": valid,
            "job_id": job.id,
            "checks": checks,
            "state": HealthState.VALIDATING if not valid else HealthState.HEALTHY,
        }
