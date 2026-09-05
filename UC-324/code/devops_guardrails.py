"""UC-324 — Guardrails nativos para agentes DevOps/SRE (H) inspirados en agent-guardrails.

El repositorio `roboticforce/agent-guardrails` no es un paquete Python
instalable (no tiene `setup.py` ni `pyproject.toml`). UC-324 implementa aquí
un motor de guardrails para operaciones de infraestructura: Kubernetes, IaC
(Terraform, Ansible), shell, Docker, AWS CLI, bases de datos SQL, etc.

Objetivos:
- Bloquear comandos destructivos o irreversibles.
- Exigir aprobación y contexto para cambios en producción.
- Restringir herramientas, entornos y namespaces permitidos.
- Detectar falta de namespaces explícitos, ejecución en pods prod, etc.
- No ejecutar nunca los comandos; solo evaluar y aprobar/bloquear.
- Auditoría con evidencia, policy, entorno y comando original.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class Tool(str, Enum):
    SHELL = "shell"
    KUBECTL = "kubectl"
    TERRAFORM = "terraform"
    HELM = "helm"
    AWSCLI = "awscli"
    DOCKER = "docker"
    ANSIBLE = "ansible"
    PYTHON = "python"
    SQL = "sql"
    GIT = "git"
    UNKNOWN = "unknown"


class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    DESTROY = "destroy"
    EXEC = "exec"
    APPLY = "apply"
    PLAN = "plan"
    IMPORT = "import"
    SCALE = "scale"
    PATCH = "patch"
    ROLLBACK = "rollback"
    UNKNOWN = "unknown"


class Environment(str, Enum):
    PROD = "prod"
    STAGING = "staging"
    DEV = "dev"
    TEST = "test"
    UNKNOWN = "unknown"


@dataclass
class InfrastructureCommand:
    """Comando de infraestructura normalizado."""

    raw_command: str
    tool: Tool = Tool.UNKNOWN
    action: Action = Action.UNKNOWN
    target_env: Environment = Environment.UNKNOWN
    namespace: Optional[str] = None
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    args: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_command": self.raw_command,
            "tool": self.tool.value,
            "action": self.action.value,
            "target_env": self.target_env.value,
            "namespace": self.namespace,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "args": self.args,
            "metadata": self.metadata,
        }


@dataclass
class GuardrailsPolicy:
    """Política de guardrails DevOps."""

    allowed_tools: Optional[Set[Tool]] = None
    blocked_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_BLOCKED_PATTERNS))
    destructive_requires_approval: bool = True
    allowed_environments: Optional[Set[Environment]] = None
    allowed_namespaces: Optional[Set[str]] = None
    require_explicit_namespace_for_kubectl_delete: bool = True
    block_production_exec: bool = True
    block_production_destroy: bool = True
    require_dry_run_for_apply: bool = False
    approval_context_required: List[str] = field(default_factory=lambda: ["approved_by", "change_ticket_id"])
    allowlist_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_tools": [t.value for t in self.allowed_tools] if self.allowed_tools else None,
            "blocked_patterns": self.blocked_patterns,
            "destructive_requires_approval": self.destructive_requires_approval,
            "allowed_environments": [e.value for e in self.allowed_environments] if self.allowed_environments else None,
            "allowed_namespaces": list(self.allowed_namespaces) if self.allowed_namespaces else None,
            "require_explicit_namespace_for_kubectl_delete": self.require_explicit_namespace_for_kubectl_delete,
            "block_production_exec": self.block_production_exec,
            "block_production_destroy": self.block_production_destroy,
            "require_dry_run_for_apply": self.require_dry_run_for_apply,
            "approval_context_required": self.approval_context_required,
            "allowlist_only": self.allowlist_only,
        }


DEFAULT_BLOCKED_PATTERNS: List[str] = [
    r"\brm\s+-rf\s+/",
    r"\brm\s+-rf\s+/?\*",
    r"\bterraform\s+apply\b.*\b-auto-approve\b",
    r"\bkubectl\s+delete\s+(--all-namespaces|-A)\b",
    r"\bkubectl\s+delete\s+namespace\b",
    r"\bkubectl\s+delete\s+.*\b--all\b",
    r"\bkubectl\s+drain\s+.*\b--force\b",
    r"\bdocker\s+system\s+prune\b",
    r"\bdocker\s+rm\s+.*\b-f\b.*\b\$?\(docker\s+ps\s+-aq",
    r"\bhelm\s+uninstall\s+.*\b--all\b",
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
    r"\btruncate\s+table\b",
    r"\bdelete\s+from\s+\w+\b",
    r"\bchmod\s+777\s+/\b",
    r"\bmkfs\.",
    r"\bdd\s+if=.*\s+of=/dev/",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpkill\s+-9\b",
    r"\bkill\s+-9\s+1\b",
    r"\baws\s+.*\bdelete\b.*\b--force\b",
    r"\baws\s+.*\bterminate-instances\b",
    r"\bkubectl\s+.*\b--overwrite\b.*\b--force\b",
    r"\bansible-playbook\s+.*\b--flush-cache\b",
    r"\bpython\s+.*\bexec\s*\(",
    r"\bpython\s+.*\beval\s*\(",
    r"\bpython\s+.*\bos\.system\b",
    r"\bpython\s+.*\bsubprocess\b",
]


@dataclass
class GuardrailsVerdict:
    allowed: bool = True
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_command: Optional[str] = None
    command: Dict[str, Any] = field(default_factory=dict)
    policy: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "issues": self.issues,
            "warnings": self.warnings,
            "sanitized_command": self.sanitized_command,
            "command": self.command,
            "policy": self.policy,
        }


class CommandParser:
    """Clasifica un comando bruto en una estructura `InfrastructureCommand`."""

    @staticmethod
    def parse(command: str, target_env: str = "unknown", metadata: Optional[Dict[str, Any]] = None) -> InfrastructureCommand:
        cmd = InfrastructureCommand(
            raw_command=command,
            target_env=Environment(target_env) if target_env in Environment._value2member_map_ else Environment.UNKNOWN,
            metadata=metadata or {},
        )
        CommandParser._classify_tool(cmd)
        CommandParser._classify_action(cmd)
        CommandParser._extract_namespace(cmd)
        CommandParser._extract_resource(cmd)
        return cmd

    @staticmethod
    def _classify_tool(cmd: InfrastructureCommand) -> None:
        text = cmd.raw_command.lower()
        if text.startswith("kubectl "):
            cmd.tool = Tool.KUBECTL
        elif text.startswith("terraform "):
            cmd.tool = Tool.TERRAFORM
        elif text.startswith("helm "):
            cmd.tool = Tool.HELM
        elif text.startswith("aws "):
            cmd.tool = Tool.AWSCLI
        elif text.startswith("docker "):
            cmd.tool = Tool.DOCKER
        elif text.startswith("ansible") or text.startswith("ansible-playbook"):
            cmd.tool = Tool.ANSIBLE
        elif text.startswith("python") or text.startswith("python3") or text.startswith("py "):
            cmd.tool = Tool.PYTHON
        elif re.search(r"\b(sqlite3|mysql|psql|sqlcmd)\b", text):
            cmd.tool = Tool.SQL
        elif text.startswith("git "):
            cmd.tool = Tool.GIT
        elif re.search(r"\b(sh|bash|zsh|/bin/sh|/bin/bash|cmd|powershell)\b", text) or text.startswith(("rm ", "cp ", "mv ", "chmod ", "chown ", "dd ", "mkfs")):
            cmd.tool = Tool.SHELL
        else:
            cmd.tool = Tool.UNKNOWN

        try:
            cmd.args = shlex.split(cmd.raw_command)
        except ValueError:
            cmd.args = cmd.raw_command.split()

    @staticmethod
    def _classify_action(cmd: InfrastructureCommand) -> None:
        text = cmd.raw_command.lower()
        if cmd.tool == Tool.KUBECTL:
            if re.search(r"\bdelete\b", text):
                cmd.action = Action.DELETE
            elif re.search(r"\bexec\b", text):
                cmd.action = Action.EXEC
            elif re.search(r"\bapply\b", text):
                cmd.action = Action.APPLY
            elif re.search(r"\bcreate\b", text):
                cmd.action = Action.CREATE
            elif re.search(r"\bscale\b", text):
                cmd.action = Action.SCALE
            elif re.search(r"\bpatch\b", text):
                cmd.action = Action.PATCH
            elif re.search(r"\bget\b|\bdescribe\b|\b logs\b", text):
                cmd.action = Action.READ
        elif cmd.tool == Tool.TERRAFORM:
            if re.search(r"\bdestroy\b", text):
                cmd.action = Action.DESTROY
            elif re.search(r"\bapply\b", text):
                cmd.action = Action.APPLY
            elif re.search(r"\bplan\b", text):
                cmd.action = Action.PLAN
            elif re.search(r"\bimport\b", text):
                cmd.action = Action.IMPORT
        elif cmd.tool == Tool.HELM:
            if re.search(r"\binstall\b|\bupgrade\b", text):
                cmd.action = Action.CREATE if "install" in text else Action.UPDATE
            elif re.search(r"\buninstall\b|\bdelete\b", text):
                cmd.action = Action.DELETE
            elif re.search(r"\brollback\b", text):
                cmd.action = Action.ROLLBACK
        elif cmd.tool == Tool.AWSCLI:
            if re.search(r"\bdelete\b|\bterminate\b|\bremove\b", text):
                cmd.action = Action.DELETE
            elif re.search(r"\bcreate\b|\brun\b|\bstart\b", text):
                cmd.action = Action.CREATE
            elif re.search(r"\bupdate\b|\bmodify\b", text):
                cmd.action = Action.UPDATE
        elif cmd.tool == Tool.DOCKER:
            if re.search(r"\brm\b|\bprune\b", text):
                cmd.action = Action.DELETE
            elif re.search(r"\brun\b|\bcreate\b", text):
                cmd.action = Action.CREATE
        elif cmd.tool == Tool.SHELL:
            if re.search(r"\brm\b|\bdelete\b|\bdestroy\b", text):
                cmd.action = Action.DELETE
            elif re.search(r"\bcreate\b|\bapply\b", text):
                cmd.action = Action.CREATE
            elif re.search(r"\bexec\b", text):
                cmd.action = Action.EXEC
        elif cmd.tool == Tool.SQL:
            if re.search(r"\bdrop\b|\bdelete\b|\btruncate\b", text):
                cmd.action = Action.DELETE
            elif re.search(r"\bcreate\b|\binsert\b|\bupdate\b", text):
                cmd.action = Action.UPDATE
            elif re.search(r"\bselect\b", text):
                cmd.action = Action.READ

    @staticmethod
    def _extract_namespace(cmd: InfrastructureCommand) -> None:
        if cmd.tool != Tool.KUBECTL:
            return
        match = re.search(r"-n\s+(\S+)|--namespace\s+(\S+)", cmd.raw_command)
        if match:
            cmd.namespace = match.group(1) or match.group(2)

    @staticmethod
    def _extract_resource(cmd: InfrastructureCommand) -> None:
        if cmd.tool != Tool.KUBECTL:
            return
        # kubectl <action> <type> <name> ...
        parts = re.split(r"\s+", cmd.raw_command)
        if len(parts) >= 3 and parts[1] in ("get", "describe", "delete", "scale", "patch", "exec", "logs"):
            cmd.resource_type = parts[2]
            if len(parts) >= 4 and not parts[3].startswith("-"):
                cmd.resource_name = parts[3]


class DevOpsGuardrails:
    """Motor de guardrails DevOps/SRE."""

    DEFAULT_POLICY = GuardrailsPolicy()

    def __init__(self, policy: Optional[GuardrailsPolicy] = None) -> None:
        self.policy = policy if policy is not None else self.DEFAULT_POLICY

    @staticmethod
    def _is_destructive_action(cmd: InfrastructureCommand) -> bool:
        return cmd.action in (Action.DELETE, Action.DESTROY, Action.ROLLBACK)

    @staticmethod
    def _is_sensitive_action(cmd: InfrastructureCommand) -> bool:
        return cmd.action in (Action.DELETE, Action.DESTROY, Action.EXEC, Action.APPLY, Action.ROLLBACK)

    def evaluate(
        self,
        command: str,
        target_env: str = "unknown",
        approval_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GuardrailsVerdict:
        """Evalúa un comando de infraestructura contra la política."""
        approval_context = approval_context or {}
        cmd = CommandParser.parse(command, target_env=target_env, metadata=metadata)
        verdict = GuardrailsVerdict(command=cmd.to_dict(), policy=self.policy.to_dict())

        # 1. Herramientas permitidas
        if self.policy.allowed_tools and cmd.tool not in self.policy.allowed_tools:
            verdict.allowed = False
            verdict.issues.append(f"Tool '{cmd.tool.value}' is not in the allowed tool list")
            return verdict

        # 2. Patrones bloqueados globalmente (destructivos sin condiciones)
        for pattern in self.policy.blocked_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                verdict.allowed = False
                verdict.issues.append(f"Blocked by destructive pattern: {pattern}")
                verdict.sanitized_command = "[BLOCKED]"
                return verdict

        # 3. Entorno permitido
        if self.policy.allowed_environments and cmd.target_env not in self.policy.allowed_environments:
            verdict.allowed = False
            verdict.issues.append(
                f"Environment '{cmd.target_env.value}' is not in allowed environments: "
                f"{[e.value for e in self.policy.allowed_environments]}"
            )

        # 4. Namespace permitido / explícito para kubectl delete
        if cmd.tool == Tool.KUBECTL and cmd.action == Action.DELETE:
            if self.policy.require_explicit_namespace_for_kubectl_delete and not cmd.namespace:
                verdict.allowed = False
                verdict.issues.append("kubectl delete requires an explicit namespace in this policy")
            if self.policy.allowed_namespaces and cmd.namespace not in self.policy.allowed_namespaces:
                verdict.allowed = False
                verdict.issues.append(
                    f"Namespace '{cmd.namespace}' is not in allowed namespaces: "
                    f"{list(self.policy.allowed_namespaces)}"
                )

        # 5. Exec en producción
        if self.policy.block_production_exec and cmd.target_env == Environment.PROD and cmd.action == Action.EXEC:
            verdict.allowed = False
            verdict.issues.append("kubectl exec into production pods is blocked by policy")

        # 6. Destroy en producción
        if self.policy.block_production_destroy and cmd.target_env == Environment.PROD and cmd.action == Action.DESTROY:
            verdict.allowed = False
            verdict.issues.append("terraform destroy in production is blocked by policy")

        # 7. Aprobación para acciones destructivas
        if self.policy.destructive_requires_approval and self._is_destructive_action(cmd):
            missing = [k for k in self.policy.approval_context_required if not approval_context.get(k)]
            if missing:
                verdict.allowed = False
                verdict.issues.append(
                    f"Destructive action requires approval context: {missing}"
                )

        # 8. Dry-run para apply en producción (warning)
        if self.policy.require_dry_run_for_apply and cmd.target_env == Environment.PROD and cmd.action == Action.APPLY:
            if "-dry-run" not in command and "--dry-run" not in command:
                verdict.warnings.append("Production terraform apply should use -dry-run first")

        # 9. Sanitización básica: no exponer secrets en texto plano (warning)
        if re.search(r"(--token|-p\s+|password\s*=|secret\s*=|AWS_SECRET_ACCESS_KEY)", command, re.IGNORECASE):
            verdict.warnings.append("Command may contain credentials; review before execution")

        if verdict.allowed and not verdict.sanitized_command:
            verdict.sanitized_command = cmd.raw_command

        return verdict

    def evaluate_plan(
        self,
        commands: List[str],
        target_env: str = "unknown",
        approval_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evalúa una lista de comandos (plan) y devuelve un resumen."""
        results = []
        overall_allowed = True
        for command in commands:
            verdict = self.evaluate(command, target_env=target_env, approval_context=approval_context)
            results.append(verdict.to_dict())
            if not verdict.allowed:
                overall_allowed = False
        return {
            "allowed": overall_allowed,
            "target_env": target_env,
            "commands_evaluated": len(results),
            "commands_blocked": sum(1 for r in results if not r["allowed"]),
            "results": results,
        }


def evaluate_command(
    command: str,
    target_env: str = "unknown",
    approval_context: Optional[Dict[str, Any]] = None,
    policy: Optional[GuardrailsPolicy] = None,
) -> Dict[str, Any]:
    """Helper de alto nivel para evaluar un comando."""
    guardrails = DevOpsGuardrails(policy=policy)
    return guardrails.evaluate(command, target_env=target_env, approval_context=approval_context).to_dict()
