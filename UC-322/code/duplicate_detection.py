"""Detección de trabajo duplicado y bloqueos.

Previene que dos agentes trabajen en la misma tarea simultáneamente
y detecta deadlocks cuando los agentes se esperan mutuamente.

Mecanismos:
1. TaskRegistry: registry de tareas activas con fingerprints.
2. DuplicateDetection: detecta si una tarea nueva coincide con una activa.
3. DeadlockDetector: detecta ciclos de espera entre agentes.
4. ProgressTracker: verifica que los agentes hacen progreso (no stall).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from conflict_models import (
    Conflict,
    ConflictType,
    ConflictSeverity,
    ResolutionStatus,
)


@dataclass
class TaskRecord:
    """Registro de una tarea activa o completada."""
    task_id: str
    agent_id: str
    domain: str
    description: str
    fingerprint: str  # Hash de la descripción para detección de duplicados
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "active"  # active, completed, failed, stalled
    last_progress_at: float = field(default_factory=time.time)
    waiting_for: Optional[str] = None  # agent_id que está esperando

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def duration(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "domain": self.domain,
            "description": self.description,
            "fingerprint": self.fingerprint,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "last_progress_at": self.last_progress_at,
            "waiting_for": self.waiting_for,
            "duration": round(self.duration, 4),
        }


@dataclass
class DeadlockInfo:
    """Información sobre un deadlock detectado."""
    cycle: List[str]  # agent_ids en el ciclo
    tasks_involved: List[str]
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle": self.cycle,
            "tasks_involved": self.tasks_involved,
            "detected_at": self.detected_at,
        }


class DuplicateDetection:
    """Detecta trabajo duplicado entre agentes.

    Usa fingerprints (hash de descripción) para detectar si dos
    agentes están trabajando en la misma tarea.
    """

    SIMILARITY_THRESHOLD = 0.85  # Similitud mínima para considerar duplicado

    def __init__(self) -> None:
        self._task_registry: Dict[str, TaskRecord] = {}
        self._fingerprint_index: Dict[str, List[str]] = {}  # fingerprint -> [task_ids]

    def register_task(
        self,
        task_id: str,
        agent_id: str,
        domain: str,
        description: str,
    ) -> Tuple[bool, Optional[Conflict]]:
        """Registra una tarea y verifica si hay duplicados.

        Args:
            task_id: ID único de la tarea.
            agent_id: ID del agente que toma la tarea.
            domain: Dominio de la tarea.
            description: Descripción de la tarea.

        Returns:
            (registered, conflict_if_duplicate)
        """
        fingerprint = self._compute_fingerprint(description)

        # Verificar duplicados
        duplicate = self._find_duplicate(fingerprint, domain, agent_id)

        if duplicate:
            conflict = Conflict(
                conflict_type=ConflictType.DUPLICATE_WORK,
                severity=ConflictSeverity.MEDIUM,
                domain=domain,
                agents_involved=[agent_id, duplicate.agent_id],
                description=f"Trabajo duplicado: '{description[:50]}' coincide con tarea {duplicate.task_id}",
                context={
                    "new_task_id": task_id,
                    "existing_task_id": duplicate.task_id,
                    "fingerprint": fingerprint,
                },
                resolution_status=ResolutionStatus.DETECTED,
            )
            return False, conflict

        # Registrar tarea
        record = TaskRecord(
            task_id=task_id,
            agent_id=agent_id,
            domain=domain,
            description=description,
            fingerprint=fingerprint,
        )
        self._task_registry[task_id] = record

        if fingerprint not in self._fingerprint_index:
            self._fingerprint_index[fingerprint] = []
        self._fingerprint_index[fingerprint].append(task_id)

        return True, None

    def _find_duplicate(
        self,
        fingerprint: str,
        domain: str,
        agent_id: str,
    ) -> Optional[TaskRecord]:
        """Busca una tarea duplicada activa."""
        for record in self._task_registry.values():
            if not record.is_active:
                continue
            if record.domain != domain:
                continue
            if record.agent_id == agent_id:
                continue  # Mismo agente, no es duplicado
            if record.fingerprint == fingerprint:
                return record
        return None

    def _compute_fingerprint(self, description: str) -> str:
        """Computa un fingerprint normalizado de la descripción."""
        normalized = description.lower().strip()
        # Remover palabras comunes que no afectan la semántica
        stop_words = {"the", "a", "an", "el", "la", "los", "las", "de", "for", "to"}
        words = [w for w in normalized.split() if w not in stop_words]
        normalized = " ".join(sorted(words))
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def complete_task(self, task_id: str, status: str = "completed") -> None:
        """Marca una tarea como completada."""
        if task_id in self._task_registry:
            record = self._task_registry[task_id]
            record.status = status
            record.completed_at = time.time()

    def update_progress(self, task_id: str) -> None:
        """Actualiza el timestamp de progreso de una tarea."""
        if task_id in self._task_registry:
            self._task_registry[task_id].last_progress_at = time.time()

    def get_active_tasks(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna las tareas activas."""
        tasks = [r for r in self._task_registry.values() if r.is_active]
        if domain:
            tasks = [t for t in tasks if t.domain == domain]
        return [t.to_dict() for t in tasks]


