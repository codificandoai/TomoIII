"""Memoria a corto plazo: bloc de notas del agente (context window simulation)."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from memory_config import ShortTermMemoryConfig


@dataclass
class Note:
    note_id: str
    note_type: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_id": self.note_id,
            "note_type": self.note_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class ShortTermNotepad:
    """Bloc de notas volátil, rápido, con límite estricto de capacidad (FIFO)."""

    def __init__(self, config: Optional[ShortTermMemoryConfig] = None) -> None:
        self.config = config or ShortTermMemoryConfig()
        self._notes: deque = deque(maxlen=self.config.max_notes)
        self._counter = 0

    def store(
        self,
        content: str,
        note_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Note:
        self._counter += 1
        note = Note(
            note_id=f"note_{self._counter:03d}",
            note_type=note_type,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self._notes.append(note)
        return note

    def retrieve_latest(self, n: int = 5, note_type: Optional[str] = None) -> List[Note]:
        notes = list(self._notes)
        if note_type:
            notes = [n for n in notes if n.note_type == note_type]
        return notes[-n:]

    def retrieve_latest_text(self, n: int = 5, note_type: Optional[str] = None) -> str:
        notes = self.retrieve_latest(n=n, note_type=note_type)
        if not notes:
            return "Vacío"
        return " | ".join(f"{n.note_type}: {n.content}" for n in notes)

    def clear(self) -> None:
        self._notes.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity": self.config.max_notes,
            "size": len(self._notes),
            "notes": [n.to_dict() for n in self._notes],
        }
