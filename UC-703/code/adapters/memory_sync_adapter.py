"""
UC-703 — Memory Sync Adapter.

Sincroniza el estado de ejecución de larga duración con la memoria del agente
(UC-326/296). No implementa memoria por sí mismo; actúa como puente entre
Temporal/workflows y los stores de conocimiento del agente.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class MemorySyncAdapter:
    """
    Adapter para sincronizar estado del runtime con memoria AGI.

    - `write_episode`: escribe un episodio (objetivo, plan, resultado) en la
      memoria episódica del agente.
    - `read_context`: recupera contexto relevante para un objetivo.
    - `update_working_memory`: actualiza memoria de trabajo con pasos completados.
    """

    write_episode_fn: Optional[Callable[[Dict[str, Any]], None]] = None
    read_context_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None
    update_working_memory_fn: Optional[Callable[[str, Dict[str, Any]], None]] = None
    _episodes: List[Dict[str, Any]] = field(default_factory=list)
    _working_memory: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def write_episode(self, objective_id: str, objective: str, outcome: str, metadata: Dict[str, Any]) -> None:
        episode = {
            "objective_id": objective_id,
            "objective": objective,
            "outcome": outcome,
            "metadata": metadata,
            "timestamp": time.time(),
        }
        self._episodes.append(episode)
        if self.write_episode_fn:
            try:
                self.write_episode_fn(episode)
            except Exception:
                pass

    def read_context(self, objective_description: str) -> List[Dict[str, Any]]:
        if self.read_context_fn:
            try:
                return self.read_context_fn(objective_description)
            except Exception:
                pass
        # Fallback: retorna episodios con palabras clave en común.
        words = set(objective_description.lower().split())
        return [e for e in self._episodes if words & set(str(e.get("objective", "")).lower().split())]

    def update_working_memory(self, objective_id: str, update: Dict[str, Any]) -> None:
        self._working_memory.setdefault(objective_id, {}).update(update)
        if self.update_working_memory_fn:
            try:
                self.update_working_memory_fn(objective_id, update)
            except Exception:
                pass

    def get_working_memory(self, objective_id: str) -> Dict[str, Any]:
        return self._working_memory.get(objective_id, {})
