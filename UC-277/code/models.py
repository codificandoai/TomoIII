"""Modelos de datos para UC-277 — Memoria Multi-Turno a Largo Plazo.

5 capas de memoria inspiradas en cogni-ciencia:
- Working Memory: contexto activo (segundos/minutos)
- Episodic Memory: eventos especificos (dias/meses)
- Semantic Memory: conocimiento general, hechos, preferencias (permanente)
- Procedural Memory: estrategias y habilidades aprendidas (permanente)
- Goal Memory: metas a largo plazo con tracking de progreso

Inspirado en:
- mem0ai/mem0: capa de memoria universal persistente.
- jojopdq/HiMem: memoria jerarquica a largo plazo.
- agiresearch/A-mem: memoria agenticaja dinamica.
- aiming-lab/SimpleMem: Store -> Index -> Retrieve.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enumeraciones
# ============================================================

class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    GOAL = "goal"


class MemoryImportance(str, Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


IMPORTANCE_WEIGHTS = {
    MemoryImportance.TRIVIAL: 0.1,
    MemoryImportance.LOW: 0.3,
    MemoryImportance.MEDIUM: 0.6,
    MemoryImportance.HIGH: 0.85,
    MemoryImportance.CRITICAL: 1.0,
}


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class ConsolidationResult(str, Enum):
    RETAINED = "retained"
    CONSOLIDATED = "consolidated"
    FORGOTTEN = "forgotten"
    UPGRADED = "upgraded"


# ============================================================
# Working Memory
# ============================================================

@dataclass
class WorkingMemoryItem:
    """Item en memoria de trabajo."""
    key: str
    content: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    priority: float = 0.5


# ============================================================
# Episodic Memory
# ============================================================

class EpisodicMemory(BaseModel):
    """Episodio: evento especifico con contexto completo."""
    episode_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    agent_id: str
    session_id: str = ""
    episode_type: str = "interaction"
    timestamp: float = Field(default_factory=time.time)
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    importance: MemoryImportance = MemoryImportance.MEDIUM
    outcome_sentiment: float = Field(ge=-1.0, le=1.0, default=0.0)
    metrics: Dict[str, float] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    access_count: int = 0
    last_accessed: float = Field(default_factory=time.time)

    def content_hash(self) -> str:
        payload = f"{self.summary}:{self.agent_id}:{self.episode_type}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ============================================================
# Semantic Memory
# ============================================================

@dataclass
class SemanticNode:
    """Nodo en el grafo de conocimiento semantico."""
    node_id: str
    agent_id: str
    node_type: str  # fact, preference, concept, entity
    content: str
    embedding: List[float] = field(default_factory=list)
    confidence: float = 0.8
    created_at: float = field(default_factory=time.time)
    last_validated: float = field(default_factory=time.time)
    source_episodes: List[str] = field(default_factory=list)


@dataclass
class SemanticEdge:
    """Relacion en el grafo semantico."""
    source_id: str
    target_id: str
    relation: str
    strength: float = 0.5
    evidence_count: int = 1


# ============================================================
# Procedural Memory
# ============================================================

@dataclass
class ProceduralSkill:
    """Habilidad/estrategia aprendida."""
    skill_id: str
    agent_id: str
    name: str
    description: str
    category: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    avg_outcome_score: float = 0.5
    applicable_when: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    version: int = 1

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5

    @property
    def mastery_level(self) -> str:
        total = self.success_count + self.failure_count
        if total < 5:
            return "novice"
        elif self.success_rate < 0.5:
            return "struggling"
        elif total < 20:
            return "competent"
        elif self.success_rate < 0.8:
            return "proficient"
        return "expert"


# ============================================================
# Goal Memory
# ============================================================

@dataclass
class Goal:
    """Meta a largo plazo con tracking de progreso."""
    goal_id: str
    agent_id: str
    title: str
    description: str
    status: GoalStatus = GoalStatus.ACTIVE
    progress: float = 0.0  # 0.0 - 1.0
    priority: float = 0.5
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    sub_goals: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    related_episodes: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)
