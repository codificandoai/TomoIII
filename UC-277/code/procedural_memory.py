"""ProceduralMemory — Habilidades y estrategias para UC-277.

Memoria procedural: estrategias aprendidas que se refinan con el uso.
- Learning: aprende nuevas habilidades.
- Update: actualiza stats tras cada uso (EMA).
- Refine: modifica parametros desde autorreflexion.
- Retrieve: recupera mejor habilidad para un contexto.

Inspirado en nuster1128/MemEngine: biblioteca modular para memoria de agentes.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from embeddings import SimpleEmbeddingModel
from models import ProceduralSkill


class ProceduralMemory:
    """Memoria procedural: estrategias y habilidades aprendidas."""

    def __init__(self, embedding_model: SimpleEmbeddingModel,
                 ema_alpha: float = 0.3) -> None:
        self.embedding_model = embedding_model
        self.ema_alpha = ema_alpha
        self.skills: Dict[str, ProceduralSkill] = {}

    def learn_skill(self, agent_id: str, name: str, description: str,
                    category: str, parameters: Dict[str, Any],
                    applicable_when: Optional[List[str]] = None,
                    initial_success: bool = True) -> str:
        """Aprende nueva habilidad."""
        skill_id = f"{agent_id}:skill:{uuid4().hex[:10]}"
        embedding = self.embedding_model.encode(f"{name} {description}")
        skill = ProceduralSkill(
            skill_id=skill_id, agent_id=agent_id, name=name,
            description=description, category=category,
            parameters=parameters, applicable_when=applicable_when or [],
            embedding=embedding,
            success_count=1 if initial_success else 0,
            failure_count=0 if initial_success else 1,
        )
        self.skills[skill_id] = skill
        return skill_id

    def update_outcome(self, skill_id: str, success: bool, outcome_score: float) -> None:
        """Actualiza stats tras uso (EMA para score)."""
        skill = self.skills.get(skill_id)
        if not skill:
            return
        if success:
            skill.success_count += 1
        else:
            skill.failure_count += 1
        skill.avg_outcome_score = (
            self.ema_alpha * outcome_score + (1 - self.ema_alpha) * skill.avg_outcome_score
        )
        skill.last_used = time.time()

    def refine_skill(self, skill_id: str, new_parameters: Dict[str, Any]) -> None:
        """Refina parametros de habilidad."""
        skill = self.skills.get(skill_id)
        if not skill:
            return
        skill.parameters.update(new_parameters)
        skill.version += 1

    def retrieve_best(self, agent_id: str, context: str,
                      category: Optional[str] = None,
                      top_k: int = 3) -> List[ProceduralSkill]:
        """Recupera mejores habilidades para un contexto."""
        context_emb = self.embedding_model.encode(context)
        candidates = []
        for skill in self.skills.values():
            if skill.agent_id != agent_id:
                continue
            if category and skill.category != category:
                continue
            if not skill.embedding:
                continue
            sim = self.embedding_model.similarity(context_emb, skill.embedding)
            score = sim * skill.success_rate * (0.5 + skill.avg_outcome_score)
            candidates.append((score, skill))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in candidates[:top_k]]

    def get_stats(self, agent_id: str) -> Dict[str, Any]:
        agent_skills = [s for s in self.skills.values() if s.agent_id == agent_id]
        if not agent_skills:
            return {"total_skills": 0}
        return {
            "total_skills": len(agent_skills),
            "avg_success_rate": round(
                sum(s.success_rate for s in agent_skills) / len(agent_skills), 4
            ),
            "by_mastery": {
                level: sum(1 for s in agent_skills if s.mastery_level == level)
                for level in ["novice", "struggling", "competent", "proficient", "expert"]
            },
        }
