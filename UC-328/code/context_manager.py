"""
UC-328 — Gestor de Contexto Persistente para ORQUESTA-R.

Implementa versionado semántico de contexto, ventana deslizante y
archivo simplificado. En producción, esto se respaldaría con Redis,
vector DB y blob storage.
"""

from typing import Dict, List, Optional, Any
import time
import hashlib

from orquesta_models import ContextVersion


class ContextManager:
    """
    Gestiona contexto persistente y versionado.

    - Cada actualización crea una nueva versión con ID único.
    - Se mantiene una ventana deslizante de versiones recientes.
    - Las versiones antiguas se "archivan" simuladamente.
    """

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._versions: List[ContextVersion] = []
        self._current_context: Dict[str, Any] = {}
        self._archived_count: int = 0

    def load(self) -> Dict[str, Any]:
        """Carga contexto actual."""
        return dict(self._current_context)

    def update(
        self,
        delta: Dict[str, Any],
        dependencies: Optional[List[str]] = None,
    ) -> ContextVersion:
        """
        Actualiza el contexto con un delta y crea una nueva versión.

        Retorna la versión creada.
        """
        parent_id = self._versions[-1].version_id if self._versions else None
        version = ContextVersion(
            parent_version_id=parent_id,
            delta=dict(delta),
            timestamp=time.time(),
            dependencies=dependencies or [],
        )

        # Apply delta to current context
        self._current_context.update(delta)
        self._versions.append(version)

        # Sliding window
        if len(self._versions) > self.window_size:
            removed = self._versions.pop(0)
            self._archived_count += 1

        return version

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor del contexto actual."""
        return self._current_context.get(key, default)

    def get_current_version_id(self) -> Optional[str]:
        """Retorna ID de la versión actual."""
        if self._versions:
            return self._versions[-1].version_id
        return None

    def get_versions(self, limit: int = 20) -> List[ContextVersion]:
        """Retorna últimas versiones."""
        return self._versions[-limit:]

    def diff(self, key: str, since_version_id: Optional[str] = None) -> Any:
        """Calcula diferencia de un valor desde una versión anterior."""
        if not since_version_id or not self._versions:
            return self._current_context.get(key)

        start_index = -1
        for i, v in enumerate(self._versions):
            if v.version_id == since_version_id:
                start_index = i
                break
        if start_index == -1:
            return self._current_context.get(key)

        # Apply deltas from start_index to current
        value = None
        for v in self._versions[start_index:]:
            if key in v.delta:
                value = v.delta[key]
        return value

    def snapshot(self) -> Dict[str, Any]:
        """Retorna snapshot completo del contexto actual."""
        return dict(self._current_context)

    def reset(self) -> None:
        """Limpia contexto y versiones."""
        self._current_context.clear()
        self._versions.clear()
        self._archived_count = 0

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del contexto."""
        return {
            "current_keys": len(self._current_context),
            "versions_in_memory": len(self._versions),
            "archived_versions": self._archived_count,
            "current_version_id": self.get_current_version_id(),
        }
