"""
UC-087 — Gestor de versiones y rollback de modelos.

Guarda versiones candidatas, canary y promocionadas; permite revertir a la
última versión conocida como segura.
"""

import json
import os
import shutil
import time
from typing import Dict, List, Optional, Any

from models_087 import ModelVersion


class RollbackManager:
    """
    Mantiene un registro de versiones de modelos en un directorio, con
    soporte para canary, promoción y rollback.
    """

    def __init__(self, models_dir: str = ".uc087_models", max_versions: int = 10):
        self.models_dir = models_dir
        self.max_versions = max_versions
        os.makedirs(self.models_dir, exist_ok=True)
        self.versions: List[ModelVersion] = []
        self._load_index()

    def _index_path(self) -> str:
        return os.path.join(self.models_dir, "versions.json")

    def _load_index(self) -> None:
        path = self._index_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.versions = [ModelVersion(**v) for v in raw]

    def _save_index(self) -> None:
        with open(self._index_path(), "w", encoding="utf-8") as f:
            json.dump([v.to_dict() for v in self.versions], f, indent=2)

    def _version_path(self, version_id: str) -> str:
        return os.path.join(self.models_dir, f"model_{version_id}.json")

    def save_candidate(
        self,
        model_state: Dict[str, Any],
        is_canary: bool = False,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> ModelVersion:
        """Guarda un modelo candidato y lo registra."""
        version = ModelVersion(
            timestamp=time.time(),
            path="",
            metrics=metrics or {},
            is_canary=is_canary,
        )
        path = self._version_path(version.version_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(model_state, f, indent=2)
        version.path = path
        self.versions.append(version)
        self._trim_versions()
        self._save_index()
        return version

    def _trim_versions(self) -> None:
        while len(self.versions) > self.max_versions:
            old = self.versions.pop(0)
            if old.path and os.path.exists(old.path):
                try:
                    os.remove(old.path)
                except Exception:
                    pass

    def promote(self, version_id: str) -> Optional[ModelVersion]:
        """Promociona una versión a producción."""
        for v in self.versions:
            if v.version_id == version_id:
                for other in self.versions:
                    other.promoted = False
                v.promoted = True
                v.is_canary = False
                self._save_index()
                return v
        return None

    def reject(self, version_id: str, reason: str) -> Optional[ModelVersion]:
        """Rechaza una versión candidata."""
        for v in self.versions:
            if v.version_id == version_id:
                v.rejected = True
                v.rejection_reason = reason
                self._save_index()
                return v
        return None

    def get_promoted(self) -> Optional[ModelVersion]:
        """Retorna la última versión promocionada."""
        promoted = [v for v in self.versions if v.promoted]
        return promoted[-1] if promoted else None

    def get_safe_version(self) -> Optional[ModelVersion]:
        """Retorna la última versión promocionada (para rollback)."""
        return self.get_promoted()

    def rollback(self, version_id: Optional[str] = None) -> Optional[ModelVersion]:
        """Revierte a una versión específica o a la última promocionada."""
        target = None
        if version_id:
            for v in self.versions:
                if v.version_id == version_id:
                    target = v
                    break
        if target is None:
            target = self.get_promoted()
        if target is None or not target.path or not os.path.exists(target.path):
            return None
        # Actualizar producción simulada
        for v in self.versions:
            v.promoted = False
        target.promoted = True
        self._save_index()
        return target

    def load_model_state(self, version_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Carga el estado de una versión."""
        if version_id is None:
            target = self.get_promoted()
            version_id = target.version_id if target else None
        if version_id is None:
            return None
        path = self._version_path(version_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_versions(self) -> List[Dict[str, Any]]:
        """Lista todas las versiones registradas."""
        return [v.to_dict() for v in self.versions]

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total": len(self.versions),
            "promoted": sum(1 for v in self.versions if v.promoted),
            "rejected": sum(1 for v in self.versions if v.rejected),
            "canary": sum(1 for v in self.versions if v.is_canary),
        }
