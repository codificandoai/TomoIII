"""GoalMemory — Metas a largo plazo para UC-277.

Memoria de objetivos:
- Crear metas con deadlines y sub-goals.
- Tracking de progreso (0.0 - 1.0).
- Milestones con timestamps.
- Vinculacion con episodios y habilidades.
- Status lifecycle: active -> completed/abandoned/failed.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from models import Goal, GoalStatus


class GoalMemory:
    """Memoria de metas a largo plazo con tracking de progreso."""

    def __init__(self, max_active_goals: int = 20) -> None:
        self.max_active = max_active_goals
        self.goals: Dict[str, Goal] = {}

    def create_goal(self, agent_id: str, title: str, description: str,
                    priority: float = 0.5, deadline: Optional[float] = None,
                    sub_goals: Optional[List[str]] = None) -> str:
        """Crea nueva meta."""
        goal_id = f"{agent_id}:goal:{uuid4().hex[:10]}"
        goal = Goal(
            goal_id=goal_id, agent_id=agent_id, title=title,
            description=description, priority=priority,
            deadline=deadline, sub_goals=sub_goals or [],
        )
        self.goals[goal_id] = goal
        return goal_id

    def update_progress(self, goal_id: str, progress: float,
                        milestone: Optional[str] = None) -> None:
        """Actualiza progreso de una meta."""
        goal = self.goals.get(goal_id)
        if not goal:
            return
        goal.progress = min(1.0, max(0.0, progress))
        if milestone:
            goal.milestones.append({
                "description": milestone,
                "progress_at": goal.progress,
                "timestamp": time.time(),
            })
        if goal.progress >= 1.0:
            goal.status = GoalStatus.COMPLETED

    def update_status(self, goal_id: str, status: GoalStatus) -> None:
        """Cambia status de una meta."""
        goal = self.goals.get(goal_id)
        if goal:
            goal.status = status

    def link_episode(self, goal_id: str, episode_id: str) -> None:
        """Vincula episodio a una meta."""
        goal = self.goals.get(goal_id)
        if goal and episode_id not in goal.related_episodes:
            goal.related_episodes.append(episode_id)

    def link_skill(self, goal_id: str, skill_id: str) -> None:
        """Vincula habilidad a una meta."""
        goal = self.goals.get(goal_id)
        if goal and skill_id not in goal.related_skills:
            goal.related_skills.append(skill_id)

    def get_active_goals(self, agent_id: str) -> List[Goal]:
        """Retorna metas activas del agente."""
        return [
            g for g in self.goals.values()
            if g.agent_id == agent_id and g.status == GoalStatus.ACTIVE
        ]

    def get_all_goals(self, agent_id: str) -> List[Goal]:
        return [g for g in self.goals.values() if g.agent_id == agent_id]

    def get_overdue_goals(self, agent_id: str) -> List[Goal]:
        """Metas activas con deadline vencido."""
        now = time.time()
        return [
            g for g in self.goals.values()
            if g.agent_id == agent_id and g.status == GoalStatus.ACTIVE
            and g.deadline and g.deadline < now
        ]

    def get_stats(self, agent_id: str) -> Dict[str, Any]:
        agent_goals = [g for g in self.goals.values() if g.agent_id == agent_id]
        if not agent_goals:
            return {"total_goals": 0}
        by_status: Dict[str, int] = {}
        for g in agent_goals:
            by_status[g.status.value] = by_status.get(g.status.value, 0) + 1
        active = [g for g in agent_goals if g.status == GoalStatus.ACTIVE]
        return {
            "total_goals": len(agent_goals),
            "by_status": by_status,
            "avg_progress_active": round(
                sum(g.progress for g in active) / len(active), 4
            ) if active else 0.0,
        }
