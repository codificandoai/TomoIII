"""UC-317 — Memory Manager: memoria corto/largo plazo para agentes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    agent_id: str
    role: str
    content: str
    source: str = "conversation"  # conversation, tool, observation, reflection
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """Gestor de memoria por agente."""

    def __init__(self) -> None:
        self._short_term: Dict[str, List[MemoryEntry]] = {}
        self._long_term: Dict[str, List[MemoryEntry]] = {}

    def add(
        self,
        agent_id: str,
        content: str,
        role: str = "assistant",
        source: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None,
        long_term: bool = False,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            agent_id=agent_id,
            role=role,
            content=content,
            source=source,
            metadata=metadata or {},
        )
        target = self._long_term if long_term else self._short_term
        target.setdefault(agent_id, []).append(entry)
        return entry

    def get_context(
        self,
        agent_id: str,
        short_term_limit: int = 10,
        long_term_limit: int = 5,
    ) -> List[Dict[str, str]]:
        """Retorna mensajes formateados para un LLM."""
        short = self._short_term.get(agent_id, [])[-short_term_limit:]
        long = self._long_term.get(agent_id, [])[-long_term_limit:]
        messages: List[Dict[str, str]] = []
        for entry in long + short:
            messages.append({"role": entry.role, "content": entry.content})
        return messages

    def retrieve(
        self,
        agent_id: str,
        query: str,
        top_k: int = 3,
    ) -> List[MemoryEntry]:
        """Recuperación simple por keyword (fallback sin embeddings)."""
        import re as _re
        query_terms = set(_re.findall(r"\w+", query.lower()))
        all_entries = self._short_term.get(agent_id, []) + self._long_term.get(agent_id, [])
        scored = []
        for entry in all_entries:
            terms = set(_re.findall(r"\w+", entry.content.lower()))
            score = len(query_terms & terms)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def clear(self, agent_id: str) -> None:
        self._short_term.pop(agent_id, None)
        self._long_term.pop(agent_id, None)
