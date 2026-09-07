"""
UC-326 — Memoria Episódica para MAQRI.

Almacena experiencias pasadas de búsqueda, permite detectar redundancia con
consultas recientes, y recuperar episodios similares para mejorar queries.
"""

from typing import List, Dict, Optional, Any
import time

from maqri_models import SearchEpisode, MemoryType, RetrievedDocument


class EpisodicMemory:
    """
    Memoria episódica del agente: diario de experiencias de búsqueda.

    Cada episodio registra: query original, query refinada, documentos
    recuperados, score de relevancia, información faltante, razón de
    fracaso, y timestamp.
    """

    def __init__(self):
        self._episodes: List[SearchEpisode] = []

    def add(self, episode: SearchEpisode) -> None:
        """Agrega un episodio a la memoria."""
        self._episodes.append(episode)

    def get_recent(self, n: int = 5) -> List[SearchEpisode]:
        """Retorna los últimos N episodios."""
        return self._episodes[-n:]

    def find_similar(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.5,
    ) -> List[SearchEpisode]:
        """
        Encuentra episodios similares al query usando similitud léxica.

        En producción, esto usaría embeddings semánticos.
        """
        query_words = set(query.lower().split())
        if not query_words:
            return []

        scored = []
        for ep in self._episodes:
            ep_words = set((ep.original_query + " " + ep.refined_query).lower().split())
            if not ep_words:
                continue
            intersection = len(query_words & ep_words)
            union = len(query_words | ep_words)
            score = intersection / union if union > 0 else 0.0
            if score >= threshold:
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]

    def is_redundant(
        self,
        query: str,
        window: int = 5,
        threshold: float = 0.8,
    ) -> bool:
        """
        Detecta si una query es redundante respecto a las consultas recientes.

        Retorna True si la similitud con alguna consulta reciente supera
        el umbral.
        """
        recent = self.get_recent(window)
        if not recent:
            return False

        query_words = set(query.lower().split())
        if not query_words:
            return False

        for ep in recent:
            ep_words = set(ep.refined_query.lower().split())
            if not ep_words:
                continue
            intersection = len(query_words & ep_words)
            union = len(query_words | ep_words)
            score = intersection / union if union > 0 else 0.0
            if score >= threshold:
                return True

        return False

    def get_failed_strategies(self, n: int = 10) -> List[str]:
        """Retorna razones de fracaso recientes para evitar repetirlas."""
        reasons = []
        for ep in self._episodes[-n:]:
            if ep.failure_reason:
                reasons.append(ep.failure_reason)
        return reasons

    def get_successful_queries(self, n: int = 5) -> List[str]:
        """Retorna queries refinadas recientes que tuvieron éxito."""
        queries = []
        for ep in reversed(self._episodes):
            if len(queries) >= n:
                break
            if ep.success and ep.relevance_score >= 0.7:
                queries.append(ep.refined_query)
        return queries

    def get_lessons_learned(self, n: int = 10) -> List[Dict[str, Any]]:
        """Extrae lecciones de episodios recientes."""
        lessons = []
        for ep in self._episodes[-n:]:
            if ep.failure_reason:
                lessons.append({
                    "query": ep.refined_query,
                    "failure": ep.failure_reason,
                    "missing": ep.missing_info,
                    "score": round(ep.relevance_score, 4),
                })
        return lessons

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de la memoria episódica."""
        total = len(self._episodes)
        if total == 0:
            return {"total": 0, "successes": 0, "failures": 0, "avg_score": 0.0}

        successes = sum(1 for ep in self._episodes if ep.success)
        avg_score = sum(ep.relevance_score for ep in self._episodes) / total
        return {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "avg_score": round(avg_score, 4),
        }

    def reset(self) -> None:
        """Limpia la memoria episódica."""
        self._episodes.clear()

    def __len__(self) -> int:
        return len(self._episodes)
