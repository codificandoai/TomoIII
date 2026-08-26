"""Esquema de estado del grafo LangGraph para UC-263."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class RLState(TypedDict):
    """Estado del agente de recomendación RL."""

    context: Dict[str, Any]
    state_description: str
    action: str
    reward: float
    q_value: float
    next_state_description: str
    episode: int
    max_episodes: int
    epsilon: float
    logs: Annotated[List[Dict[str, Any]], operator.add]
    recommendations: Annotated[List[Dict[str, Any]], operator.add]
    reflection: str
    status: str
    final_output: Optional[Dict[str, Any]]
    error_count: int
