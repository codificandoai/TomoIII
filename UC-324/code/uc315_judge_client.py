"""UC-324 — Cliente externo de LLM-as-a-judge para contenido no confiable.

Este módulo proporciona una capa de jucio externo aislada de UC-315:
- UC-315 (o cualquier LLM) actúa como generador de evidencia, no como gate.
- UC-324 conserva el veredicto final determinista.
- El cliente puede conectarse a un endpoint real de UC-315, a un callable
  inyectado, o usar un stub heurístico que simula un juez semántico.

Principios:
1. El juez nunca decide allow/block.
2. El juez devuelve un risk_score, señales y explicación.
3. UC-300/UC-324 combinan ese score con reglas fijas.
4. El agent_id del juez es distinto al del agente que ejecuta.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class JudgeResult:
    """Veredicto del juez: evidencia, no orden."""
    risk_score: float  # 0.0 - 1.0
    manipulation_signals: List[str] = field(default_factory=list)
    explanation: str = ""
    judge_source: str = "unknown"  # stub, endpoint, callable
    raw_evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 4),
            "manipulation_signals": self.manipulation_signals,
            "explanation": self.explanation,
            "judge_source": self.judge_source,
            "raw_evidence": self.raw_evidence,
        }


# Señales semánticas que un juez LLM debería detectar.
SEMANTIC_MANIPULATION_PATTERNS = [
    (r"\bignore\b.*\b(?:previous|prior|all)\b.*\b(?:instructions?|rules?|constraints?)\b", "ignore_instructions"),
    (r"\bdisregard\b.*\b(?:safety|security|policy|policies|rules?)\b", "disregard_safety"),
    (r"\bsystem\b.*\bprompt\b", "system_prompt_leak"),
    (r"\bnew\b.*\bsystem\b.*\binstruction", "new_system_instruction"),
    (r"\brole\b.*\b(?:override|change|switch|play)\b", "role_override"),
    (r"\bpretend\b.*\b(?:to be|you are|you're)\b", "pretend_role"),
    (r"\bDAN\b|\bDo Anything Now\b", "dan_jailbreak"),
    (r"\bjailbreak\b|\bmode\b.*\bdeveloper\b", "jailbreak_keyword"),
    (r"\bnow\b.*\b(?:can you|you can)\b.*\b(?:harm|illegal|steal|leak)\b", "permission_escalation"),
    (r"\bforget\b.*\b(?:everything|all|your)\b.*\b(?:instructions?|training)\b", "forget_training"),
    (r"\bthis\b.*\b(?:is|was)\b.*\b(?:a test|testing|just a joke)\b", "post_hoc_override"),
    (r"\byou\b.*\b(?:must|should|will)\b.*\b(?:not|never)\b.*\b(?:disclose|tell|reveal)\b", "secrecy_coercion"),
    (r"\bencode\b|\bbase64\b|\bdecode\b", "encoding_request"),
    (r"\brepeat\b.*\b(?:after me|word for word|verbatim)\b", "repetition_trap"),
    (r"\bwhat\b.*\b(?:system|developer|initial|hidden)\b.*\b(?:prompt|instruction|message)\b", "prompt_extraction"),
]


def _stub_judge_score(content: str) -> float:
    """Stub determinista que simula un análisis semántico superficial."""
    text = content.lower()
    score = 0.0
    for pattern, _signal in SEMANTIC_MANIPULATION_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        score += 0.12 * len(matches)
    # Palabras clave de riesgo adicionales
    risk_keywords = [
        "ignore", "disregard", "jailbreak", "system prompt", "new instruction",
        "pretend", "role play", "DAN", "do anything now", "leak", "steal",
        "bypass", "override", "forget", "encoded", "base64", "hidden",
    ]
    for kw in risk_keywords:
        if kw in text:
            score += 0.05
    # Penalizar contenido corto pero intenso
    if len(text) < 100:
        score = min(score * 1.5, 1.0)
    return round(min(score, 1.0), 4)


def _stub_judge(content: str, context: Optional[Dict[str, Any]] = None) -> JudgeResult:
    """Juez stub: no depende de UC-315; útil para tests y contingencia."""
    score = _stub_judge_score(content)
    text = content.lower()
    signals = []
    for pattern, signal in SEMANTIC_MANIPULATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            if signal not in signals:
                signals.append(signal)
    if score >= 0.7:
        explanation = f"Alto riesgo de manipulación detectado (score={score}): {', '.join(signals[:3])}."
    elif score >= 0.4:
        explanation = f"Riesgo moderado de manipulación (score={score}): {', '.join(signals[:2] or ['patrones ambiguos'])}."
    else:
        explanation = f"Bajo riesgo de manipulación (score={score})."
    return JudgeResult(
        risk_score=score,
        manipulation_signals=signals,
        explanation=explanation,
        judge_source="stub",
        raw_evidence={"semantic_pattern_hits": len(signals), "content_length": len(content)},
    )


class UC315JudgeClient:
    """Cliente externo que consulta a un LLM-as-a-judge por evidencia."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        judge_fn: Optional[Callable[[str, Optional[Dict[str, Any]]], JudgeResult]] = None,
        timeout_seconds: float = 5.0,
        judge_agent_id: str = "uc315-llm-judge",
    ) -> None:
        self.endpoint = endpoint or os.environ.get("UC315_JUDGE_ENDPOINT", "")
        self.judge_fn = judge_fn
        self.timeout = timeout_seconds
        self.judge_agent_id = judge_agent_id

    def judge(
        self,
        content: str,
        source_type: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
    ) -> JudgeResult:
        """Consulta al juez y devuelve evidencia. Nunca bloquea."""
        ctx = context or {}
        ctx["source_type"] = source_type
        ctx["judge_agent_id"] = self.judge_agent_id

        # Prioridad 1: callable inyectado (p.ej. adaptador real a UC-315)
        if self.judge_fn is not None:
            try:
                return self.judge_fn(content, ctx)
            except Exception as exc:
                return JudgeResult(
                    risk_score=0.0,
                    manipulation_signals=["judge_callable_error"],
                    explanation=f"Judge callable failed: {exc}. Falling back to stub.",
                    judge_source="callable-error",
                )

        # Prioridad 2: endpoint HTTP de UC-315
        if self.endpoint and HAS_REQUESTS:
            try:
                resp = requests.post(
                    self.endpoint,
                    json={"content": content, "context": ctx, "task": "prompt_injection_judge"},
                    timeout=self.timeout,
                )
                data = resp.json()
                return JudgeResult(
                    risk_score=float(data.get("risk_score", 0.0)),
                    manipulation_signals=data.get("manipulation_signals", []),
                    explanation=data.get("explanation", ""),
                    judge_source=f"endpoint:{self.endpoint}",
                    raw_evidence=data,
                )
            except Exception as exc:
                return JudgeResult(
                    risk_score=0.0,
                    manipulation_signals=["judge_endpoint_error"],
                    explanation=f"Judge endpoint failed: {exc}. Falling back to stub.",
                    judge_source="endpoint-error",
                )

        # Prioridad 3: stub heurístico
        return _stub_judge(content, ctx)
