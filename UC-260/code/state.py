"""Esquema de estado del grafo LangGraph BDI para UC-260."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class BDIState(TypedDict):
    """Estado persistente del agente BDI a través de los nodos de LangGraph.

    Campos anotados con ``Annotated[..., operator.add]`` se acumulan en lugar
    de reemplazarse, permitiendo guardar un historial de reflexiones, creencias
    y logs entre iteraciones.
    """

    request: Dict[str, Any]
    itinerary: List[Dict[str, Any]]
    beliefs: Annotated[List[Dict[str, Any]], operator.add]
    desires: List[Dict[str, Any]]
    intentions: List[Dict[str, Any]]
    experiences: List[Dict[str, Any]]
    world_state: Dict[str, Any]
    reflections: Annotated[List[str], operator.add]
    logs: Annotated[List[Dict[str, Any]], operator.add]
    status: str
    final_output: Optional[Dict[str, Any]]
    error_count: int
    retry_count: int
    max_retries: int
    safety_flags: Annotated[List[str], operator.add]
    missing_info: List[str]
    user_confirmed: bool
    requires_confirmation: bool
