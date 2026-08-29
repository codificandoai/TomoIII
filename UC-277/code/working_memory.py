"""WorkingMemory — Memoria de trabajo para UC-277.

Contexto activo de la sesion actual:
- Capacidad limitada (7 +/- 2 items, patron Miller).
- Eviction por score = priority * recency.
- Vida: segundos/minutos.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from models import WorkingMemoryItem


class WorkingMemory:
    """Memoria de trabajo: contexto activo de la sesion actual."""

    def __init__(self, capacity: int = 7) -> None:
        self.capacity = capacity
        self.items: Dict[str, WorkingMemoryItem] = {}
        self.session_id: str = uuid4().hex[:16]
        self.session_start: float = time.time()

    def put(self, key: str, content: Any, priority: float = 0.5) -> None:
        """Agrega/actualiza item en memoria de trabajo."""
        if key in self.items:
            item = self.items[key]
            item.content = content
            item.last_accessed = time.time()
            item.access_count += 1
            item.priority = priority
        else:
            if len(self.items) >= self.capacity:
                self._evict()
            self.items[key] = WorkingMemoryItem(
                key=key, content=content, priority=priority
            )

    def get(self, key: str) -> Optional[Any]:
        """Recupera item y actualiza recencia."""
        item = self.items.get(key)
        if item:
            item.last_accessed = time.time()
            item.access_count += 1
            return item.content
        return None

    def remove(self, key: str) -> bool:
        if key in self.items:
            del self.items[key]
            return True
        return False

    def get_context_snapshot(self) -> Dict[str, Any]:
        """Snapshot del contexto activo."""
        return {
            "session_id": self.session_id,
            "session_duration_seconds": round(time.time() - self.session_start, 2),
            "items": {k: v.content for k, v in self.items.items()},
            "item_count": len(self.items),
            "capacity": self.capacity,
        }

    def clear(self) -> None:
        self.items.clear()

    def new_session(self) -> str:
        """Inicia nueva sesion, limpia contexto."""
        self.clear()
        self.session_id = uuid4().hex[:16]
        self.session_start = time.time()
        return self.session_id

    def _evict(self) -> None:
        """Eviction por score = priority * recency."""
        if not self.items:
            return
        now = time.time()
        scores = {
            k: item.priority * math.exp(-(now - item.last_accessed) / 3600)
            for k, item in self.items.items()
        }
        victim = min(scores, key=scores.get)
        del self.items[victim]
