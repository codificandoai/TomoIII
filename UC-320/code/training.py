"""UC-320 — Training Job Stub: job aislado, reproducible y versionado.

El entrenamiento debe ejecutarse como un job aislado, separado del bucle
de ejecución de mercado. No se actualizan pesos en línea mientras existe
una orden externa pendiente.

Patrón seguro:
  1. Recopilar episodios
  2. Desidentificar
  3. Crear dataset versionado
  4. Entrenar en sandbox
  5. Evaluar
  6. Red-team
  7. Crear checkpoint
  8. Solicitar aprobación
  9. Promover mediante canary

Esta implementación es un stub determinista para tests. En producción
debe conectarse a transformers.Trainer con datasets reales.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TrainingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # UC-324 bloqueó el job


@dataclass
class TrainingJob:
    job_id: str
    base_model: str
    dataset_id: str
    dataset_revision: str
    output_dir: str
    objective: str
    metrics: Dict[str, float] = field(default_factory=dict)
    status: TrainingStatus = TrainingStatus.PENDING
    checkpoint_hash: str = ""
    model_card: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "base_model": self.base_model,
            "dataset_id": self.dataset_id,
            "dataset_revision": self.dataset_revision,
            "output_dir": self.output_dir,
            "objective": self.objective,
            "metrics": self.metrics,
            "status": self.status.value,
            "checkpoint_hash": self.checkpoint_hash,
            "model_card": self.model_card,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class TrainingManager:
    """Gestor de jobs de entrenamiento controlados."""

    def __init__(self) -> None:
        self._jobs: Dict[str, TrainingJob] = {}

    def submit(
        self,
        base_model: str,
        dataset_id: str,
        dataset_revision: str,
        output_dir: str,
        objective: str,
    ) -> TrainingJob:
        job = TrainingJob(
            job_id=f"train_{uuid.uuid4().hex[:10]}",
            base_model=base_model,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
            output_dir=output_dir,
            objective=objective,
        )
        self._jobs[job.job_id] = job
        return job

    def run(self, job_id: str, approved: bool = True) -> TrainingJob:
        """Ejecuta el job. Si approved=False (UC-324 bloqueó), marca BLOCKED."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if not approved:
            job.status = TrainingStatus.BLOCKED
            job.error = "Blocked by UC-324: dataset/license/PII/policy validation failed"
            return job

        job.status = TrainingStatus.RUNNING
        # Stub: en producción esto ejecuta transformers.Trainer.
        # Aquí simulamos métricas deterministas.
        time.sleep(0.01)
        job.status = TrainingStatus.EVALUATING
        job.metrics = {
            "eval_f1": 0.87,
            "eval_accuracy": 0.91,
            "eval_loss": 0.34,
            "train_loss": 0.42,
        }
        job.checkpoint_hash = hashlib.sha256(
            f"{job.base_model}:{job.dataset_id}:{job.objective}".encode()
        ).hexdigest()[:16]
        job.model_card = {
            "base_model": job.base_model,
            "dataset": job.dataset_id,
            "dataset_revision": job.dataset_revision,
            "objective": job.objective,
            "metrics": job.metrics,
            "license": "internal",
            "limitations": ["Stub training; not for production without UC-324 approval."],
            "red_team_status": "pending",
        }
        job.status = TrainingStatus.COMPLETED
        job.completed_at = time.time()
        return job

    def get(self, job_id: str) -> Optional[TrainingJob]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.values()]

    def promote(self, job_id: str, human_approved: bool) -> Dict[str, Any]:
        """Promoción productiva: requiere aprobación humana + UC-324."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        if job.status != TrainingStatus.COMPLETED:
            return {"promoted": False, "reason": f"Job status is {job.status.value}, must be completed"}
        if not human_approved:
            return {"promoted": False, "reason": "Human approval required for production promotion"}
        if job.model_card.get("red_team_status") != "passed":
            return {"promoted": False, "reason": "Red-team must pass before promotion"}
        return {
            "promoted": True,
            "job_id": job_id,
            "checkpoint_hash": job.checkpoint_hash,
            "model_card": job.model_card,
            "message": "Model promoted to production via canary deployment",
        }
