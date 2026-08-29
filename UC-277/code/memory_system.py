"""MultiLayerMemorySystem — Orquestador de las 5 capas de memoria para UC-277.

Integra las 5 capas y provee:
- Almacenamiento unificado (store interaction).
- Recall multi-capa (working + episodic + semantic + procedural + goals).
- Consolidacion: working -> episodic -> semantic.
- Estadisticas globales.

Inspirado en:
- mem0ai/mem0: capa de memoria universal.
- agiresearch/MemOS: unifica store/retrieve/manage.
- LangChain LangMem: Long-term Memory Store.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from config import get_config
from embeddings import SimpleEmbeddingModel
from episodic_store import EpisodicMemoryStore
from goal_memory import GoalMemory
from models import (
    EpisodicMemory,
    GoalStatus,
    MemoryImportance,
    MemoryType,
)
from procedural_memory import ProceduralMemory
from semantic_memory import SemanticMemory
from working_memory import WorkingMemory


class MultiLayerMemorySystem:
    """
    Sistema de memoria multi-capa completo.
    Orquesta working + episodic + semantic + procedural + goal.
    """

    def __init__(self, agent_id: str, db_path: str = ":memory:") -> None:
        config = get_config()
        self.agent_id = agent_id
        self.embedding_model = SimpleEmbeddingModel(dim=config.embedding.dimension)

        self.working = WorkingMemory(capacity=config.working.capacity)
        self.episodic = EpisodicMemoryStore(self.embedding_model, db_path=db_path)
        self.semantic = SemanticMemory(self.embedding_model, config.semantic.similarity_threshold)
        self.procedural = ProceduralMemory(self.embedding_model, config.procedural.ema_alpha)
        self.goals = GoalMemory(config.goal.max_active_goals)

    def store_interaction(self, summary: str, session_id: str = "",
                          episode_type: str = "interaction",
                          details: Optional[Dict] = None,
                          tags: Optional[List[str]] = None,
                          importance: MemoryImportance = MemoryImportance.MEDIUM,
                          sentiment: float = 0.0,
                          extract_facts: bool = True) -> str:
        """
        Almacena una interaccion en el sistema multi-capa.
        1. Guarda en memoria episodica.
        2. Actualiza working memory.
        3. Extrae hechos a memoria semantica (si habilitado).
        """
        # 1. Episodic
        episode = EpisodicMemory(
            agent_id=self.agent_id,
            session_id=session_id or self.working.session_id,
            episode_type=episode_type,
            summary=summary,
            details=details or {},
            tags=tags or [],
            importance=importance,
            outcome_sentiment=sentiment,
        )
        episode_id = self.episodic.store(episode)

        # 2. Working memory
        self.working.put(f"last_{episode_type}", summary, priority=0.7)
        self.working.put("last_interaction", summary, priority=0.5)

        # 3. Semantic extraction
        if extract_facts and importance in (MemoryImportance.HIGH, MemoryImportance.CRITICAL):
            self.semantic.add_fact(self.agent_id, summary, "fact", episode_id)

        return episode_id

    def recall(self, query: str, top_k: int = 5,
               layers: Optional[List[MemoryType]] = None) -> Dict[str, Any]:
        """
        Recall multi-capa: busca en todas las capas relevantes.
        Retorna resultados unificados.
        """
        layers = layers or [MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
        result: Dict[str, Any] = {"query": query}

        if MemoryType.WORKING in layers:
            result["working"] = self.working.get_context_snapshot()

        if MemoryType.EPISODIC in layers:
            episodes = self.episodic.recall_semantic(query, self.agent_id, top_k)
            result["episodic"] = [{
                "episode_id": ep.episode_id,
                "summary": ep.summary,
                "episode_type": ep.episode_type,
                "importance": ep.importance.value,
                "sentiment": ep.outcome_sentiment,
            } for ep in episodes]

        if MemoryType.SEMANTIC in layers:
            facts = self.semantic.query(self.agent_id, query, top_k)
            result["semantic"] = facts

        if MemoryType.PROCEDURAL in layers:
            skills = self.procedural.retrieve_best(self.agent_id, query, top_k=top_k)
            result["procedural"] = [{
                "skill_id": s.skill_id, "name": s.name,
                "success_rate": round(s.success_rate, 3),
                "mastery": s.mastery_level,
            } for s in skills]

        if MemoryType.GOAL in layers:
            active_goals = self.goals.get_active_goals(self.agent_id)
            result["goals"] = [{
                "goal_id": g.goal_id, "title": g.title,
                "progress": g.progress, "status": g.status.value,
            } for g in active_goals]

        return result

    def consolidate(self) -> Dict[str, int]:
        """
        Consolida memorias: extrae patrones de episodica -> semantica.
        Simula el proceso de consolidacion durante 'sueno'.
        """
        episodes = list(self.episodic.episodes.values())
        agent_eps = [ep for ep in episodes if ep.agent_id == self.agent_id]
        consolidated = 0
        for ep in agent_eps:
            if ep.importance in (MemoryImportance.HIGH, MemoryImportance.CRITICAL):
                self.semantic.add_fact(self.agent_id, ep.summary, "fact", ep.episode_id)
                consolidated += 1
        return {"episodes_processed": len(agent_eps), "consolidated_to_semantic": consolidated}

    def new_session(self) -> str:
        """Inicia nueva sesion, limpia working memory."""
        return self.working.new_session()

    def get_system_stats(self) -> Dict[str, Any]:
        """Estadisticas globales del sistema de memoria."""
        return {
            "agent_id": self.agent_id,
            "working_memory": self.working.get_context_snapshot(),
            "episodic": self.episodic.get_stats(self.agent_id),
            "semantic": self.semantic.get_stats(self.agent_id),
            "procedural": self.procedural.get_stats(self.agent_id),
            "goals": self.goals.get_stats(self.agent_id),
        }
