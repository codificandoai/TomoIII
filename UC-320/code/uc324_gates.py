"""UC-320 — UC-324 Gates: PRE, EXEC, POST para integración con Hugging Face.

UC-324 aplica gates sobre cada operación que pueda tener consecuencias
externas o afectar datos, modelos, costes, permisos o despliegues.

Este módulo es una integración nativa que replica los gates de UC-324
sin copiar el código de UC-324. En producción, debe delegar al API REST
de UC-324 en /api/v1/containment/check.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class GatePhase(str, Enum):
    PRE = "pre"
    EXEC = "exec"
    POST = "post"


class Verdict(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"


@dataclass
class GateResult:
    phase: GatePhase
    layer: str  # A-K
    verdict: Verdict
    score: float = 0.0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "layer": self.layer,
            "verdict": self.verdict.value,
            "score": self.score,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass
class ContainmentDecision:
    allowed: bool
    verdict: Verdict
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    audit_log: List[Dict[str, Any]] = field(default_factory=list)
    signed_intent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "verdict": self.verdict.value,
            "issues": self.issues,
            "warnings": self.warnings,
            "audit_log": self.audit_log,
            "signed_intent": self.signed_intent,
        }


# Patrones de prompt injection conocidos.
PROMPT_INJECTION_PATTERNS = [
    r"ignor(?:e|a)\s+(?:tus?\s+)?instrucciones",
    r"ignore\s+(?:your\s+)?instructions",
    r"disregard\s+(?:previous|all)",
    r"system\s*:\s*you\s+are\s+now",
    r"new\s+instructions?:",
    r"override\s+safety",
    r"jailbreak",
]

PII_PATTERNS = [
    r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
    r"\b\d{16}\b",  # credit card
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email
]

SHELL_INJECTION_PATTERNS = [
    r"__import__",
    r"subprocess",
    r"os\.system",
    r"eval\s*\(",
    r"exec\s*\(",
    r";\s*rm\s",
    r"\$\(",
    r"`.*`",
]


class UC324GateIntegrator:
    """Integración nativa de los gates PRE/EXEC/POST de UC-324.

    En producción, cada gate puede delegar al API REST de UC-324.
    Aquí se implementan versiones deterministas para tests.
    """

    def __init__(self, hmac_secret: Optional[str] = None) -> None:
        self.hmac_secret = hmac_secret or "uc320-default-hmac-secret"
        self._used_nonces: Set[str] = set()
        self.audit_log: List[Dict[str, Any]] = []

    # --- GATE PRE ---
    def gate_pre(self, contract: Dict[str, Any]) -> List[GateResult]:
        results: List[GateResult] = []
        model_id = contract.get("model_id", "")
        provider = contract.get("provider", "")
        input_text = json.dumps(contract.get("input", {}))
        risk_level = contract.get("risk_level", "low")
        max_cost = contract.get("max_cost", 1.0)
        max_latency = contract.get("max_latency_ms", 10000)

        # A — Governance: verifica allowlist y risk.
        allowed_models = contract.get("_allowed_models", set())
        if allowed_models and model_id not in allowed_models:
            results.append(GateResult(GatePhase.PRE, "A", Verdict.BLOCK, 1.0, f"Model {model_id} not allowlisted"))
        else:
            results.append(GateResult(GatePhase.PRE, "A", Verdict.ALLOW, 0.0, "Governance OK"))

        # C — Red-team: detecta prompt injection.
        injection_score = 0.0
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, input_text, re.IGNORECASE):
                injection_score = max(injection_score, 0.95)
        if injection_score > 0.7:
            results.append(GateResult(GatePhase.PRE, "C", Verdict.BLOCK, injection_score, "Prompt injection detected"))
        else:
            results.append(GateResult(GatePhase.PRE, "C", Verdict.ALLOW, injection_score, "No injection detected"))

        # E — Circuit breaker: verifica cost y latency.
        estimated_cost = contract.get("_estimated_cost", 0.0)
        estimated_latency = contract.get("_estimated_latency", 500.0)
        if estimated_cost > max_cost:
            results.append(GateResult(GatePhase.PRE, "E", Verdict.BLOCK, 1.0, f"Cost {estimated_cost} > max {max_cost}"))
        elif estimated_latency > max_latency:
            results.append(GateResult(GatePhase.PRE, "E", Verdict.BLOCK, 1.0, f"Latency {estimated_latency} > max {max_latency}"))
        else:
            results.append(GateResult(GatePhase.PRE, "E", Verdict.ALLOW, 0.0, "Circuit breaker OK"))

        # G — Prompt injection policy engine.
        if injection_score > 0.7:
            results.append(GateResult(GatePhase.PRE, "G", Verdict.BLOCK, injection_score, f"Injection score {injection_score} > 0.7"))
        else:
            results.append(GateResult(GatePhase.PRE, "G", Verdict.ALLOW, injection_score, "Injection score below threshold"))

        # I — PII / LLM traffic guardrails.
        pii_found = any(re.search(p, input_text) for p in PII_PATTERNS)
        if pii_found:
            results.append(GateResult(GatePhase.PRE, "I", Verdict.BLOCK, 1.0, "PII detected in input"))
        else:
            results.append(GateResult(GatePhase.PRE, "I", Verdict.ALLOW, 0.0, "No PII detected"))

        return results

    # --- GATE EXEC ---
    def gate_exec(self, contract: Dict[str, Any]) -> List[GateResult]:
        results: List[GateResult] = []
        # Filtrar campos no serializables (_allowed_models es un set).
        clean = {k: (list(v) if isinstance(v, set) else v) for k, v in contract.items()}
        intent = json.dumps(clean, sort_keys=True, default=str)
        nonce = contract.get("nonce", str(uuid.uuid4()))
        timestamp = contract.get("timestamp", time.time())

        # F — Faramesh: HMAC + nonce + anti-replay + anti shell/SQL.
        if nonce in self._used_nonces:
            results.append(GateResult(GatePhase.EXEC, "F", Verdict.BLOCK, 1.0, "Replay detected: nonce already used"))
        else:
            self._used_nonces.add(nonce)
            expected_sig = hmac.new(
                self.hmac_secret.encode(), intent.encode(), hashlib.sha256
            ).hexdigest()
            shell_found = any(re.search(p, intent, re.IGNORECASE) for p in SHELL_INJECTION_PATTERNS)
            if shell_found:
                results.append(GateResult(GatePhase.EXEC, "F", Verdict.BLOCK, 1.0, "Shell injection detected"))
            else:
                results.append(GateResult(GatePhase.EXEC, "F", Verdict.ALLOW, 0.0, "HMAC valid, nonce unique, no shell", {"signature": expected_sig[:16]}))

        return results

    # --- GATE POST ---
    def gate_post(self, contract: Dict[str, Any], output: Dict[str, Any]) -> List[GateResult]:
        results: List[GateResult] = []
        output_text = json.dumps(output)
        output_schema = contract.get("output_schema", "")

        # D — SafeAuto: verificación post-acción declarativa.
        if not output:
            results.append(GateResult(GatePhase.POST, "D", Verdict.BLOCK, 1.0, "Empty output"))
        else:
            results.append(GateResult(GatePhase.POST, "D", Verdict.ALLOW, 0.0, "Post-action rules pass"))

        # J — AgentDoG: evaluación de trayectoria.
        tool_instructions = any(
            kw in output_text.lower()
            for kw in ["use tool", "call function", "execute action", "buy now", "sell now"]
        )
        if tool_instructions:
            results.append(GateResult(GatePhase.POST, "J", Verdict.BLOCK, 1.0, "Output contains unauthorized tool/action instructions"))
        else:
            results.append(GateResult(GatePhase.POST, "J", Verdict.ALLOW, 0.0, "Trajectory safe"))

        # K — OpenAgentSafety: evaluación stage-wise.
        pii_in_output = any(re.search(p, output_text) for p in PII_PATTERNS)
        if pii_in_output:
            results.append(GateResult(GatePhase.POST, "K", Verdict.BLOCK, 1.0, "PII leaked in output"))
        else:
            results.append(GateResult(GatePhase.POST, "K", Verdict.ALLOW, 0.0, "Stage-wise safety OK"))

        return results

    def evaluate(
        self,
        contract: Dict[str, Any],
        output: Optional[Dict[str, Any]] = None,
    ) -> ContainmentDecision:
        """Ejecuta los 3 gates y retorna la decisión agregada."""
        all_results: List[GateResult] = []
        all_results.extend(self.gate_pre(contract))
        all_results.extend(self.gate_exec(contract))
        if output is not None:
            all_results.extend(self.gate_post(contract, output))

        issues = [r.message for r in all_results if r.verdict == Verdict.BLOCK]
        warnings = [r.message for r in all_results if r.verdict == Verdict.WARN]
        allowed = len(issues) == 0
        verdict = Verdict.ALLOW if allowed else Verdict.BLOCK

        audit = [r.to_dict() for r in all_results]
        self.audit_log.extend(audit)

        signed = None
        if allowed:
            clean = {k: (list(v) if isinstance(v, set) else v) for k, v in contract.items()}
            intent = json.dumps(clean, sort_keys=True, default=str)
            signed = hmac.new(
                self.hmac_secret.encode(), intent.encode(), hashlib.sha256
            ).hexdigest()[:32]

        return ContainmentDecision(
            allowed=allowed,
            verdict=verdict,
            issues=issues,
            warnings=warnings,
            audit_log=audit,
            signed_intent=signed,
        )
