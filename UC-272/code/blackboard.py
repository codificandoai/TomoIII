"""Pizarra compartida (Shared Blackboard) para UC-272.

Patrón Blackboard con:
- Versionado automático de entradas.
- Filtrado por confianza y TTL.
- Suscripción a cambios por categoría.
- Historial completo de escrituras.

Inspirado en: claudioed/agent-blackboard, whiteducksoftware/flock, ryanstwrt/MABS.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from config import BlackboardConfig, get_config
from models import BlackboardEntry, KnowledgeCategory


class SharedBlackboard:
    """Pizarra compartida con concurrencia, versionado y suscripciones."""

    def __init__(self, config: BlackboardConfig | None = None) -> None:
        self.config = config or get_config().blackboard
        self._entries: Dict[str, List[BlackboardEntry]] = {}
        self._history: List[BlackboardEntry] = []
        self._subscribers: Dict[KnowledgeCategory, List[Callable]] = {}
        self._lock = threading.Lock()

    def write(self, entry: BlackboardEntry) -> BlackboardEntry:
        """Publica conocimiento en la pizarra."""
        with self._lock:
            if entry.key not in self._entries:
                self._entries[entry.key] = []

            # Versionar: incrementa versión de entradas previas con menor confianza
            for existing in self._entries[entry.key]:
                if existing.confidence < entry.confidence:
                    existing.version += 1

            self._entries[entry.key].append(entry)
            self._history.append(entry)

        self._notify(entry)
        return entry

    def read(self, key: str, min_confidence: float | None = None) -> Optional[BlackboardEntry]:
        """Lee la entrada más reciente y confiable para una clave."""
        mc = min_confidence if min_confidence is not None else self.config.min_confidence
        entries = self._entries.get(key, [])
        valid = [e for e in entries if e.confidence >= mc and not self._is_expired(e)]
        if not valid:
            return None
        return max(valid, key=lambda e: (e.confidence, e.timestamp.timestamp()))

    def read_category(self, category: KnowledgeCategory) -> List[BlackboardEntry]:
        """Lee todas las entradas activas de una categoría."""
        results = []
        for entries in self._entries.values():
            for e in entries:
                if e.category == category and not self._is_expired(e):
                    results.append(e)
        return results

    def subscribe(self, category: KnowledgeCategory, callback: Callable) -> None:
        """Suscribe un callback a cambios en una categoría."""
        self._subscribers.setdefault(category, []).append(callback)

    @property
    def history(self) -> List[BlackboardEntry]:
        return list(self._history)

    @property
    def entry_count(self) -> int:
        return sum(len(v) for v in self._entries.values())

    def _notify(self, entry: BlackboardEntry) -> None:
        for cb in self._subscribers.get(entry.category, []):
            try:
                cb(entry)
            except Exception:
                pass

    def _is_expired(self, entry: BlackboardEntry) -> bool:
        age = (datetime.utcnow() - entry.timestamp).total_seconds()
        return age > entry.ttl_seconds
