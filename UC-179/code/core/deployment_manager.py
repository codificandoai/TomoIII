"""
Codificando.AI - UC-179
Gestor de despliegue: promueve un modelo validado a producción de forma
segura (respaldo del modelo anterior antes de sobrescribir) y permite
revertir (`rollback`) al último respaldo si el modelo recién desplegado
presenta problemas en producción.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union


class DeploymentManager:
    def __init__(self, knowledge_base, production_dir: Union[str, Path] = "models/production"):
        self.kb = knowledge_base
        self.production_dir = Path(production_dir)
        self.production_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.production_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.current_model_path = self.production_dir / "current_model.joblib"
        self.metadata_path = self.production_dir / "current_model.metadata.json"

    def deploy_model(self, model_path: Union[str, Path], version: str, metrics: Dict) -> Dict:
        """Respalda el modelo activo (si existe) y promueve `model_path`
        a producción, registrando el evento en la base de conocimiento."""
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"No se encontró el modelo a desplegar: {model_path}")

        backup_info = self._backup_current_model()

        shutil.copy2(model_path, self.current_model_path)
        metadata = {
            "version": version,
            "source_path": str(model_path),
            "metrics": metrics,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "previous_backup": backup_info,
        }
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.kb.mark_model_deployed(version)
        return metadata

    def _backup_current_model(self) -> Optional[Dict]:
        if not self.current_model_path.exists():
            return None

        current_metadata = self.get_active_deployment() or {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_model_path = self.backup_dir / f"model_{timestamp}.joblib"
        backup_metadata_path = self.backup_dir / f"model_{timestamp}.metadata.json"

        shutil.copy2(self.current_model_path, backup_model_path)
        backup_record = {
            **current_metadata,
            "backup_model_path": str(backup_model_path),
            "backup_metadata_path": str(backup_metadata_path),
        }
        with open(backup_metadata_path, "w", encoding="utf-8") as f:
            json.dump(backup_record, f, indent=2, ensure_ascii=False)

        return backup_record

    def get_active_deployment(self) -> Optional[Dict]:
        if not self.metadata_path.exists():
            return None
        with open(self.metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_backups(self) -> List[Dict]:
        backups = []
        for metadata_file in sorted(self.backup_dir.glob("*.metadata.json"), reverse=True):
            with open(metadata_file, "r", encoding="utf-8") as f:
                content = json.load(f)
            backups.append({"metadata_file": str(metadata_file), **content})
        return backups

    def rollback(self, backup_model_path: Optional[Union[str, Path]] = None) -> Dict:
        """Revierte al respaldo indicado, o al más reciente si no se
        especifica ninguno."""
        backups = self.list_backups()
        if not backups:
            raise RuntimeError("No hay respaldos disponibles para revertir")

        target = None
        if backup_model_path:
            target = next((b for b in backups if b["backup_model_path"] == str(backup_model_path)), None)
            if target is None:
                raise FileNotFoundError(f"Respaldo no encontrado: {backup_model_path}")
        else:
            target = backups[0]

        shutil.copy2(target["backup_model_path"], self.current_model_path)
        rollback_metadata = {k: v for k, v in target.items() if k != "metadata_file"}
        rollback_metadata["rolled_back_at"] = datetime.now(timezone.utc).isoformat()

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(rollback_metadata, f, indent=2, ensure_ascii=False)

        if rollback_metadata.get("version"):
            self.kb.mark_model_deployed(rollback_metadata["version"])

        return rollback_metadata
