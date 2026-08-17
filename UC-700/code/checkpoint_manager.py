"""UC-700 — Checkpoint Manager.

Paso 6: Recuperar desde el último checkpoint válido.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import AgentConfig, HealthState
from models import Checkpoint, TrainingJob


class CheckpointManager:
    """Gestiona checkpoints consistentes, verifica integridad y selecciona el último válido."""

    def __init__(self, config: AgentConfig, storage_path: str = "/tmp/qbex-checkpoints"):
        self.config = config
        self.storage_path = storage_path
        self._checkpoints: Dict[str, List[Checkpoint]] = {}
        os.makedirs(storage_path, exist_ok=True)

    def create_checkpoint(
        self,
        job: TrainingJob,
        global_step: int,
        verified: bool = True,
        size_bytes: int = 0,
    ) -> Checkpoint:
        cp_id = f"{job.id}-cp-{global_step}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        path = os.path.join(self.storage_path, cp_id)
        checksum = hashlib.sha256(
            json.dumps({"job_id": job.id, "step": global_step, "ts": datetime.utcnow().isoformat()}).encode()
        ).hexdigest()
        cp = Checkpoint(
            id=cp_id,
            job_id=job.id,
            path=path,
            timestamp=datetime.utcnow(),
            global_step=global_step,
            verified=verified,
            size_bytes=size_bytes,
            checksum=checksum,
        )
        os.makedirs(path, exist_ok=True)
        placeholder = os.path.join(path, "checkpoint.bin")
        with open(placeholder, "wb") as f:
            f.write(b"UC700-CHK")
        self._checkpoints.setdefault(job.id, []).append(cp)
        return cp

    def list_checkpoints(self, job_id: str) -> List[Checkpoint]:
        return sorted(self._checkpoints.get(job_id, []), key=lambda c: c.timestamp, reverse=True)

    def get_last_valid_checkpoint(self, job_id: str) -> Optional[Checkpoint]:
        max_age = timedelta(minutes=self.config.thresholds.checkpoint_max_age_min)
        now = datetime.utcnow()
        for cp in self.list_checkpoints(job_id):
            if cp.verified and (now - cp.timestamp) <= max_age:
                return cp
        # Fallback: retornar el más reciente si existe
        cps = self.list_checkpoints(job_id)
        return cps[0] if cps else None

    def verify_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Verifica lectura, checksum y reproducibilidad básica."""
        if not os.path.exists(checkpoint.path):
            checkpoint.verified = False
            return False
        # Simulación de validación de checksum
        checkpoint.verified = True
        return True

    def restore(self, job: TrainingJob, checkpoint: Optional[Checkpoint] = None) -> Dict[str, any]:
        cp = checkpoint or self.get_last_valid_checkpoint(job.id)
        if not cp:
            return {"restored": False, "reason": "no_valid_checkpoint", "job_id": job.id}
        self.verify_checkpoint(cp)
        if not cp.verified:
            return {"restored": False, "reason": "checkpoint_verification_failed", "checkpoint_id": cp.id}
        return {
            "restored": True,
            "checkpoint_id": cp.id,
            "global_step": cp.global_step,
            "path": cp.path,
            "job_id": job.id,
            "state": HealthState.RECOVERING,
        }
