"""Tests del generador de manifiestos K8s."""
from __future__ import annotations

from manifest_generator import ManifestGenerator
from models import AgentProfile, AgentRole


def _profiles() -> list[AgentProfile]:
    return [
        AgentProfile(name="researcher", role=AgentRole.researcher, skill=0.9, cost=1.0, latency_ms=200, replicas=2, service_account="researcher-sa"),
        AgentProfile(name="coder", role=AgentRole.coder, skill=0.85, cost=0.8, latency_ms=150, replicas=1, service_account="coder-sa"),
    ]


def test_generates_manifests_for_all_agents() -> None:
    gen = ManifestGenerator()
    manifests = gen.generate_all(_profiles())
    # Each agent: Namespace + SA + Role + RoleBinding + Deployment + Service + NetworkPolicy = 7
    # Plus HPA per agent = 2
    # 7*2 + 2 = 16
    assert len(manifests) >= 10


def test_deployment_has_security_context() -> None:
    gen = ManifestGenerator()
    manifests = gen.generate_all(_profiles())
    deployments = [m for m in manifests if m.kind == "Deployment"]
    assert len(deployments) == 2
    for dep in deployments:
        container = dep.content["spec"]["template"]["spec"]["containers"][0]
        sc = container["securityContext"]
        assert sc["readOnlyRootFilesystem"] is True
        assert sc["allowPrivilegeEscalation"] is False
        assert "ALL" in sc["capabilities"]["drop"]


def test_hpa_generated_with_metrics() -> None:
    gen = ManifestGenerator()
    manifests = gen.generate_all(_profiles())
    hpas = [m for m in manifests if m.kind == "HorizontalPodAutoscaler"]
    assert len(hpas) == 2
    for hpa in hpas:
        spec = hpa.content["spec"]
        assert spec["minReplicas"] >= 1
        assert spec["maxReplicas"] >= spec["minReplicas"]
        assert len(spec["metrics"]) == 3


def test_rbac_role_created() -> None:
    gen = ManifestGenerator()
    manifests = gen.generate_all(_profiles())
    roles = [m for m in manifests if m.kind == "Role"]
    assert len(roles) == 2


def test_network_policy_created() -> None:
    gen = ManifestGenerator()
    manifests = gen.generate_all(_profiles())
    netpols = [m for m in manifests if m.kind == "NetworkPolicy"]
    assert len(netpols) == 2
    for np in netpols:
        spec = np.content["spec"]
        assert "Ingress" in spec["policyTypes"]
        assert "Egress" in spec["policyTypes"]
