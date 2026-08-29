"""Memoria Episódica de Reflexiones para UC-275.

Implementa:
- Almacenamiento de episodios de reflexión con indexación por tipo/causa.
- Extracción de patrones de éxito y fallo.
- Recuperación de episodios similares (similitud Jaccard + numérica).
- Lecciones aprendidas por tipo de acción.
- Estadísticas de rendimiento.

Inspirado en:
- Reflexion (Shinn et al., NeurIPS 2023): memoria dinámica de reflexiones.
- Self-Refine (Madaan et al., 2023): aprendizaje iterativo del feedback.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from models import (
    ActionTrace,
    ReflectionEpisode,
    ReflectionOutcome,
)


class ReflectionMemory:
    """
    Memoria episódica de reflexiones pasadas.
    Permite al agente aprender de errores y éxitos previos similares.
    """

    def __init__(self, max_episodes: int = 1000,
                 similarity_threshold: float = 0.7) -> None:
        self.episodes: deque[ReflectionEpisode] = deque(maxlen=max_episodes)
        self.success_patterns: List[Dict[str, Any]] = []
        self.failure_patterns: List[Dict[str, Any]] = []
        self.similarity_threshold = similarity_threshold

        self._by_action_type: Dict[str, List[str]] = defaultdict(list)
        self._by_cause: Dict[str, List[str]] = defaultdict(list)
        self._by_agent: Dict[str, List[str]] = defaultdict(list)

    def store(self, episode: ReflectionEpisode) -> None:
        """Almacena episodio y extrae patrones."""
        self.episodes.append(episode)

        self._by_action_type[episode.action.action_type].append(episode.episode_id)
        self._by_agent[episode.agent_id].append(episode.episode_id)

        if episode.root_cause:
            self._by_cause[episode.root_cause.category.value].append(episode.episode_id)

        if episode.final_outcome in (ReflectionOutcome.EXCELLENT, ReflectionOutcome.GOOD):
            self._extract_success_pattern(episode)
        elif episode.final_outcome in (ReflectionOutcome.POOR, ReflectionOutcome.FAILURE):
            self._extract_failure_pattern(episode)

    def recall_similar(self, current_action: ActionTrace,
                       top_k: int = 5) -> List[ReflectionEpisode]:
        """Recupera episodios similares al actual."""
        candidates = []
        episode_ids = self._by_action_type.get(current_action.action_type, [])

        for ep_id in episode_ids:
            episode = self._find_episode(ep_id)
            if episode:
                similarity = self._compute_similarity(current_action, episode.action)
                if similarity >= self.similarity_threshold:
                    candidates.append((similarity, episode))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in candidates[:top_k]]

    def get_lessons_learned(self, action_type: str) -> Dict[str, Any]:
        """Retorna lecciones aprendidas para un tipo de acción."""
        episodes = [
            ep for ep in self.episodes
            if ep.action.action_type == action_type
        ]

        if not episodes:
            return {"success_rate": 0.5, "common_causes": [], "advice": [], "total_episodes": 0}

        successes = sum(
            1 for e in episodes
            if e.final_outcome in (ReflectionOutcome.EXCELLENT, ReflectionOutcome.GOOD)
        )
        success_rate = successes / len(episodes)

        causes: Dict[str, int] = defaultdict(int)
        for e in episodes:
            if e.root_cause:
                causes[e.root_cause.category.value] += 1
        top_causes = sorted(causes.items(), key=lambda x: x[1], reverse=True)[:3]

        advice: List[str] = []
        for e in episodes:
            if e.refinements and e.final_score and e.final_score > 0.8:
                for r in e.refinements:
                    if r.net_benefit > 0.3:
                        advice.append(r.rationale)

        return {
            "success_rate": round(success_rate, 4),
            "common_causes": top_causes,
            "advice": list(set(advice))[:5],
            "total_episodes": len(episodes),
        }

    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Estadísticas de rendimiento de un agente."""
        episodes = [ep for ep in self.episodes if ep.agent_id == agent_id]
        if not episodes:
            return {"total_episodes": 0, "avg_score": 0.0, "success_rate": 0.0,
                    "total_iterations": 0, "improvement_rate": 0.0}

        scores = [ep.final_score for ep in episodes if ep.final_score is not None]
        successes = sum(
            1 for e in episodes
            if e.final_outcome in (ReflectionOutcome.EXCELLENT, ReflectionOutcome.GOOD)
        )
        total_iters = sum(e.iterations for e in episodes)

        improved = sum(
            1 for e in episodes
            if e.iterations > 0 and e.final_score is not None
            and e.final_score > e.evaluation.score
        )

        return {
            "total_episodes": len(episodes),
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "success_rate": round(successes / len(episodes), 4),
            "total_iterations": total_iters,
            "improvement_rate": round(improved / max(len(episodes), 1), 4),
        }

    def get_system_stats(self) -> Dict[str, Any]:
        """Estadísticas globales del sistema."""
        if not self.episodes:
            return {"total_episodes": 0, "avg_score": 0.0, "avg_iterations": 0.0,
                    "convergence_rate": 0.0, "memory_size": 0}

        scores = [ep.final_score for ep in self.episodes if ep.final_score is not None]
        iters = [ep.iterations for ep in self.episodes]
        converged = sum(
            1 for ep in self.episodes
            if ep.final_outcome in (ReflectionOutcome.EXCELLENT, ReflectionOutcome.GOOD)
        )

        agents = set(ep.agent_id for ep in self.episodes)

        return {
            "total_agents": len(agents),
            "total_episodes": len(self.episodes),
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "avg_iterations": round(sum(iters) / len(iters), 2) if iters else 0.0,
            "convergence_rate": round(converged / len(self.episodes), 4),
            "memory_size": len(self.episodes),
            "success_patterns": len(self.success_patterns),
            "failure_patterns": len(self.failure_patterns),
        }

    def _find_episode(self, episode_id: str) -> Optional[ReflectionEpisode]:
        return next((e for e in self.episodes if e.episode_id == episode_id), None)

    def _compute_similarity(self, a1: ActionTrace, a2: ActionTrace) -> float:
        """Similitud entre dos acciones: Jaccard sobre keys + numérica sobre values."""
        if a1.action_type != a2.action_type:
            return 0.0

        keys1 = set(a1.action_params.keys())
        keys2 = set(a2.action_params.keys())

        if not keys1 or not keys2:
            return 0.5

        num_sim = 0.0
        num_count = 0
        for k in keys1 & keys2:
            v1 = a1.action_params.get(k)
            v2 = a2.action_params.get(k)
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                if v1 == 0 and v2 == 0:
                    num_sim += 1.0
                else:
                    diff = abs(v1 - v2) / max(abs(v1), abs(v2), 1e-9)
                    num_sim += max(0, 1 - diff)
                num_count += 1

        jaccard = len(keys1 & keys2) / len(keys1 | keys2)
        num_score = num_sim / num_count if num_count > 0 else 0.5

        return 0.5 * jaccard + 0.5 * num_score

    def _extract_success_pattern(self, episode: ReflectionEpisode) -> None:
        self.success_patterns.append({
            "action_type": episode.action.action_type,
            "key_params": {
                k: v for k, v in episode.action.action_params.items()
                if isinstance(v, (int, float, str))
            },
            "score": episode.final_score,
            "timestamp": episode.action.timestamp,
        })

    def _extract_failure_pattern(self, episode: ReflectionEpisode) -> None:
        self.failure_patterns.append({
            "action_type": episode.action.action_type,
            "key_params": {
                k: v for k, v in episode.action.action_params.items()
                if isinstance(v, (int, float, str))
            },
            "cause": episode.root_cause.category.value if episode.root_cause else "unknown",
            "score": episode.final_score,
            "timestamp": episode.action.timestamp,
        })
