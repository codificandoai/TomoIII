"""Motor de Q-Learning vectorial para UC-263.

Utiliza embeddings determinísticos para representar el estado y similitud del
 coseno para generalizar Q-values a contextos nunca vistos.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from config import AppConfig, RLLearningConfig
from models import RLExperience, TravelerContext, now_iso


class VectorQLearner:
    """Agente RL con memoria vectorial de experiencias y ecuación de Bellman."""

    _lock = threading.Lock()

    def __init__(self, config: Optional[RLLearningConfig] = None, memory_path: Optional[str] = None) -> None:
        self.config = config or RLLearningConfig()
        self.memory_path = memory_path or ""
        self.experiences: List[RLExperience] = []
        if self.memory_path and os.path.exists(self.memory_path):
            self._load_from_disk()

    def _embed(self, context: str) -> np.ndarray:
        """Genera un embedding determinista a partir del contexto."""
        seed = int(hashlib.sha256(context.encode("utf-8")).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.random(self.config.embedding_dim).astype(np.float64)
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    def get_q_value(self, state_context: str, action: str) -> float:
        """Devuelve el Q-value promedio ponderado por similitud del coseno.

        Si no hay experiencias para la acción, retorna 0.0 (estado inicial).
        """
        state_vec = self._embed(state_context).reshape(1, -1)
        action_experiences = [e for e in self.experiences if e.action == action]
        if not action_experiences:
            return 0.0

        memory_matrix = np.array([e.state_embedding for e in action_experiences])
        similarities = cosine_similarity(state_vec, memory_matrix)[0]

        # Top-k vecinos más similares
        k = min(self.config.k_neighbors, len(action_experiences))
        top_idx = np.argsort(similarities)[-k:]
        top_sim = similarities[top_idx]
        top_q = np.array([action_experiences[i].q_value for i in top_idx])

        weight_sum = np.sum(top_sim) + 1e-8
        weighted_q = np.sum(top_sim * top_q) / weight_sum
        return float(weighted_q)

    def get_all_q_values(self, state_context: str, actions: List[str]) -> Dict[str, float]:
        return {action: self.get_q_value(state_context, action) for action in actions}

    def choose_action(
        self,
        state_context: str,
        actions: List[str],
        epsilon: Optional[float] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> tuple:
        """Epsilon-greedy: explora con probabilidad epsilon, explota con 1-epsilon."""
        eps = epsilon if epsilon is not None else self.config.epsilon
        rng = rng or np.random.default_rng()
        if rng.random() < eps:
            action = rng.choice(actions).item()
            return action, True
        q_values = self.get_all_q_values(state_context, actions)
        best_q = max(q_values.values()) if q_values else 0.0
        best_actions = [a for a, q in q_values.items() if abs(q - best_q) < 1e-6]
        action = rng.choice(best_actions).item() if best_actions else actions[0]
        return action, False

    def update(
        self,
        state_context: str,
        action: str,
        reward: float,
        next_state_context: str,
        actions: List[str],
    ) -> float:
        """Actualiza Q(s,a) mediante la ecuación de Bellman y guarda la experiencia."""
        state_vec = self._embed(state_context)
        current_q = self.get_q_value(state_context, action)
        next_q_values = [self.get_q_value(next_state_context, a) for a in actions]
        max_future_q = max(next_q_values) if next_q_values else 0.0

        new_q = current_q + self.config.alpha * (
            reward + self.config.gamma * max_future_q - current_q
        )

        experience = RLExperience(
            state_context=state_context,
            state_embedding=state_vec.tolist(),
            action=action,
            reward=reward,
            q_value=new_q,
            next_state_context=next_state_context,
        )
        with self._lock:
            self.experiences.append(experience)
            self._persist()
        return float(new_q)

    def _persist(self) -> None:
        if not self.memory_path:
            return
        try:
            os.makedirs(os.path.dirname(self.memory_path) or ".", exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                for exp in self.experiences:
                    f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load_from_disk(self) -> None:
        try:
            with open(self.memory_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self.experiences.append(RLExperience.from_dict(data))
        except (json.JSONDecodeError, OSError):
            self.experiences = []

    def reset(self) -> None:
        with self._lock:
            self.experiences.clear()
            if self.memory_path and os.path.exists(self.memory_path):
                try:
                    os.remove(self.memory_path)
                except OSError:
                    pass

    def stats(self) -> Dict[str, Any]:
        return {
            "experiences": len(self.experiences),
            "actions": sorted(set(e.action for e in self.experiences)),
            "avg_q": round(
                float(np.mean([e.q_value for e in self.experiences])) if self.experiences else 0.0, 4
            ),
        }
