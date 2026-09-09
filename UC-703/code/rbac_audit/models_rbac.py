"""Modelos para RBAC y auditoría inmutable de gobernanza de IA."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    DEPLOY = "deploy"
    APPROVE = "approve"
    ADMIN = "admin"


class ResourceType(str, Enum):
    MODEL = "model"
    DATASET = "dataset"
    PROMPT = "prompt"
    CONFIG = "config"
    SECRET = "secret"
    ENVIRONMENT = "environment"
    PIPELINE = "pipeline"
    USER = "user"
    AUDIT = "audit"


@dataclass
class Principal:
    principal_id: str = ""
    name: str = ""
    principal_type: str = ""  # user, group, service_account, pipeline
    roles: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "name": self.name,
            "principal_type": self.principal_type,
            "roles": self.roles,
            "metadata": self.metadata,
        }


@dataclass
class Role:
    role_id: str = ""
    name: str = ""
    description: str = ""
    permissions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
        }


@dataclass
class Permission:
    permission_id: str = ""
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""  # empty means all resources of type
    conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "permission_id": self.permission_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "conditions": self.conditions,
        }


@dataclass
class Resource:
    resource_id: str = ""
    resource_type: str = ""
    owner: str = ""
    version: str = ""
    sensitivity: str = ""  # public, internal, restricted, secret
    environment: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "owner": self.owner,
            "version": self.version,
            "sensitivity": self.sensitivity,
            "environment": self.environment,
            "metadata": self.metadata,
        }


@dataclass
class AccessDecision:
    decision_id: str = field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:8]}")
    principal_id: str = ""
    action: str = ""
    resource_id: str = ""
    resource_type: str = ""
    allowed: bool = False
    reason: str = ""
    roles: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "principal_id": self.principal_id,
            "action": self.action,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "allowed": self.allowed,
            "reason": self.reason,
            "roles": self.roles,
            "timestamp": self.timestamp,
        }


@dataclass
class AuditRecord:
    record_id: str = field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:8]}")
    event_type: str = ""  # authentication, access, change, deployment, approval, denial
    principal_id: str = ""
    identity: str = ""
    role: str = ""
    action: str = ""
    resource_id: str = ""
    resource_type: str = ""
    resource_version: str = ""
    outcome: str = ""  # success, denied, error
    origin: str = ""
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    decision_id: str = ""
    immutable_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "event_type": self.event_type,
            "principal_id": self.principal_id,
            "identity": self.identity,
            "role": self.role,
            "action": self.action,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "resource_version": self.resource_version,
            "outcome": self.outcome,
            "origin": self.origin,
            "timestamp": self.timestamp,
            "details": self.details,
            "decision_id": self.decision_id,
            "immutable_hash": self.immutable_hash,
        }


@dataclass
class ApprovalRequest:
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}")
    principal_id: str = ""
    action: str = ""
    resource_id: str = ""
    resource_type: str = ""
    justification: str = ""
    status: str = "pending"  # pending, approved, rejected
    approvals: List[str] = field(default_factory=list)
    rejections: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "principal_id": self.principal_id,
            "action": self.action,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "justification": self.justification,
            "status": self.status,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "details": self.details,
        }
