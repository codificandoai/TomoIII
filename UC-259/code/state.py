"""Esquema del estado del grafo LangGraph para UC-259."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict):
    """Estado persistente que viaja por los nodos del grafo.

    Campos anotados con ``Annotated[..., operator.add]`` se acumulan en lugar de
    ser reemplazados, lo que permite conservar un historial de reflexiones y
    logs entre iteraciones.
    """

    request: Dict[str, Any]
    itinerary: List[Dict[str, Any]]
    status: str
    world_state: Dict[str, Any]
    reflections: Annotated[List[str], operator.add]
    error_count: int
    retry_count: int
    max_retries: int
    final_output: Optional[Dict[str, Any]]
    safety_flags: Annotated[List[str], operator.add]
    missing_info: List[str]
    requires_confirmation: bool
    user_confirmed: bool
    logs: Annotated[List[Dict[str, Any]], operator.add]
