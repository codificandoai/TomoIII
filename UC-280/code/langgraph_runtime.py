"""Real LangGraph runtime for the production goal execution lifecycle."""
from __future__ import annotations

from typing import Any, Dict, TypedDict

from langgraph.graph import END, START, StateGraph

from executor import DAGExecutor
from models import ExecutionSummary, Goal


class WorkflowState(TypedDict, total=False):
    goal: Goal
    execution: ExecutionSummary
    metadata: Dict[str, Any]


class LangGraphRuntime:
    """Compile and invoke a LangGraph StateGraph around the validated DAG executor."""

    def __init__(self, executor: DAGExecutor) -> None:
        self.executor = executor
        graph = StateGraph(WorkflowState)
        graph.add_node("validate", self._validate)
        graph.add_node("execute_parallel_dag", self._execute)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "validate")
        graph.add_edge("validate", "execute_parallel_dag")
        graph.add_edge("execute_parallel_dag", "finalize")
        graph.add_edge("finalize", END)
        self.graph = graph.compile()

    @staticmethod
    def _validate(state: WorkflowState) -> WorkflowState:
        from planners import validate_dag
        validate_dag(state["goal"])
        return {"metadata": {"runtime": "langgraph", "validated": True}}

    def _execute(self, state: WorkflowState) -> WorkflowState:
        return {"execution": self.executor.execute(state["goal"])}

    @staticmethod
    def _finalize(state: WorkflowState) -> WorkflowState:
        metadata = dict(state.get("metadata", {}))
        metadata["finalized"] = True
        return {"metadata": metadata}

    def invoke(self, goal: Goal) -> ExecutionSummary:
        result = self.graph.invoke({"goal": goal, "metadata": {}})
        return result["execution"]