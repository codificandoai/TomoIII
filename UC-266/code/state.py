"""Esquema de estado del grafo LangGraph para UC-265."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class ModelBasedState(TypedDict):
    """Estado del agente basado en modelo probabilístico con MCTS y persistencia."""

    request: Dict[str, Any]
    world_model: Dict[str, Any]
    belief_state: Optional[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    simulations: Annotated[List[Dict[str, Any]], operator.add]
    evaluations: List[Dict[str, Any]]
    selected_plan: Optional[Dict[str, Any]]
    execution_result: Optional[Dict[str, Any]]
    observations: Annotated[List[Dict[str, Any]], operator.add]
    reflections: Annotated[List[Dict[str, Any]], operator.add]
    logs: Annotated[List[Dict[str, Any]], operator.add]
    status: str
    final_output: Optional[Dict[str, Any]]
    error_count: int
    retry_count: int
    max_retries: int
    safety_flags: Annotated[List[str], operator.add]
    missing_info: List[str]
    requires_confirmation: bool
