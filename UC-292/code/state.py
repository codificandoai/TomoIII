"""Esquema de estado del grafo LangGraph para UC-292."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class TradingAgentState(TypedDict):
    """Estado del agente de trading multi-agente con world model."""

    request: Dict[str, Any]
    snapshots: Optional[Dict[str, Any]]
    signals: List[Dict[str, Any]]
    juice_validations: List[Dict[str, Any]]
    approved_signals: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    simulations: Annotated[List[Dict[str, Any]], operator.add]
    evaluations: List[Dict[str, Any]]
    selected_strategy: Optional[Dict[str, Any]]
    risk_decision: Optional[Dict[str, Any]]
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
