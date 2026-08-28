"""Generador de manifiestos Kubernetes para UC-271.

Genera YAMLs para: Deployment, HPA, NetworkPolicy, ServiceAccount, Role, RoleBinding.
"""
from __future__ import annotations

from typing import Any, Dict, List

from config import AppConfig, get_config
from models import AgentProfile, K8sManifest
from security import SecurityManager


class ManifestGenerator:
    """Genera manifiestos K8s completos para el sistema multi-agent."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or get_config()
        self.security = SecurityManager(self.config.security, self.config.namespace)

    def generate_all(self, agents: List[AgentProfile]) -> List[K8sManifest]:
        """Genera todos los manifiestos para una lista de agentes."""
        manifests: List[K8sManifest] = []
        for agent in agents:
            manifests.extend(self._generate_for_agent(agent, [a.name for a in agents]))
        # HPA para cada agente
        for agent in agents:
            manifests.append(self._hpa(agent))
        return manifests

    def _generate_for_agent(self, agent: AgentProfile, all_names: List[str]) -> List[K8sManifest]:
        return [
            self._namespace(),
            self._service_account(agent),
            self._role(agent),
            self._role_binding(agent),
            self._deployment(agent),
            self._service(agent),
            self._network_policy(agent, all_names),
        ]

    def _namespace(self) -> K8sManifest:
        return K8sManifest(
            kind="Namespace",
            api_version="v1",
            name=self.config.namespace,
            content={
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": self.config.namespace,
                    "labels": {"pod-security.kubernetes.io/enforce": self.config.security.pod_security_standard},
                },
            },
        )

    def _service_account(self, agent: AgentProfile) -> K8sManifest:
        sa = self.security.generate_service_account(agent)
        return K8sManifest(
            kind="ServiceAccount",
            api_version="v1",
            name=sa.name,
            namespace=self.config.namespace,
            content={
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {"name": sa.name, "namespace": self.config.namespace, "annotations": sa.annotations},
                "automountServiceAccountToken": sa.automount_token,
            },
        )

    def _role(self, agent: AgentProfile) -> K8sManifest:
        rbac = self.security.generate_rbac(agent)
        rules = []
        for r in rbac.rules:
            rules.append({"apiGroups": r.api_groups, "resources": r.resources, "verbs": r.verbs})
        return K8sManifest(
            kind="Role",
            api_version="rbac.authorization.k8s.io/v1",
            name=rbac.role_name,
            namespace=self.config.namespace,
            content={
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "Role",
                "metadata": {"name": rbac.role_name, "namespace": self.config.namespace},
                "rules": rules,
            },
        )

    def _role_binding(self, agent: AgentProfile) -> K8sManifest:
        return K8sManifest(
            kind="RoleBinding",
            api_version="rbac.authorization.k8s.io/v1",
            name=f"{agent.name}-binding",
            namespace=self.config.namespace,
            content={
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": f"{agent.name}-binding", "namespace": self.config.namespace},
                "subjects": [{"kind": "ServiceAccount", "name": f"{agent.name}-sa", "namespace": self.config.namespace}],
                "roleRef": {"kind": "Role", "name": f"{agent.name}-role", "apiGroup": "rbac.authorization.k8s.io"},
            },
        )

    def _deployment(self, agent: AgentProfile) -> K8sManifest:
        sec_ctx = self.security.generate_security_context(agent)
        return K8sManifest(
            kind="Deployment",
            api_version="apps/v1",
            name=f"{agent.name}-deployment",
            namespace=self.config.namespace,
            content={
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": f"{agent.name}-deployment", "namespace": self.config.namespace},
                "spec": {
                    "replicas": agent.replicas,
                    "selector": {"matchLabels": {"app": agent.name, "role": agent.role.value}},
                    "template": {
                        "metadata": {"labels": {"app": agent.name, "role": agent.role.value}},
                        "spec": {
                            "serviceAccountName": f"{agent.name}-sa",
                            "securityContext": {"runAsNonRoot": sec_ctx.run_as_non_root},
                            "containers": [{
                                "name": agent.name,
                                "image": self.config.security.pod_security_standard,
                                "resources": {
                                    "requests": {"cpu": agent.cpu_request, "memory": agent.memory_request},
                                    "limits": {"cpu": agent.cpu_limit, "memory": agent.memory_limit},
                                },
                                "securityContext": {
                                    "readOnlyRootFilesystem": sec_ctx.read_only_root_fs,
                                    "allowPrivilegeEscalation": sec_ctx.allow_privilege_escalation,
                                    "capabilities": {"drop": sec_ctx.drop_capabilities},
                                    "seccompProfile": {"type": sec_ctx.seccomp_profile},
                                },
                                "ports": [{"containerPort": 8080}],
                            }],
                        },
                    },
                },
            },
        )

    def _service(self, agent: AgentProfile) -> K8sManifest:
        return K8sManifest(
            kind="Service",
            api_version="v1",
            name=f"{agent.name}-svc",
            namespace=self.config.namespace,
            content={
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": f"{agent.name}-svc", "namespace": self.config.namespace},
                "spec": {
                    "selector": {"app": agent.name},
                    "ports": [{"port": 8080, "targetPort": 8080}],
                },
            },
        )

    def _network_policy(self, agent: AgentProfile, peers: List[str]) -> K8sManifest:
        np = self.security.generate_network_policy(agent, peers)
        ingress_rules = []
        egress_rules = []
        for rule in np.rules:
            pod_selector = [{"podSelector": {"matchLabels": {"app": p}}} for p in rule.allowed_pods]
            entry = {"from" if rule.direction == "ingress" else "to": pod_selector, "ports": [{"port": port} for port in rule.ports]}
            if rule.direction == "ingress":
                ingress_rules.append(entry)
            else:
                egress_rules.append(entry)

        return K8sManifest(
            kind="NetworkPolicy",
            api_version="networking.k8s.io/v1",
            name=f"{agent.name}-netpol",
            namespace=self.config.namespace,
            content={
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": f"{agent.name}-netpol", "namespace": self.config.namespace},
                "spec": {
                    "podSelector": {"matchLabels": {"app": agent.name}},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": ingress_rules,
                    "egress": egress_rules,
                },
            },
        )

    def _hpa(self, agent: AgentProfile) -> K8sManifest:
        return K8sManifest(
            kind="HorizontalPodAutoscaler",
            api_version="autoscaling/v2",
            name=f"{agent.name}-hpa",
            namespace=self.config.namespace,
            content={
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {"name": f"{agent.name}-hpa", "namespace": self.config.namespace},
                "spec": {
                    "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": f"{agent.name}-deployment"},
                    "minReplicas": self.config.hpa.min_replicas,
                    "maxReplicas": self.config.hpa.max_replicas,
                    "metrics": [
                        {"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": self.config.hpa.target_cpu_percent}}},
                        {"type": "Resource", "resource": {"name": "memory", "target": {"type": "Utilization", "averageUtilization": self.config.hpa.target_memory_percent}}},
                        {"type": "Pods", "pods": {"metric": {"name": self.config.hpa.custom_metric_name}, "target": {"type": "AverageValue", "averageValue": str(self.config.hpa.custom_metric_target)}}},
                    ],
                    "behavior": {
                        "scaleUp": {"stabilizationWindowSeconds": self.config.hpa.scale_up_cooldown_sec, "policies": [{"type": "Percent", "value": 100, "periodSeconds": 60}]},
                        "scaleDown": {"stabilizationWindowSeconds": self.config.hpa.scale_down_cooldown_sec, "policies": [{"type": "Pods", "value": 1, "periodSeconds": 60}]},
                    },
                },
            },
        )
