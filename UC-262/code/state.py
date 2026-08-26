"""Esquema de estado del grafo LangGraph para UC-262."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class GenericAIState(TypedDict):
    """Estado cognitivo avanzado del copiloto genérico."""

    request: Dict[str, Any]
    user_id: str
    thread_id: str
    memory_context: Dict[str, Any]
    beliefs: Annotated[List[Dict[str, Any]], operator.add]
    desires: List[Dict[str, Any]]
    intentions: List[Dict[str, Any]]
    reasoning_chain: Annotated[List[str], operator.add]
    population: List[Dict[str, Any]]
    generation: int
    best_candidate: Optional[Dict[str, Any]]
    self_critique: str
    human_feedback: str
    approved_alternative: str
    final_plan: List[Dict[str, Any]]
    itinerary: List[Dict[str, Any]]
    reflections: Annotated[List[Dict[str, Any]], operator.add]
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
    evolution_stats: Dict[str, Any]
    audit_trail: Annotated[List[Dict[str, Any]], operator.add]