class DeadlockDetector:
    """Detecta deadlocks entre agentes.

    Un deadlock ocurre cuando:
    - Agente A espera a Agente B (waiting_for)
    - Agente B espera a Agente A (waiting_for)
    - Ninguno hace progreso

    Usa detección de ciclos en el grafo de espera.
    """

    STALL_TIMEOUT_SECONDS = 30.0  # Tiempo sin progreso para considerar stall

    def __init__(self) -> None:
        self._waiting_graph: Dict[str, str] = {}  # agent_id -> waiting_for
        self._task_registry: Dict[str, TaskRecord] = {}

    def set_waiting(self, agent_id: str, waiting_for: str, task_id: str) -> None:
        """Registra que un agente está esperando a otro."""
        self._waiting_graph[agent_id] = waiting_for
        if task_id in self._task_registry:
            self._task_registry[task_id].waiting_for = waiting_for

    def clear_waiting(self, agent_id: str) -> None:
        """Limpia el estado de espera de un agente."""
        self._waiting_graph.pop(agent_id, None)

    def detect_cycle(self) -> Optional[DeadlockInfo]:
        """Detecta un ciclo en el grafo de espera (deadlock).

        Usa DFS para encontrar ciclos.
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            neighbor = self._waiting_graph.get(node)
            if neighbor:
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Ciclo encontrado
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:]

            path.pop()
            rec_stack.discard(node)
            return None

        for node in self._waiting_graph:
            if node not in visited:
                cycle = dfs(node)
                if cycle:
                    tasks = [
                        tid for tid, r in self._task_registry.items()
                        if r.agent_id in cycle
                    ]
                    return DeadlockInfo(cycle=cycle, tasks_involved=tasks)

        return None

    def detect_stall(
        self,
        task_records: Dict[str, TaskRecord],
    ) -> List[Conflict]:
        """Detecta tareas que no han hecho progreso recientemente."""
        now = time.time()
        conflicts: List[Conflict] = []

        for task_id, record in task_records.items():
            if not record.is_active:
                continue
            stall_time = now - record.last_progress_at
            if stall_time > self.STALL_TIMEOUT_SECONDS:
                conflict = Conflict(
                    conflict_type=ConflictType.DEADLOCK,
                    severity=ConflictSeverity.HIGH,
                    domain=record.domain,
                    agents_involved=[record.agent_id],
                    description=f"Tarea {task_id} stall por {stall_time:.1f}s",
                    context={
                        "task_id": task_id,
                        "stall_time": stall_time,
                        "agent_id": record.agent_id,
                    },
                    resolution_status=ResolutionStatus.DETECTED,
                )
                conflicts.append(conflict)

        return conflicts

    def get_waiting_graph(self) -> Dict[str, str]:
        """Retorna el grafo de espera actual."""
        return dict(self._waiting_graph)
