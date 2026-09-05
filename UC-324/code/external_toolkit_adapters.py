"""UC-324 — Adaptadores para toolkits externos de seguridad de agentes (A-K).

Cada adapter envuelve un proyecto de código abierto. Si la librería no está
instalada, el adapter cae a una heurística interna equivalente para no romper
la ejecución ni introducir dependencias obligatorias.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Gate(str, Enum):
    PRE_ACTION = "pre_action"
    EXECUTION = "execution"
    POST_ACTION = "post_action"





@dataclass
class AdapterResult:
    allowed: bool = True
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 0.0  # 0.0 = seguro, 1.0 = máximo riesgo
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "issues": self.issues,
            "warnings": self.warnings,
            "score": self.score,
            "details": self.details,
        }


class ExternalAdapter(ABC):
    """Interfaz común para validadores externos."""

    name: str = ""
    source_repo: str = ""
    gate: Gate = Gate.PRE_ACTION

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# A. Microsoft Agent Governance Toolkit
# ---------------------------------------------------------------------------
class AGTGovernanceAdapter(ExternalAdapter):
    """Adaptador para Microsoft Agent Governance Toolkit.

    Si `agent_governance` no está disponible, aplica un motor de políticas
    declarativas emulado a partir de `domain_policy.py`.
    """

    name = "microsoft_agent_governance"
    source_repo = "https://github.com/microsoft/agent-governance-toolkit"
    gate = Gate.PRE_ACTION

    def __init__(self) -> None:
        self._native = None
        try:
            from agt_native_integration import AGT_AVAILABLE, AGTNativeGovernance

            if AGT_AVAILABLE:
                self._native = AGTNativeGovernance()
        except Exception as exc:
            self._native = None
            self._native_error = str(exc)

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        skill = context.get("skill", {})
        inputs = context.get("inputs", {})
        roles = context.get("user_roles", [])
        domain_state = context.get("domain_state", {})
        result = AdapterResult()

        if self._native is not None:
            try:
                agt_res = self._native.evaluate(
                    skill=skill,
                    inputs=inputs,
                    roles=roles,
                    domain_state=domain_state,
                    agent_id=context.get("agent_id", "orchestrator_001"),
                )
                result.allowed = agt_res.allowed
                result.issues = agt_res.issues
                result.warnings = agt_res.warnings
                result.details = {**agt_res.details, "source": "AGT native"}
                return result
            except Exception as exc:
                result.warnings.append(f"AGT native falló: {exc}; se usa fallback")

        # Fallback determinista fail-closed
        required_roles = skill.get("required_roles", [])
        missing_roles = [r for r in required_roles if r not in roles]
        if missing_roles:
            result.allowed = False
            result.issues.append(f"AGT fallback: faltan roles {missing_roles}")

        perms = skill.get("permissions", [])
        missing_perms = [p for p in perms if p not in roles]
        if missing_perms:
            result.allowed = False
            result.issues.append(f"AGT fallback: faltan permisos {missing_perms}")

        risk = skill.get("risk_level", "low")
        if risk in ("high", "critical") and not domain_state.get("approval_override"):
            result.warnings.append("AGT fallback: acción de alto riesgo requiere aprobación")

        result.details["source"] = "AGT fallback"
        return result


# ---------------------------------------------------------------------------
# B. Adaptive Stress Testing Toolbox
# ---------------------------------------------------------------------------
class AdaptiveStressTestingAdapter(ExternalAdapter):
    """Adaptador para sisl/AdaptiveStressTestingToolbox.

    Busca escenarios worst-case para políticas autónomas usando el algoritmo
    AST nativo (MCTS-UCT) implementado en `ast_integration.py`. La librería
    original no es instalable por su dependencia legacy `torch==1.3.0`, así
    que se portó el núcleo del método.
    """

    name = "adaptive_stress_testing"
    source_repo = "https://github.com/sisl/AdaptiveStressTestingToolbox"
    gate = Gate.PRE_ACTION

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        skill = context.get("skill", {})
        domain_state = context.get("domain_state", {})
        result = AdapterResult()

        try:
            from ast_integration import run_stress_test

            worst = run_stress_test(skill, domain_state, iterations=200)
            result.details = {"worst_case": worst, "source": "AST integration"}
            if worst.get("violation"):
                result.warnings.append(
                    f"AST worst-case podría violar: {worst['violation']} "
                    f"(perturbaciones: {worst.get('perturbed_keys', [])})"
                )
                result.score = worst.get("risk_score", 1.0)
            else:
                result.score = worst.get("risk_score", 0.0)
            return result
        except Exception as exc:
            result.warnings.append(f"AST integration no disponible: {exc}; se usa heurística")

        # Heurística worst-case simple
        worst_cost = skill.get("estimated_cost", 0) * 10
        worst_latency = skill.get("estimated_latency_ms", 0) * 5
        risk = skill.get("risk_level", "low")

        if risk in ("high", "critical"):
            if worst_cost > domain_state.get("max_cost_per_action", 1_000_000):
                result.allowed = False
                result.issues.append(
                    f"Stress test worst-case cost {worst_cost} excede presupuesto de contingencia"
                )
            if worst_latency > domain_state.get("max_latency_ms", 60_000):
                result.warnings.append(
                    f"Stress test worst-case latency {worst_latency}ms excede SLA"
                )

        result.score = 0.8 if risk == "critical" else 0.5 if risk == "high" else 0.1
        result.details["worst_case_cost"] = worst_cost
        result.details["worst_case_latency_ms"] = worst_latency
        result.details["source"] = "AST heuristic"
        return result


# ---------------------------------------------------------------------------
# C. AI Safety (red-teaming)
# ---------------------------------------------------------------------------
class AISafetyRedTeamAdapter(ExternalAdapter):
    """Adaptador para cjackett/ai-safety: red-teaming de agentes autónomos.

    Implementa detección heurística de jailbreak/prompt injection en inputs.
    La evaluación adversarial completa (campanas de ataque contra el sandbox)
    está en `ai_safety_integration.RedTeamEvaluator`.
    """

    name = "ai_safety_redteam"
    source_repo = "https://github.com/cjackett/ai-safety"
    gate = Gate.PRE_ACTION

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        from ai_safety_integration import quick_jailbreak_check

        text = json.dumps(context.get("inputs", {}), ensure_ascii=False)
        check = quick_jailbreak_check(text)
        result = AdapterResult()
        if check["detected"]:
            result.allowed = False
            result.issues.append(
                f"Red-team: patrones de jailbreak detectados {check['matches']}"
            )
            result.score = 1.0
        result.details["patterns_checked"] = check["patterns_checked"]
        result.details["matches"] = check["matches"]
        result.details["source"] = "Red-team heuristic (ai-safety integration)"
        return result


# ---------------------------------------------------------------------------
# D. SafeAuto (post-action verification)
# ---------------------------------------------------------------------------
class SafeAutoPostActionAdapter(ExternalAdapter):
    """Adaptador para AI-secure/SafeAuto: verificación post-acción con reglas.

    Como SafeAuto no es un paquete pip instalable, delega en el motor de reglas
    declarativas implementado en `safeauto_integration.py`.
    """

    name = "safeauto_post_action"
    source_repo = "https://github.com/AI-secure/SafeAuto"
    gate = Gate.POST_ACTION

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None) -> None:
        from safeauto_integration import PostActionRuleEngine

        self._engine = PostActionRuleEngine(rules=rules)

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        skill = context.get("skill", {})
        inputs = context.get("inputs", {})
        output = context.get("output", {})
        domain_state = context.get("domain_state", {})

        verdict = self._engine.evaluate(skill, inputs, output, domain_state)
        result = AdapterResult()
        result.allowed = verdict.allowed
        result.issues = [v["message"] for v in verdict.violations]
        result.warnings = [w["message"] for w in verdict.warnings]
        result.details = {**verdict.details, "source": "SafeAuto-style rule engine"}
        result.score = 1.0 if not verdict.allowed else 0.0
        return result


# ---------------------------------------------------------------------------
# E. Awesome Safety-Critical AI resources
# ---------------------------------------------------------------------------
class AwesomeSafetyCIAdapter(ExternalAdapter):
    """Adaptador curado de recursos safety-critical.

    Implementa circuit breakers y monitoreo de umbrales de confianza.
    """

    name = "awesome_safety_critical_ai"
    source_repo = "https://github.com/JGalego/awesome-safety-critical-ai"
    gate = Gate.PRE_ACTION

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        skill_name = context.get("skill", {}).get("name", "unknown")
        history = context.get("failure_history", {})
        threshold = context.get("circuit_breaker_threshold", 3)
        result = AdapterResult()

        failures = history.get(skill_name, 0)
        if failures >= threshold:
            result.allowed = False
            result.issues.append(
                f"Circuit breaker: {skill_name} tiene {failures} fallos >= {threshold}"
            )
            result.score = 1.0
        elif failures >= threshold * 0.5:
            result.warnings.append(
                f"Umbral de confianza bajo para {skill_name}: {failures} fallos"
            )

        confidence = context.get("confidence", 1.0)
        min_confidence = context.get("min_confidence", 0.6)
        if confidence < min_confidence:
            result.warnings.append(
                f"Confianza {confidence} por debajo del umbral {min_confidence}"
            )

        result.details["failures"] = failures
        result.details["confidence"] = confidence
        result.details["source"] = "Safety-critical CI heuristic"
        return result


# ---------------------------------------------------------------------------
# F. Faramesh cryptographic/deterministic boundary
# ---------------------------------------------------------------------------
class FarameshCryptoBoundaryAdapter(ExternalAdapter):
    """Adaptador para faramesh/faramesh-core: frontera criptográfica entre LLM
    y acciones externas (shell, SQL, APIs).

    Delega en `CryptoBoundary` de `faramesh_boundary.py`, que implementa HMAC,
    nonce, timestamp, anti-replay y políticas de acciones sensibles.
    """

    name = "faramesh_crypto_boundary"
    source_repo = "https://github.com/faramesh/faramesh-core"
    gate = Gate.EXECUTION

    def __init__(self, secret: Optional[str] = None) -> None:
        from faramesh_boundary import CryptoBoundary

        self._boundary = CryptoBoundary(secret=secret)

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        action = context.get("skill", {})
        inputs = context.get("inputs", {})
        signature_value = context.get("signature")

        sig, nonce, timestamp = self._boundary.extract_signature_parts(signature_value)
        verdict = self._boundary.verify_intent(
            skill_name=action.get("name", "unknown"),
            inputs=inputs,
            action_class=action.get("action_class", "read"),
            signature=sig,
            nonce=nonce,
            timestamp=timestamp,
        )

        result = AdapterResult()
        result.allowed = verdict.allowed
        result.issues = verdict.issues
        result.details = {**verdict.details, "source": "Faramesh CryptoBoundary (native)"}
        result.score = 1.0 if not verdict.allowed else 0.0
        return result


# ---------------------------------------------------------------------------
# G. Agent Policy Engine (prompt injection)
# ---------------------------------------------------------------------------
class AgentPolicyEngineAdapter(ExternalAdapter):
    """Adaptador para kahalewai/agent-policy-engine: políticas de contenido
    entrante (web, documentos, tickets, correos) contra prompt injection.

    Delega en `PromptInjectionPolicyEngine` de `prompt_injection_policy_engine.py`,
    que implementa detección de prompt injection con proveniencia, score y
    fail-closed para acciones sensibles.
    """

    name = "agent_policy_engine"
    source_repo = "https://github.com/kahalewai/agent-policy-engine"
    gate = Gate.PRE_ACTION

    def __init__(self) -> None:
        from prompt_injection_policy_engine import (
            ContentItem,
            PromptInjectionPolicyEngine,
            SourceType,
        )

        self._engine = PromptInjectionPolicyEngine()
        self._ContentItem = ContentItem
        self._SourceType = SourceType

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        from prompt_injection_policy_engine import Sensitivity

        inputs = context.get("inputs", {})
        action_class = context.get("skill", {}).get("action_class", "read")
        sensitivity = context.get("sensitivity", "medium")
        content_items = context.get("content_items", [])

        result = AdapterResult()

        if content_items:
            items = [
                self._ContentItem(
                    content=item.get("content", ""),
                    source_type=self._SourceType(item.get("source_type", "unknown")),
                    source_id=item.get("source_id"),
                    author=item.get("author"),
                    timestamp=item.get("timestamp"),
                    trust_level=item.get("trust_level"),
                    metadata=item.get("metadata", {}),
                )
                for item in content_items
            ]
        else:
            text = json.dumps(inputs, ensure_ascii=False)
            items = [
                self._ContentItem(
                    content=text,
                    source_type=self._SourceType.UNKNOWN,
                )
            ]

        verdict = self._engine.evaluate(
            items,
            action_sensitivity=Sensitivity(sensitivity),
            action_class=action_class,
        )

        result.allowed = verdict.allowed
        result.score = verdict.score
        result.issues = verdict.block_reasons
        result.warnings = verdict.warnings
        result.details = {
            "evidence_count": len(verdict.evidence),
            "evidence": verdict.evidence[:10],
            "provenance": verdict.provenance,
            "redacted_content": verdict.redacted_content,
            "source": "PromptInjectionPolicyEngine (native)",
        }
        return result


# ---------------------------------------------------------------------------
# H. Agent Guardrails (DevOps/SRE)
# ---------------------------------------------------------------------------
class AgentGuardrailsAdapter(ExternalAdapter):
    """Adaptador para roboticforce/agent-guardrails: guardrails para agentes
    DevOps/SRE, Kubernetes, IaC e infraestructura.

    Delega en `DevOpsGuardrails` de `devops_guardrails.py`, que implementa
    clasificación de comandos, detección de patrones destructivos, control de
    entornos/namespaces y requisitos de aprobación.
    """

    name = "agent_guardrails_devops"
    source_repo = "https://github.com/roboticforce/agent-guardrails"
    gate = Gate.PRE_ACTION

    def __init__(self, policy: Optional[Dict[str, Any]] = None) -> None:
        from devops_guardrails import DevOpsGuardrails, GuardrailsPolicy

        self._policy = policy
        if policy:
            self._guardrails = DevOpsGuardrails(
                policy=GuardrailsPolicy(**policy)
            )
        else:
            self._guardrails = DevOpsGuardrails()

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        inputs = context.get("inputs", {})
        command = None
        if isinstance(inputs, dict):
            command = inputs.get("command") or inputs.get("commands")
        if command is None:
            command = json.dumps(inputs, ensure_ascii=False)

        # Si recibimos una lista, evaluamos como plan
        if isinstance(command, list):
            verdict = self._guardrails.evaluate_plan(
                command,
                target_env=context.get("target_env", "unknown"),
                approval_context=context.get("approval_context", {}),
            )
            result = AdapterResult()
            result.allowed = verdict["allowed"]
            result.score = 1.0 if not verdict["allowed"] else 0.0
            if not result.allowed:
                result.issues.append(
                    f"DevOps guardrail: {verdict['commands_blocked']} command(s) blocked in plan"
                )
            result.details = {**verdict, "source": "DevOpsGuardrails (native)"}
            return result

        verdict = self._guardrails.evaluate(
            command,
            target_env=context.get("target_env", "unknown"),
            approval_context=context.get("approval_context", {}),
            metadata=context.get("metadata", {}),
        )
        result = AdapterResult()
        result.allowed = verdict.allowed
        result.score = 1.0 if not verdict.allowed else 0.0
        result.issues = verdict.issues
        result.warnings = verdict.warnings
        result.details = {**verdict.to_dict(), "source": "DevOpsGuardrails (native)"}
        return result


# ---------------------------------------------------------------------------
# I. OpenGuardrails (LLM traffic / PII)
# ---------------------------------------------------------------------------
class OpenGuardrailsAdapter(ExternalAdapter):
    """Adaptador para openguardrails/openguardrails: protección de tráfico LLM,
    PII, políticas de uso y control de proveedores/modelos.

    El repositorio upstream es un monorepo/protocolo que no es instalable
    directamente como paquete pip en este entorno. UC-324 implementa un motor
    nativo equivalente en `llm_guardrails.py`, inspirado en el contrato
    GuardEvent/Verdict de OpenGuardrails.
    """

    name = "openguardrails"
    source_repo = "https://github.com/openguardrails/openguardrails"
    gate = Gate.PRE_ACTION

    def __init__(self, policy: Optional[Dict[str, Any]] = None) -> None:
        from llm_guardrails import LLMTrafficGuardrails, LLMTrafficPolicy

        self._policy = policy
        if policy:
            self._guardrails = LLMTrafficGuardrails(
                policy=LLMTrafficPolicy.from_dict(policy)
            )
        else:
            self._guardrails = LLMTrafficGuardrails()

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        from llm_guardrails import LLMTrafficEvent, TrafficDirection

        inputs = context.get("inputs", {})
        # Si inputs ya es un evento estructurado, lo usamos directamente;
        # si es un dict genérico de skill, lo convertimos a mensajes.
        if isinstance(inputs, dict) and "messages" in inputs:
            messages = inputs.get("messages", [])
            provider = inputs.get("provider", context.get("provider", "unknown"))
            model = inputs.get("model", context.get("model", "unknown"))
            use_case = inputs.get("use_case", context.get("use_case", "general"))
            usage = inputs.get("usage", {})
            metadata = inputs.get("metadata", {})
        else:
            messages = [{"role": "user", "content": json.dumps(inputs, ensure_ascii=False)}]
            provider = context.get("provider", "unknown")
            model = context.get("model", "unknown")
            use_case = context.get("use_case", "general")
            usage = context.get("usage", {})
            metadata = context.get("metadata", {})

        direction = context.get("direction", "request")
        if isinstance(direction, TrafficDirection):
            direction = direction.value

        event = LLMTrafficEvent(
            provider=provider,
            model=model,
            direction=TrafficDirection(direction),
            messages=messages if isinstance(messages, list) else [],
            use_case=use_case,
            metadata=metadata,
            usage=usage,
        )

        verdict = self._guardrails.evaluate(event)
        result = AdapterResult()
        result.allowed = verdict.allowed
        result.score = 0.0 if verdict.allowed else 1.0
        result.issues = verdict.issues
        result.warnings = verdict.warnings
        result.details = {
            **verdict.details,
            "findings_count": len(verdict.findings),
            "source": "OpenGuardrails-style native guardrails",
        }
        # Nunca propagar los mensajes redactados si contienen placeholders que
        # aún podrían revelar qué tipo de secreto existía; aquí es seguro porque
        # los placeholders son genéricos.  Además no incluimos valores crudos.
        if verdict.redacted_messages:
            result.details["redacted_messages_preview"] = [
                {k: m.get(k) for k in ("role", "content") if k in m}
                for m in verdict.redacted_messages
            ]
        return result


# ---------------------------------------------------------------------------
# J. AgentDoG (contextual trajectory evaluation)
# ---------------------------------------------------------------------------
class AgentDoGEvalAdapter(ExternalAdapter):
    """Adaptador para AI45Lab/AgentDoG: evaluación contextual de trayectorias y
    detección de patrones inseguros.

    El repositorio AgentDoG es un framework basado en modelos que no es
    instalable directamente como paquete pip en este entorno. UC-324 implementa
    un evaluador determinista de trayectorias en `agent_dog_integration.py`
    inspirado en la taxonomía y funcionalidad de AgentDoG.
    """

    name = "agent_dog_eval"
    source_repo = "https://github.com/AI45Lab/AgentDoG"
    gate = Gate.POST_ACTION

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        from agent_dog_integration import TrajectoryEvaluator

        self._config = config or {}
        self._evaluator = TrajectoryEvaluator(**self._config)

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        trajectory = context.get("trajectory", [])
        skill = context.get("skill", {})
        output = context.get("output", {})

        # Enriquecer el último paso con el skill/output actual si no está en la
        # trayectoria (el pipeline post-action lo llama con el step actual en
        # `skill` y `output`).
        if isinstance(trajectory, list) and skill:
            step_id = skill.get("name", "current")
            if not any(s.get("step_id") == step_id for s in trajectory if isinstance(s, dict)):
                trajectory = list(trajectory) + [{
                    "step_id": step_id,
                    "skill_name": skill.get("name", "unknown"),
                    "action_class": skill.get("action_class", "read"),
                    "domain": skill.get("domain", "unknown"),
                    "status": "executed" if output.get("success", True) else "failed",
                    "inputs": context.get("inputs", {}),
                    "output": output,
                    "risk_level": skill.get("risk_level", "low"),
                    "requires_approval": skill.get("requires_approval", False),
                    "human_reviewed": context.get("human_reviewed", False),
                }]

        verdict = self._evaluator.evaluate(
            trajectory,
            declared_domain=skill.get("domain"),
            declared_goal=context.get("goal"),
            approval_context=context.get("approval_context", {}),
        )

        result = AdapterResult()
        result.allowed = verdict.allowed
        result.score = verdict.score
        for finding in verdict.findings:
            msg = f"AgentDoG: {finding.message}"
            if finding.severity.value == "critical":
                result.issues.append(msg)
            elif finding.severity.value == "high" and not result.allowed:
                result.issues.append(msg)
            else:
                result.warnings.append(msg)

        result.details = {
            **verdict.details,
            "findings": [f.to_dict() for f in verdict.findings],
            "per_step_scores": verdict.per_step_scores,
            "source": "AgentDoG-style trajectory evaluator (native)",
        }
        return result


# ---------------------------------------------------------------------------
# K. OpenAgentSafety (stage-wise evaluation)
# ---------------------------------------------------------------------------
class OpenAgentSafetyEvalAdapter(ExternalAdapter):
    """Adaptador para Open-Agent-Safety/OpenAgentSafety: observaciones en cada
    etapa del pipeline.

    El repositorio original es un benchmark de simulaciones realistas que
    requiere Docker y servicios externos; no es un paquete pip instalable. UC-324
    implementa un evaluador determinista por etapas en
    `open_agent_safety_integration.py` inspirado en las estrategias rule-based y
    LLM-as-Judge de OpenAgentSafety.
    """

    name = "open_agent_safety_eval"
    source_repo = "https://github.com/Open-Agent-Safety/OpenAgentSafety"
    gate = Gate.POST_ACTION

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        from open_agent_safety_integration import StageWiseSafetyEvaluator

        self._config = config or {}
        self._evaluator = StageWiseSafetyEvaluator(**self._config)

    def evaluate(self, context: Dict[str, Any]) -> AdapterResult:
        skill = context.get("skill", {})
        output = context.get("output", {})
        trajectory = context.get("trajectory", [])

        # Construir stages a partir de la trayectoria + step/output actual.
        stages: List[Dict[str, Any]] = []
        for item in trajectory:
            if not isinstance(item, dict):
                continue
            stages.append({
                "stage_id": item.get("step_id", item.get("skill_name", "-")),
                "name": item.get("skill_name", "unknown"),
                "action_class": item.get("action_class", "read"),
                "domain": item.get("domain", "unknown"),
                "status": item.get("status", "executed"),
                "inputs": item.get("inputs", {}),
                "output": item.get("output", {}),
                "risk_level": item.get("risk_level", "low"),
                "requires_approval": item.get("requires_approval", False),
                "human_reviewed": context.get("human_reviewed", False),
            })

        # Añadir el paso actual si no viene en la trayectoria.
        if skill:
            current_id = skill.get("name", "current")
            if not any(s.get("stage_id") == current_id for s in stages):
                stages.append({
                    "stage_id": current_id,
                    "name": skill.get("name", "unknown"),
                    "action_class": skill.get("action_class", "read"),
                    "domain": skill.get("domain", "unknown"),
                    "status": "executed" if output.get("success", True) else "failed",
                    "inputs": context.get("inputs", {}),
                    "output": output,
                    "risk_level": skill.get("risk_level", "low"),
                    "requires_approval": skill.get("requires_approval", False),
                    "human_reviewed": context.get("human_reviewed", False),
                })

        verdict = self._evaluator.evaluate(
            stages,
            declared_domain=skill.get("domain") if skill else None,
            declared_goal=context.get("goal"),
        )

        result = AdapterResult()
        result.allowed = verdict.allowed
        result.score = verdict.score
        for finding in verdict.findings:
            msg = f"OpenAgentSafety: {finding.message}"
            if finding.severity.value in ("critical", "high"):
                result.issues.append(msg)
            else:
                result.warnings.append(msg)

        result.details = {
            **verdict.details,
            "findings": [f.to_dict() for f in verdict.findings],
            "per_stage_scores": verdict.per_stage_scores,
            "source": "OpenAgentSafety-style stage-wise evaluator (native)",
        }
        return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def build_default_adapters(secret: Optional[str] = None) -> List[ExternalAdapter]:
    """Construye los adapters por defecto; `secret` para la frontera criptográfica."""
    return [
        AGTGovernanceAdapter(),
        AdaptiveStressTestingAdapter(),
        AISafetyRedTeamAdapter(),
        AwesomeSafetyCIAdapter(),
        AgentPolicyEngineAdapter(),
        AgentGuardrailsAdapter(),
        OpenGuardrailsAdapter(),
        FarameshCryptoBoundaryAdapter(secret=secret),
        SafeAutoPostActionAdapter(),
        AgentDoGEvalAdapter(),
        OpenAgentSafetyEvalAdapter(),
    ]
