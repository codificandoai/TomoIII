"""Pluggable LangGraph-style, TDAG and ReAcTree goal planners."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from models import Goal, PlannerType, Task, TaskPriority


class Planner(ABC):
    @abstractmethod
    def decompose(self, description: str, context: dict) -> Goal:
        raise NotImplementedError

    @staticmethod
    def _goal(description: str, context: dict, kind: PlannerType) -> Goal:
        if not description or not description.strip():
            raise ValueError("goal description is required")
        return Goal(description=description.strip(), context=context, planner=kind)


class LangGraphPlanner(Planner):
    """Production-oriented state graph: clarify -> research/design -> build -> verify -> deliver."""

    def decompose(self, description: str, context: dict) -> Goal:
        goal = self._goal(description, context, PlannerType.LANGGRAPH)
        specifications = [
            ("Clarify objective and acceptance criteria", ["planning"], TaskPriority.CRITICAL),
            ("Research constraints and available evidence", ["research"], TaskPriority.HIGH),
            ("Design execution plan and interfaces", ["architecture"], TaskPriority.CRITICAL),
            ("Execute the objective", ["execution"], TaskPriority.CRITICAL),
            ("Validate outputs against acceptance criteria", ["quality"], TaskPriority.HIGH),
            ("Synthesize and deliver final result", ["communication"], TaskPriority.MEDIUM),
        ]
        tasks = [Task(title, f"For goal: {description}", priority=priority,
                      required_capabilities=caps) for title, caps, priority in specifications]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[0].id]
        tasks[3].dependencies = [tasks[1].id, tasks[2].id]
        tasks[4].dependencies = [tasks[3].id]
        tasks[5].dependencies = [tasks[4].id]
        goal.tasks = {task.id: task for task in tasks}
        return goal


class TDAGPlanner(Planner):
    """Task-DAG planner emphasizing dynamic parallel branches and a synchronization join."""

    def decompose(self, description: str, context: dict) -> Goal:
        goal = self._goal(description, context, PlannerType.TDAG)
        scope = Task("Define scope", description, priority=TaskPriority.CRITICAL, required_capabilities=["planning"])
        branches = [
            Task("Analyze domain evidence", description, required_capabilities=["research"], dependencies=[scope.id]),
            Task("Analyze risks and constraints", description, required_capabilities=["risk"], dependencies=[scope.id]),
            Task("Prototype candidate solution", description, required_capabilities=["execution"], dependencies=[scope.id]),
        ]
        join = Task("Merge parallel branches", description, priority=TaskPriority.HIGH,
                    required_capabilities=["synthesis"], dependencies=[t.id for t in branches])
        validate = Task("Evaluate and repair merged plan", description, required_capabilities=["quality"], dependencies=[join.id])
        deliver = Task("Deliver objective result", description, required_capabilities=["communication"], dependencies=[validate.id])
        goal.tasks = {t.id: t for t in [scope, *branches, join, validate, deliver]}
        return goal


class ReAcTreePlanner(Planner):
    """Reason-Act tree represented as a DAG with alternative actions and evaluation."""

    def decompose(self, description: str, context: dict) -> Goal:
        goal = self._goal(description, context, PlannerType.REACTREE)
        reason = Task("Reason about objective", description, priority=TaskPriority.CRITICAL, required_capabilities=["reasoning"])
        actions = [
            Task("Execute primary action", description, required_capabilities=["execution"], dependencies=[reason.id], metadata={"branch": "primary"}),
            Task("Execute alternative action", description, priority=TaskPriority.LOW, required_capabilities=["execution"], dependencies=[reason.id], metadata={"branch": "alternative"}),
        ]
        evaluate = Task("Evaluate action branches", description, required_capabilities=["quality"], dependencies=[t.id for t in actions])
        reflect = Task("Reflect and select best result", description, required_capabilities=["reasoning"], dependencies=[evaluate.id])
        goal.tasks = {t.id: t for t in [reason, *actions, evaluate, reflect]}
        return goal


PLANNERS: Dict[PlannerType, Planner] = {
    PlannerType.LANGGRAPH: LangGraphPlanner(),
    PlannerType.TDAG: TDAGPlanner(),
    PlannerType.REACTREE: ReAcTreePlanner(),
}


def decompose(description: str, context: dict | None = None,
              planner: PlannerType = PlannerType.LANGGRAPH) -> Goal:
    goal = PLANNERS[planner].decompose(description, context or {})
    validate_dag(goal)
    return goal


def topological_waves(goal: Goal) -> List[List[Task]]:
    """Return parallel execution waves and reject cycles or missing dependencies."""
    validate_dag(goal)
    indegree = {task_id: len(task.dependencies) for task_id, task in goal.tasks.items()}
    dependents: Dict[str, List[str]] = {task_id: [] for task_id in goal.tasks}
    for task in goal.tasks.values():
        for dependency in task.dependencies:
            dependents[dependency].append(task.id)
    waves, ready, visited = [], sorted([k for k, degree in indegree.items() if degree == 0]), 0
    while ready:
        wave = sorted((goal.tasks[task_id] for task_id in ready), key=lambda t: (t.priority, t.id))
        waves.append(wave)
        next_ready = []
        for task in wave:
            visited += 1
            for child in dependents[task.id]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_ready.append(child)
        ready = sorted(next_ready)
    if visited != len(goal.tasks):
        raise ValueError("task graph contains a cycle")
    return waves


def validate_dag(goal: Goal) -> None:
    for task in goal.tasks.values():
        if task.id in task.dependencies:
            raise ValueError(f"task {task.id} cannot depend on itself")
        missing = [dep for dep in task.dependencies if dep not in goal.tasks]
        if missing:
            raise ValueError(f"task {task.id} has missing dependencies: {missing}")
    visiting, visited = set(), set()
    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError("task graph contains a cycle")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in goal.tasks[task_id].dependencies:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in goal.tasks:
        visit(task_id)