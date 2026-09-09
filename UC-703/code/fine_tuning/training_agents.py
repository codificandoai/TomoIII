"""
UC-703 fine_tuning — Recursos, SRE de entrenamiento e hyperparameter search.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fine_tuning.models_ft import ResourcePlan, TrainingRunConfig


class ResourcePlannerAgent:
    """
    Selecciona estrategia de fine-tuning y recursos según presupuesto, deadline,
    tamaño de modelo y dataset.
    """

    def __init__(self, spot_discount: float = 0.6) -> None:
        self.spot_discount = spot_discount

    def plan(
        self,
        model_size_b: float,
        dataset_samples: int,
        budget_usd: float,
        deadline_hours: float,
        prefer_reliability: bool = False,
    ) -> ResourcePlan:
        # Estrategia heurística
        if model_size_b <= 8 and dataset_samples <= 100_000 and budget_usd <= 200:
            strategy = "qlora"
            instance = "g5.xlarge" if not prefer_reliability else "g5.2xlarge"
            hours = max(1.0, dataset_samples / 20_000)
            cost = 1.0 * hours
        elif model_size_b <= 70 and budget_usd <= 1000:
            strategy = "lora"
            instance = "g5.12xlarge"
            hours = max(2.0, dataset_samples / 10_000)
            cost = 8.0 * hours
        else:
            strategy = "full"
            instance = "p4d.24xlarge"
            hours = max(4.0, dataset_samples / 5_000)
            cost = 40.0 * hours

        use_spot = (not prefer_reliability) and (cost <= budget_usd * 0.8)
        if use_spot:
            cost *= self.spot_discount

        zero = 2 if strategy != "full" else 3
        return ResourcePlan(
            strategy=strategy,
            instance_type=instance,
            use_spot=use_spot,
            estimated_cost_usd=round(cost, 2),
            estimated_duration_hours=round(hours, 2),
            num_gpus=1 if strategy == "qlora" else 4,
            zero_stage=zero,
        )


class TrainingSREAgent:
    """
    Monitorea jobs de entrenamiento y aplica políticas de recuperación ante OOM,
    deadlocks, cuellos de NVLink, etc.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, TrainingRunConfig] = {}
        self._events: Dict[str, List[Dict[str, Any]]] = {}

    def register_job(self, config: TrainingRunConfig) -> TrainingRunConfig:
        self._jobs[config.run_id] = config
        self._events[config.run_id] = []
        config.status = "pending"
        return config

    def emit_metric(self, run_id: str, metric: Dict[str, Any]) -> None:
        self._events.setdefault(run_id, []).append(metric)
        job = self._jobs.get(run_id)
        if not job:
            return
        for key in ("loss", "gpu_util", "oom", "deadlock", "nvlink_error"):
            if key in metric:
                job.metrics.setdefault(key, []).append(metric[key])

    def diagnose(self, run_id: str) -> Dict[str, Any]:
        job = self._jobs.get(run_id)
        if not job:
            return {"status": "unknown", "action": "none"}
        losses = job.metrics.get("loss", [])
        ooms = job.metrics.get("oom", [])
        deadlocks = job.metrics.get("deadlock", [])
        nvlink_errors = job.metrics.get("nvlink_error", [])

        action = "continue"
        reason = "healthy"
        if any(ooms):
            action = "reduce_batch"
            reason = "oom_detected"
        elif len(losses) >= 3 and losses[-1] > 2 * losses[-3]:
            action = "abort_divergence"
            reason = "loss_spike"
        elif any(deadlocks):
            action = "restart_from_checkpoint"
            reason = "deadlock"
        elif any(nvlink_errors):
            action = "migrate_node"
            reason = "nvlink_error"
        return {"status": job.status, "action": action, "reason": reason, "run_id": run_id}

    def apply_recovery(self, run_id: str) -> Optional[TrainingRunConfig]:
        job = self._jobs.get(run_id)
        if not job:
            return None
        diag = self.diagnose(run_id)
        if diag["action"] == "reduce_batch":
            job.hyperparams.setdefault("per_device_batch_size", 8)
            job.hyperparams["per_device_batch_size"] = max(1, job.hyperparams["per_device_batch_size"] // 2)
            job.checkpoint_uris.append(f"checkpoint://{run_id}/post-oom")
        elif diag["action"] == "restart_from_checkpoint":
            job.checkpoint_uris.append(f"checkpoint://{run_id}/post-deadlock")
        elif diag["action"] == "abort_divergence":
            job.status = "failed"
        return job


@dataclass
class HPTrial:
    trial_id: str
    hyperparams: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "hyperparams": self.hyperparams,
            "status": self.status,
            "score": self.score,
        }


class HyperparameterSearchAgent:
    """
    Búsqueda bayesiana simplificada con presupuesto fijo de GPU y early stopping
    ante loss spikes.
    """

    def __init__(self, max_trials: int = 8, metric: str = "eval_loss") -> None:
        self.max_trials = max_trials
        self.metric = metric
        self._trials: List[HPTrial] = []

    def suggest_trials(self) -> List[HPTrial]:
        # Grid simplificado para demostración.
        learning_rates = [1e-5, 5e-5, 1e-4]
        batch_sizes = [4, 8]
        lora_ranks = [8, 16]
        trials: List[HPTrial] = []
        trial_id = 0
        for lr in learning_rates:
            for bs in batch_sizes:
                for r in lora_ranks:
                    if len(trials) >= self.max_trials:
                        break
                    trials.append(HPTrial(
                        trial_id=f"trial-{trial_id:02d}",
                        hyperparams={"learning_rate": lr, "per_device_batch_size": bs, "lora_r": r},
                    ))
                    trial_id += 1
        self._trials = trials
        return trials

    def report_trial_result(self, trial_id: str, loss: float, has_spike: bool) -> HPTrial:
        trial = next((t for t in self._trials if t.trial_id == trial_id), None)
        if trial is None:
            trial = HPTrial(trial_id=trial_id)
            self._trials.append(trial)
        if has_spike:
            trial.status = "pruned"
            trial.score = float("inf")
        else:
            trial.status = "completed"
            trial.score = loss
        return trial

    def best_trial(self) -> Optional[HPTrial]:
        completed = [t for t in self._trials if t.status == "completed"]
        if not completed:
            return None
        return min(completed, key=lambda t: t.score)
