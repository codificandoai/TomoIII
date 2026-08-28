"""Modelos Pydantic para UC-271 — Multi-Agent K8s con Seguridad y HPA.

Cubre: agentes, pods, HPA decisions, security policies, RBAC, manifests.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class AgentRole(str, Enum):
    supervisor = "supervisor"
    researcher = "researcher"
    coder = "coder"
    reviewer = "reviewer"
    executor = "executor"


class ScalingDirection(str, Enum):
    up = "scale_up"
    down = "scale_down"
    none = "no_change"


class SecurityLevel(str, Enum):
    restricted = "restricted"
    baseline = "baseline"
    privileged = "privileged"


class PolicyAction(str, Enum):
    allow = "allow"
    deny = "deny"
    audit = "audit"


# ============================================================
# Agent & Task models
# ============================================================

class AgentProfile(BaseModel):
    """Perfil de un agente desplegable en K8s."""
    name: str
    role: AgentRole
    skill: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    replicas: int = Field(ge=1, default=1)
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
    service_account: str = ""
    labels: Dict[str, str] = Field(default_factory=dict)


class TaskRequest(BaseModel):
    """Solicitud de tarea al sistema multi-agent."""
    task_id: UUID = Field(default_factory=uuid4)
    task: str
    resource: Optional[str] = None
    priority: int = Field(ge=0, le=10, default=5)
    requester: str = "user"


class Proposal(BaseModel):
    """Propuesta de un agente para ejecutar una tarea."""
    agent_name: str
    role: AgentRole
    score: float
    latency_ms: int
    cost: float
    message: str


class ExecutionResult(BaseModel):
    """Resultado de ejecución de una tarea."""
    task_id: UUID
    task: str
    winner: str
    proposals: List[Proposal]
    execution: Dict[str, Any]
    scaling_decision: Optional["ScalingDecision"] = None
    security_context: Optional["SecurityContext"] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# HPA models
# ============================================================

class PodMetrics(BaseModel):
    """Métricas actuales de un pod/agente."""
    agent_name: str
    cpu_percent: float = Field(ge=0.0, le=100.0)
    memory_percent: float = Field(ge=0.0, le=100.0)
    queue_depth: int = Field(ge=0, default=0)
    active_tasks: int = Field(ge=0, default=0)
    replicas_current: int = Field(ge=0, default=1)


class ScalingDecision(BaseModel):
    """Decisión de escalado del HPA."""
    decision_id: UUID = Field(default_factory=uuid4)
    agent_name: str
    direction: ScalingDirection
    current_replicas: int
    desired_replicas: int
    reason: str
    metrics: PodMetrics
    cooldown_remaining_sec: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HPAStatus(BaseModel):
    """Estado actual del HPA para un agente."""
    agent_name: str
    min_replicas: int
    max_replicas: int
    current_replicas: int
    target_cpu_percent: int
    target_memory_percent: int
    last_scale_time: Optional[datetime] = None
    decisions_history: List[ScalingDecision] = Field(default_factory=list)


# ============================================================
# Security models
# ============================================================

class RBACRule(BaseModel):
    """Regla RBAC para un agente."""
    api_groups: List[str] = Field(default_factory=lambda: [""])
    resources: List[str]
    verbs: List[str]


class RBACPolicy(BaseModel):
    """Política RBAC completa para un agente."""
    agent_name: str
    role_name: str
    namespace: str = "agents"
    rules: List[RBACRule]


class NetworkPolicyRule(BaseModel):
    """Regla de NetworkPolicy."""
    direction: Literal["ingress", "egress"]
    allowed_pods: List[str] = Field(default_factory=list)
    allowed_namespaces: List[str] = Field(default_factory=list)
    ports: List[int] = Field(default_factory=list)
    action: PolicyAction = PolicyAction.allow


class NetworkPolicy(BaseModel):
    """NetworkPolicy completa para un agente."""
    agent_name: str
    namespace: str = "agents"
    rules: List[NetworkPolicyRule]


class ServiceAccountConfig(BaseModel):
    """Configuración de ServiceAccount."""
    name: str
    namespace: str = "agents"
    automount_token: bool = False
    annotations: Dict[str, str] = Field(default_factory=dict)


class SecurityContext(BaseModel):
    """Contexto de seguridad aplicado a un pod."""
    run_as_non_root: bool = True
    read_only_root_fs: bool = True
    drop_capabilities: List[str] = Field(default_factory=lambda: ["ALL"])
    allow_privilege_escalation: bool = False
    seccomp_profile: str = "RuntimeDefault"


class SecurityAuditEntry(BaseModel):
    """Entrada de auditoría de seguridad."""
    entry_id: UUID = Field(default_factory=uuid4)
    action: str
    agent_name: str
    detail: str
    level: SecurityLevel = SecurityLevel.restricted
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# Kubernetes manifest model
# ============================================================

class K8sManifest(BaseModel):
    """Manifiesto K8s generado."""
    kind: str
    api_version: str
    name: str
    namespace: str = "agents"
    content: Dict[str, Any]
