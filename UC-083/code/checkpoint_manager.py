"""
UC-083 — Gestor de checkpoints idempotentes para reprocesamiento batch.

Permite reanudar el procesamiento de particiones sin repetir lotes ya
completados, registrando el progreso en disco.
"""

import os
import json
import time
from typing import List, Dict, Optional, Any

from incident_models import Checkpoint


class CheckpointManager:
    """
    Mantiene el estado de checkpoints por pipeline. Soporta guardar,
cargar, marcar como completado y reanudar desde el último progreso.
    """

    def __init__(self, pipeline_id: str, checkpoint_dir: str = ".uc083_checkpoints"):
        self.pipeline_id = pipeline_id
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
        self._path = os.path.join(checkpoint_dir, f"{pipeline_id}.json")
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for partition_id, c in data.items():
                self._checkpoints[partition_id] = Checkpoint(**c)
        except Exception:
            self._checkpoints = {}

    def _save(self) -> None:
        data = {pid: c.to_dict() for pid, c in self._checkpoints.items()}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def create(self, partition_id: str, metadata: Optional[Dict[str, Any]] = None) -> Checkpoint:
        checkpoint = Checkpoint(
            partition_id=partition_id,
            status="pending",
            records_processed=0,
            metadata=metadata or {},
        )
        self._checkpoints[partition_id] = checkpoint
        self._save()
        return checkpoint

    def get(self, partition_id: str) -> Optional[Checkpoint]:
        return self._checkpoints.get(partition_id)

    def complete(self, partition_id: str, records_processed: int, metadata: Optional[Dict[str, Any]] = None) -> Checkpoint:
        checkpoint = self._checkpoints.get(partition_id)
        if checkpoint is None:
            checkpoint = self.create(partition_id)
        checkpoint.status = "completed"
        checkpoint.records_processed = records_processed
        checkpoint.timestamp = time.time()
        if metadata:
            checkpoint.metadata.update(metadata)
        self._save()
        return checkpoint

    def fail(self, partition_id: str, reason: str) -> Checkpoint:
        checkpoint = self._checkpoints.get(partition_id)
        if checkpoint is None:
            checkpoint = self.create(partition_id)
        checkpoint.status = "failed"
        checkpoint.timestamp = time.time()
        checkpoint.metadata["failure_reason"] = reason
        self._save()
        return checkpoint

    def is_completed(self, partition_id: str) -> bool:
        checkpoint = self._checkpoints.get(partition_id)
        return checkpoint is not None and checkpoint.status == "completed"

    def pending_partitions(self, partitions: List[str]) -> List[str]:
        """Devuelve particiones que aún no están completadas."""
        return [p for p in partitions if not self.is_completed(p)]

    def all_checkpoints(self) -> List[Checkpoint]:
        return list(self._checkpoints.values())

    def reset(self) -> None:
        self._checkpoints.clear()
        if os.path.exists(self._path):
            os.remove(self._path)

    def get_statistics(self) -> Dict[str, Any]:
        completed = sum(1 for c in self._checkpoints.values() if c.status == "completed")
        failed = sum(1 for c in self._checkpoints.values() if c.status == "failed")
        pending = sum(1 for c in self._checkpoints.values() if c.status == "pending")
        total_records = sum(c.records_processed for c in self._checkpoints.values())
        return {
            "pipeline_id": self.pipeline_id,
            "total": len(self._checkpoints),
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "total_records_processed": total_records,
        }
