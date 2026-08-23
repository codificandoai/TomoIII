"""UC-702 — Checkpoint Manager para interrupción de instancias spot.

Adaptado de `UC-700/code/checkpoint_manager.py`: en lugar de checkpoints
de entrenamiento, aquí se usa para guardar el estado del workload que
corría en la instancia spot y para ejecutar scripts de limpieza antes de
que la nube retire el recurso (~120s de aviso en AWS).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("uc702-checkpoint")


class CheckpointRecord(dict):
    """Registro simple de checkpoint (dict-like) serializable a JSON."""


class CheckpointManager:
    """Gestiona checkpoints de estado ante interrupción y ejecuta scripts
    externos de checkpoint/cleanup (Python, Node.js, bash, etc.)."""

    def __init__(self, storage_path: str = os.path.join(os.sep, "tmp", "uc702-checkpoints")) -> None:
        self.storage_path = storage_path
        self._records: Dict[str, List[CheckpointRecord]] = {}
        os.makedirs(storage_path, exist_ok=True)

    def create_checkpoint(self, node_id: str, payload: Optional[Dict] = None) -> CheckpointRecord:
        now = datetime.now(timezone.utc)
        cp_id = f"{node_id}-cp-{now.strftime('%Y%m%d%H%M%S%f')}"
        path = os.path.join(self.storage_path, cp_id)
        os.makedirs(path, exist_ok=True)

        content = json.dumps(payload or {}, ensure_ascii=False, default=str)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with open(os.path.join(path, "state.json"), "w", encoding="utf-8") as f:
            f.write(content)

        record = CheckpointRecord(
            id=cp_id,
            node_id=node_id,
            path=path,
            timestamp=now.isoformat(),
            checksum=checksum,
        )
        self._records.setdefault(node_id, []).append(record)
        return record

    def list_checkpoints(self, node_id: str) -> List[CheckpointRecord]:
        return sorted(self._records.get(node_id, []), key=lambda r: r["timestamp"], reverse=True)

    def run_script(self, script_path: Optional[str], env_extra: Optional[Dict[str, str]] = None, timeout: float = 60.0) -> Optional[Dict]:
        """Ejecuta un script externo de checkpoint/cleanup (Python, Node.js
        o bash, detectado por extensión) y retorna su resultado. No lanza
        excepción si el script falla: se registra y se continúa, dado que
        el tiempo antes de la terminación es limitado (~120s en AWS)."""
        if not script_path:
            return None
        if not os.path.exists(script_path):
            logger.warning("script no encontrado: %s", script_path)
            return {"executed": False, "reason": "not_found", "script": script_path}

        interpreter = self._interpreter_for(script_path)
        cmd = interpreter + [script_path]
        env = dict(os.environ)
        env.update(env_extra or {})
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, env=env, check=False
            )
            return {
                "executed": True,
                "script": script_path,
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }
        except subprocess.SubprocessError as exc:
            logger.warning("fallo ejecutando script %s: %s", script_path, exc)
            return {"executed": False, "reason": str(exc), "script": script_path}

    @staticmethod
    def _interpreter_for(script_path: str) -> List[str]:
        ext = os.path.splitext(script_path)[1].lower()
        if ext == ".py":
            return ["python3"]
        if ext == ".js":
            return ["node"]
        if ext in (".sh", ""):
            return ["bash"]
        return []
