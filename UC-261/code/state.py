"""Esquema de estado del grafo LangGraph adaptativo para UC-261."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class AdaptiveState(TypedDict):
    """Estado persistente del agente adaptativo."""

    request: Dict[str, Any]
    user_id: str
    profile: Dict[str, Any]
    itinerary: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    auto_actions: List[Dict[str, Any]]
    approval_actions: List[Dict[str, Any]]
    approved_action_ids: List[str]
    rejected_action_ids: List[str]
    beliefs: Annotated[List[Dict[str, Any]], operator.add]
    desires: List[Dict[str, Any]]
    intentions: List[Dict[str, Any]]
    experiences: Annotated[List[Dict[str, Any]], operator.add]
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
