"""
UC-328 — Wrapper de importación para módulos con guión en el nombre.

Permite: from uc328 import UCOrquestaRLayer
en lugar de importar directamente el módulo con guión.
"""

import importlib

_mod = importlib.import_module("UC-328")

UCOrquestaRLayer = _mod.UCOrquestaRLayer
default_sources = _mod.default_sources
demo = _mod.demo

from orchestrator import OrquestaREngine  # noqa: E402, F401
from orquesta_models import (  # noqa: E402, F401
    OrquestaConfig,
    OrquestaResult,
    Subquery,
    Source,
    PartialResult,
    ResolvedFact,
    ExecutionMetrics,
    Budget,
    CacheEntry,
    ContextVersion,
    HealthStatus,
    ExecutionVerdict,
    SubqueryStatus,
    SourceType,
    PrivacyPolicy,
)
from source_registry import SourceRegistry  # noqa: E402, F401
from schema_federation import SchemaFederation  # noqa: E402, F401
from query_router import QueryRouter  # noqa: E402, F401
from cache_manager import CacheManager  # noqa: E402, F401
from cost_latency_manager import CostLatencyManager  # noqa: E402, F401
from conflict_resolver import ConflictResolver  # noqa: E402, F401
from privacy_compliance import PrivacyComplianceManager  # noqa: E402, F401
from fault_tolerance import FaultToleranceManager  # noqa: E402, F401
from load_balancer import LoadBalancer  # noqa: E402, F401
from context_manager import ContextManager  # noqa: E402, F401
from observability_328 import ObservabilityManager  # noqa: E402, F401

__all__ = [
    "UCOrquestaRLayer",
    "OrquestaREngine",
    "default_sources",
    "OrquestaConfig",
    "OrquestaResult",
    "Subquery",
    "Source",
    "PartialResult",
    "ResolvedFact",
    "ExecutionMetrics",
    "Budget",
    "CacheEntry",
    "ContextVersion",
    "HealthStatus",
    "ExecutionVerdict",
    "SubqueryStatus",
    "SourceType",
    "PrivacyPolicy",
    "SourceRegistry",
    "SchemaFederation",
    "QueryRouter",
    "CacheManager",
    "CostLatencyManager",
    "ConflictResolver",
    "PrivacyComplianceManager",
    "FaultToleranceManager",
    "LoadBalancer",
    "ContextManager",
    "ObservabilityManager",
]
