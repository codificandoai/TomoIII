"""UC-700 — Agente de medición de degradación de eficiencia.

Paso 9: Medir la degradación de eficiencia.
"""

from __future__ import annotations

from typing import Dict, List

from config import AgentConfig
from models import TelemetrySnapshot, TrainingJob


class EfficiencyAgent:
    """Paso 9: Medir degradación de eficiencia post-recuperación."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def measure(
        self,
        job: TrainingJob,
        snapshots: List[TelemetrySnapshot],
    ) -> Dict[str, any]:
        if not snapshots:
            return {"efficiency_pct": 0.0, "throughput_drop_pct": 100.0, "acceptable": False}

        # Tomar promedio de las últimas muestras para suavizar ruido
        samples = [s.metrics.get("training_samples_per_sec", 0.0) for s in snapshots[-5:]]
        avg_samples = sum(samples) / len(samples) if samples else 0.0
        baseline = job.samples_per_sec_baseline

        efficiency_pct = (avg_samples / baseline * 100) if baseline > 0 else 0.0
        throughput_drop_pct = max(0.0, 100.0 - efficiency_pct)

        acceptable = throughput_drop_pct <= self.config.thresholds.allowed_throughput_drop_pct

        step_times = [s.metrics.get("training_step_time_ms", 0.0) for s in snapshots[-5:]]
        avg_step_time = sum(step_times) / len(step_times) if step_times else 0.0

        return {
            "job_id": job.id,
            "baseline_samples_per_sec": baseline,
            "current_samples_per_sec": round(avg_samples, 2),
            "efficiency_pct": round(efficiency_pct, 2),
            "throughput_drop_pct": round(throughput_drop_pct, 2),
            "avg_step_time_ms": round(avg_step_time, 2),
            "acceptable": acceptable,
            "threshold_pct": self.config.thresholds.allowed_throughput_drop_pct,
        }
