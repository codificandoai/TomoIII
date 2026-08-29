"""Application service exposing decompose, execute, resume and inspect operations."""
from __future__ import annotations

from executor import DAGExecutor, AgentRegistry, build_default_registry
from langgraph_runtime import LangGraphRuntime
from models import ExecutionSummary, Goal, PlannerType
from planners import decompose, topological_waves
from store import GoalStore


class GoalOrchestrator:
    def __init__(self, store: GoalStore | None = None, agents: AgentRegistry | None = None,
                 max_workers: int = 8) -> None:
        self.store = store or GoalStore()
        self.agents = agents or build_default_registry()
        self.executor = DAGExecutor(self.agents, max_workers, self.store.save)
        self.langgraph = LangGraphRuntime(self.executor)

    def create_plan(self, description: str, context: dict | None = None,
                    planner: PlannerType = PlannerType.LANGGRAPH) -> Goal:
        goal = decompose(description, context, planner)
        self.store.save(goal)
        return goal

    def execute(self, goal_id: str) -> ExecutionSummary:
        goal = self.store.get(goal_id)
        summary = self.langgraph.invoke(goal) if goal.planner == PlannerType.LANGGRAPH else self.executor.execute(goal)
        self.store.save(goal)
        return summary

    def plan_view(self, goal_id: str) -> dict:
        goal = self.store.get(goal_id)
        return {"goal": goal.public_dict(), "waves": [[t.id for t in wave] for wave in topological_waves(goal)],
                "events": self.store.events(goal_id)}