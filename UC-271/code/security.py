"""Módulo de seguridad para UC-271 — RBAC, NetworkPolicy, mTLS, ServiceAccount.

Genera políticas de seguridad para cada agente desplegado en K8s con:
- RBAC con permisos mínimos por rol.
- NetworkPolicy para aislamiento de red.
- SecurityContext restrictivo (pod security standards).
- ServiceAccount dedicado sin automount de token.
- Auditoría de acciones de seguridad.
"""
from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from config import SecurityConfig, get_config
from models import (
    AgentProfile,
    AgentRole,
    NetworkPolicy,
    NetworkPolicyRule,
    PolicyAction,
    RBACPolicy,
    RBACRule,
    SecurityAuditEntry,
    SecurityContext,
    SecurityLevel,
    ServiceAccountConfig,
)


# RBAC templates por rol
_RBAC_TEMPLATES: Dict[AgentRole, List[RBACRule]] = {
    AgentRole.supervisor: [
        RBACRule(resources=["pods", "services", "deployments"], verbs=["get", "list", "watch", "create", "update"]),
        RBACRule(resources=["configmaps", "secrets"], verbs=["get", "list"]),
        RBACRule(api_groups=["autoscaling"], resources=["horizontalpodautoscalers"], verbs=["get", "list", "update"]),
    ],
    AgentRole.researcher: [
        RBACRule(resources=["pods", "services"], verbs=["get", "list"]),
        RBACRule(resources=["configmaps"], verbs=["get"]),
    ],
    AgentRole.coder: [
        RBACRule(resources=["pods", "services"], verbs=["get", "list"]),
        RBACRule(resources=["configmaps"], verbs=["get", "create", "update"]),
    ],
    AgentRole.reviewer: [
        RBACRule(resources=["pods", "services"], verbs=["get", "list"]),
        RBACRule(resources=["configmaps"], verbs=["get"]),
    ],
    AgentRole.executor: [
        RBACRule(resources=["pods"], verbs=["get", "list", "create", "delete"]),
        RBACRule(resources=["services", "configmaps"], verbs=["get", "list"]),
    ],
}


class SecurityManager:
    """Gestor de seguridad para agentes K8s."""

    def __init__(self, config: SecurityConfig | None = None, namespace: str = "agents"):
        self.config = config or get_config().security
        self.namespace = namespace
        self._audit_trail: List[SecurityAuditEntry] = []

    def generate_rbac(self, agent: AgentProfile) -> RBACPolicy:
        """Genera política RBAC con permisos mínimos según el rol del agente."""
        rules = _RBAC_TEMPLATES.get(agent.role, [RBACRule(resources=["pods"], verbs=["get", "list"])])
        policy = RBACPolicy(
            agent_name=agent.name,
            role_name=f"{agent.name}-role",
            namespace=self.namespace,
            rules=rules,
        )
        self._audit("rbac_generated", agent.name, f"Role={policy.role_name}, rules={len(rules)}")
        return policy

    def generate_network_policy(self, agent: AgentProfile, peers: List[str]) -> NetworkPolicy:
        """Genera NetworkPolicy para un agente.
        
        - Ingress: sólo permite tráfico del supervisor y peers explícitos.
        - Egress: permite salida al supervisor y servicios de monitoreo.
        """
        ingress_peers = ["supervisor"] + [p for p in peers if p != agent.name]
        egress_peers = ["supervisor", "prometheus", "jaeger"]

        rules = [
            NetworkPolicyRule(
                direction="ingress",
                allowed_pods=ingress_peers,
                allowed_namespaces=[self.namespace],
                ports=[8080, 9090],
                action=PolicyAction.allow,
            ),
            NetworkPolicyRule(
                direction="egress",
                allowed_pods=egress_peers,
                allowed_namespaces=[self.namespace, "monitoring"],
                ports=[8080, 9090, 14268],
                action=PolicyAction.allow,
            ),
        ]
        policy = NetworkPolicy(agent_name=agent.name, namespace=self.namespace, rules=rules)
        self._audit("netpol_generated", agent.name, f"ingress_peers={ingress_peers}")
        return policy

    def generate_service_account(self, agent: AgentProfile) -> ServiceAccountConfig:
        """Genera ServiceAccount dedicado sin automount."""
        sa = ServiceAccountConfig(
            name=f"{agent.name}-sa",
            namespace=self.namespace,
            automount_token=False,
            annotations={"iam.gke.io/gcp-service-account": f"{agent.name}@project.iam.gserviceaccount.com"},
        )
        self._audit("sa_generated", agent.name, f"ServiceAccount={sa.name}")
        return sa

    def generate_security_context(self, agent: AgentProfile) -> SecurityContext:
        """Genera SecurityContext restrictivo (pod security standard: restricted)."""
        ctx = SecurityContext(
            run_as_non_root=True,
            read_only_root_fs=True,
            drop_capabilities=["ALL"],
            allow_privilege_escalation=False,
            seccomp_profile="RuntimeDefault",
        )
        self._audit("secctx_generated", agent.name, f"nonroot=True, readonly_fs=True, drop=ALL")
        return ctx

    def validate_agent_security(self, agent: AgentProfile) -> List[str]:
        """Valida que un agente cumple con las políticas de seguridad."""
        violations: List[str] = []
        if not agent.service_account:
            violations.append(f"{agent.name}: no service account configured")
        if agent.role == AgentRole.supervisor and agent.replicas < 2:
            violations.append(f"{agent.name}: supervisor should have >=2 replicas for HA")
        # CPU/memory limits check
        if agent.cpu_limit == "":
            violations.append(f"{agent.name}: cpu_limit not set")
        if agent.memory_limit == "":
            violations.append(f"{agent.name}: memory_limit not set")
        if violations:
            self._audit("validation_failed", agent.name, f"violations={len(violations)}")
        else:
            self._audit("validation_passed", agent.name, "All checks passed")
        return violations

    @property
    def audit_trail(self) -> List[SecurityAuditEntry]:
        return list(self._audit_trail)

    def _audit(self, action: str, agent: str, detail: str) -> None:
        self._audit_trail.append(
            SecurityAuditEntry(action=action, agent_name=agent, detail=detail)
        )
