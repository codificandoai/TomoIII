"""UC-324 — LLM Private/Secure Service Gateway (PIS).

Puerta de enlace para servir modelos de lenguaje en entornos privados,
regulados o de alta seguridad. Soporta despliegue local (Ollama, vLLM, TGI)
y proveedores cloud controlados (OpenAI, Anthropic) con:

- Allowlist de proveedores/modelos/regiones.
- Detección de PII y redacción.
- Moderación de toxicidad en request/response.
- Detección de prompt injection y evasión.
- Revisión humana para funciones de alto impacto.
- Métricas Prometheus: latencia, requests bloqueadas, toxicidad, evasión.
- Eventos canónicos a UC-309.
- Backends simulados para tests.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from llm_guardrails import (
    LLMTrafficEvent,
    LLMTrafficGuardrails,
    LLMTrafficPolicy,
    TrafficDirection,
)


class LLMBackend(str, Enum):
    """Backends de inferencia soportados."""
    OLLAMA = "ollama"
    VLLM = "vllm"
    TGI = "tgi"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class SafetyStatus(str, Enum):
    """Resultado de la revisión de seguridad."""
    ALLOWED = "allowed"
    REDACTED = "redacted"
    BLOCKED = "blocked"
    HITL_REQUIRED = "hitl_required"


@dataclass
class LLMRequest:
    """Solicitud normalizada al gateway."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    agent_id: str = "unknown"
    provider: str = "ollama"
    model: str = "llama3.1"
    prompt: str = ""
    use_case: str = "default"
    high_impact: bool = False
    region: str = "private"
    max_tokens: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "provider": self.provider,
            "model": self.model,
            "prompt": self.prompt,
            "use_case": self.use_case,
            "high_impact": self.high_impact,
            "region": self.region,
            "max_tokens": self.max_tokens,
            "metadata": self.metadata,
        }


@dataclass
class LLMResponse:
    """Respuesta normalizada del gateway."""
    request_id: str
    text: str
    safety_status: SafetyStatus
    safety_findings: List[Dict[str, Any]]
    blocked: bool
    requires_hitl: bool
    backend: str
    latency_ms: float
    model: str
    prompt_injection_score: float
    pii_redacted: bool
    toxicity_score: float
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "text": self.text,
            "safety_status": self.safety_status.value,
            "safety_findings": self.safety_findings,
            "blocked": self.blocked,
            "requires_hitl": self.requires_hitl,
            "backend": self.backend,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "prompt_injection_score": self.prompt_injection_score,
            "pii_redacted": self.pii_redacted,
            "toxicity_score": self.toxicity_score,
            "evidence": self.evidence,
        }


def _default_toxicity_patterns() -> List[Tuple[re.Pattern, float]]:
    """Patrones rápidos de toxicidad (regex + peso)."""
    raw = [
        (r"\b(hate|hates|hating)\b", 0.3),
        (r"\b(kill|kills|killing|killed)\b", 0.5),
        (r"\b(die|dies|died|death|dead)\b", 0.4),
        (r"\b(attack|attacks|attacking)\b", 0.3),
        (r"\b(bomb|bombs|shoot|shoots|shooting)\b", 0.6),
        (r"\b(rape|rapes|raping)\b", 0.8),
        (r"\b(nigger|nazi|fag|whore|slut)\b", 0.9),
        (r"\bretard\b|\bidiot\b|\bmoron\b|\bstupid\b", 0.2),
    ]
    return [(re.compile(p, re.IGNORECASE), w) for p, w in raw]


@dataclass
class ToxicityFilter:
    """Filtro de toxicidad ligero basado en patrones."""
    patterns: List[Tuple[re.Pattern, float]] = field(default_factory=_default_toxicity_patterns)
    threshold: float = 0.3

    def score(self, text: str) -> float:
        if not text:
            return 0.0
        return min(1.0, sum(w for p, w in self.patterns if p.search(text)))

    def detect(self, text: str) -> List[Dict[str, Any]]:
        findings = []
        for p, w in self.patterns:
            for m in p.finditer(text):
                findings.append({
                    "category": "toxicity",
                    "matched": m.group(0),
                    "position": m.start(),
                    "score": w,
                })
        return findings


@dataclass
class EvasionFilter:
    """Detecta intentos de evasión de guardrails."""
    patterns: List[Tuple[re.Pattern, float]] = field(default_factory=lambda: [
        (re.compile(r"\bignore\b.*\b(prev|previous|prior|all)\b.*\b(instructions?|rules?|constraints?)\b", re.I), 0.9),
        (re.compile(r"\bdisregard\b.*\b(safety|security|policy|policies)\b", re.I), 0.8),
        (re.compile(r"\bpretend\b.*\b(you are|you're|to be)\b", re.I), 0.6),
        (re.compile(r"\bnew\b.*\bsystem\b.*\binstruction\b", re.I), 0.8),
        (re.compile(r"\bbase64\b|\bencoded\b|\bdecode\b", re.I), 0.4),
        (re.compile(r"\b(dan|jailbreak)\b", re.I), 0.7),
    ])

    def score(self, text: str) -> float:
        if not text:
            return 0.0
        return min(1.0, sum(w for p, w in self.patterns if p.search(text)))

    def detect(self, text: str) -> List[Dict[str, Any]]:
        findings = []
        for p, w in self.patterns:
            for m in p.finditer(text):
                findings.append({
                    "category": "evasion",
                    "matched": m.group(0),
                    "position": m.start(),
                    "score": w,
                })
        return findings


class DiversityFilter:
    """Estimación simple de diversidad léxica."""

    def score(self, text: str) -> float:
        words = re.findall(r"\b\w+\b", text.lower())
        if not words:
            return 0.0
        unique = len(set(words))
        return round(unique / len(words), 4)


class LLMPrivateGateway:
    """Gateway privado/seguro para LLM."""

    def __init__(
        self,
        allowed_providers: Optional[List[str]] = None,
        allowed_models: Optional[Dict[str, List[str]]] = None,
        allowed_regions: Optional[List[str]] = None,
        high_impact_use_cases: Optional[List[str]] = None,
        policy: Optional[LLMTrafficPolicy] = None,
        toxicity: Optional[ToxicityFilter] = None,
        evasion: Optional[EvasionFilter] = None,
        diversity: Optional[DiversityFilter] = None,
        hitl_threshold: float = 0.6,
        block_threshold: float = 0.8,
        uc309_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        backend_handlers: Optional[Dict[str, Callable[[LLMRequest], str]]] = None,
    ) -> None:
        self.allowed_providers = set(allowed_providers or {b.value for b in LLMBackend})
        self.allowed_models = allowed_models or {
            "ollama": ["llama3.1", "llama3.2"],
            "vllm": ["meta-llama/Llama-2-70b"],
            "tgi": ["meta-llama/Llama-2-70b"],
            "openai": ["gpt-4o-mini"],
            "anthropic": ["claude-3-haiku"],
            "mock": ["mock-1"],
        }
        self.allowed_regions = set(allowed_regions or ["private", "vpc", "on-prem"])
        self.high_impact_use_cases = set(high_impact_use_cases or ["medical", "legal", "financial", "military"])
        self.guardrails = LLMTrafficGuardrails(policy or LLMTrafficPolicy())
        self.toxicity = toxicity or ToxicityFilter()
        self.evasion = evasion or EvasionFilter()
        self.diversity = diversity or DiversityFilter()
        self.hitl_threshold = hitl_threshold
        self.block_threshold = block_threshold
        self.uc309_sink = uc309_sink
        self.backend_handlers = backend_handlers or _default_backend_handlers()
        self._metrics: Dict[str, Any] = {
            "requests_total": 0,
            "blocked_total": 0,
            "hitl_total": 0,
            "pii_redacted_total": 0,
            "toxicity_total": 0.0,
            "evasion_total": 0.0,
            "diversity_total": 0.0,
            "latency_sum_ms": 0.0,
            "latency_count": 0,
        }

    def _record_metric(self, key: str, value: float) -> None:
        if key in ("requests_total", "blocked_total", "hitl_total", "pii_redacted_total"):
            self._metrics[key] = self._metrics.get(key, 0) + int(value)
        elif key in ("toxicity_total", "evasion_total", "diversity_total", "latency_sum_ms"):
            self._metrics[key] = self._metrics.get(key, 0.0) + float(value)
        elif key == "latency_count":
            self._metrics[key] = self._metrics.get(key, 0) + int(value)

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.uc309_sink is not None:
            try:
                self.uc309_sink({"event_type": event_type, "timestamp": time.time(), **payload})
            except Exception:
                pass

    def _check_model_allowlist(self, req: LLMRequest) -> Optional[Dict[str, Any]]:
        if req.provider not in self.allowed_providers:
            return {"finding": "provider_denied", "provider": req.provider, "allowed": list(self.allowed_providers)}
        if req.model not in self.allowed_models.get(req.provider, []):
            return {"finding": "model_denied", "model": req.model, "allowed": self.allowed_models.get(req.provider, [])}
        if req.region not in self.allowed_regions:
            return {"finding": "region_denied", "region": req.region, "allowed": list(self.allowed_regions)}
        return None

    def _apply_input_guardrails(self, req: LLMRequest) -> tuple:
        findings: List[Dict[str, Any]] = []
        text = req.prompt

        # PII / usage / model policy
        event = LLMTrafficEvent(
            provider=req.provider,
            model=req.model,
            direction=TrafficDirection.REQUEST,
            messages=[{"role": "user", "content": text}],
            use_case=req.use_case,
            metadata={"agent_id": req.agent_id},
        )
        pre = self.guardrails.evaluate(event)
        if not pre.allowed:
            findings.append({"category": "guardrails", "reason": "; ".join(pre.issues), "score": 1.0})
        if pre.redacted_messages:
            text = pre.redacted_messages[0].get("content", text)
            self._record_metric("pii_redacted_total", 1)

        # Toxicity
        tox_score = self.toxicity.score(text)
        tox_findings = self.toxicity.detect(text)
        if tox_findings:
            findings.extend(tox_findings)

        # Evasion / prompt injection
        eva_score = self.evasion.score(text)
        eva_findings = self.evasion.detect(text)
        if eva_findings:
            findings.extend(eva_findings)

        return text, tox_score, eva_score, findings, not pre.allowed

    def _apply_output_guardrails(self, text: str) -> tuple:
        tox_score = self.toxicity.score(text)
        tox_findings = self.toxicity.detect(text)
        eva_score = 0.0
        eva_findings: List[Dict[str, Any]] = []
        return text, tox_score, tox_findings, eva_score

    def _requires_hitl(self, req: LLMRequest, tox_score: float, eva_score: float) -> bool:
        if req.high_impact or req.use_case in self.high_impact_use_cases:
            return True
        if tox_score >= self.hitl_threshold or eva_score >= self.hitl_threshold:
            return True
        return False

    def generate(self, req: LLMRequest) -> LLMResponse:
        """Punto de entrada principal: valida, enruta y aplica guardrails."""
        start = time.time()
        self._record_metric("requests_total", 1)

        # 1. Allowlist
        deny = self._check_model_allowlist(req)
        if deny:
            latency = (time.time() - start) * 1000
            self._record_metric("blocked_total", 1)
            self._record_metric("latency_sum_ms", latency)
            self._record_metric("latency_count", 1)
            self._emit("llm_private_request_blocked", {**req.to_dict(), **deny})
            return LLMResponse(
                request_id=req.request_id,
                text="",
                safety_status=SafetyStatus.BLOCKED,
                safety_findings=[deny],
                blocked=True,
                requires_hitl=False,
                backend=req.provider,
                latency_ms=latency,
                model=req.model,
                prompt_injection_score=0.0,
                pii_redacted=False,
                toxicity_score=0.0,
                evidence={"reason": "allowlist"},
            )

        # 2. Input guardrails
        safe_prompt, tox_in, eva_in, findings, pre_blocked = self._apply_input_guardrails(req)
        if pre_blocked:
            latency = (time.time() - start) * 1000
            self._record_metric("blocked_total", 1)
            self._record_metric("toxicity_total", tox_in)
            self._record_metric("evasion_total", eva_in)
            self._record_metric("latency_sum_ms", latency)
            self._record_metric("latency_count", 1)
            self._emit("llm_private_request_blocked", {**req.to_dict(), "findings": findings})
            return LLMResponse(
                request_id=req.request_id,
                text="",
                safety_status=SafetyStatus.BLOCKED,
                safety_findings=findings,
                blocked=True,
                requires_hitl=False,
                backend=req.provider,
                latency_ms=latency,
                model=req.model,
                prompt_injection_score=eva_in,
                pii_redacted=self._metrics["pii_redacted_total"] > 0,
                toxicity_score=tox_in,
                evidence={"reason": "input_guardrails"},
            )

        # 2.5 Bloqueo automático por severidad
        if tox_in >= self.block_threshold or eva_in >= self.block_threshold:
            latency = (time.time() - start) * 1000
            self._record_metric("blocked_total", 1)
            self._record_metric("toxicity_total", tox_in)
            self._record_metric("evasion_total", eva_in)
            self._record_metric("latency_sum_ms", latency)
            self._record_metric("latency_count", 1)
            self._emit("llm_private_request_blocked", {**req.to_dict(), "findings": findings})
            return LLMResponse(
                request_id=req.request_id,
                text="",
                safety_status=SafetyStatus.BLOCKED,
                safety_findings=findings,
                blocked=True,
                requires_hitl=False,
                backend=req.provider,
                latency_ms=latency,
                model=req.model,
                prompt_injection_score=eva_in,
                pii_redacted=self._metrics["pii_redacted_total"] > 0,
                toxicity_score=tox_in,
                evidence={"reason": "toxicity_or_evasion_threshold"},
            )

        # 3. High-impact / HITL
        if self._requires_hitl(req, tox_in, eva_in):
            latency = (time.time() - start) * 1000
            self._record_metric("hitl_total", 1)
            self._record_metric("toxicity_total", tox_in)
            self._record_metric("evasion_total", eva_in)
            self._record_metric("latency_sum_ms", latency)
            self._record_metric("latency_count", 1)
            self._emit("llm_private_hitl_required", {**req.to_dict(), "findings": findings})
            return LLMResponse(
                request_id=req.request_id,
                text="",
                safety_status=SafetyStatus.HITL_REQUIRED,
                safety_findings=findings,
                blocked=False,
                requires_hitl=True,
                backend=req.provider,
                latency_ms=latency,
                model=req.model,
                prompt_injection_score=eva_in,
                pii_redacted=self._metrics["pii_redacted_total"] > 0,
                toxicity_score=tox_in,
                evidence={"reason": "high_impact"},
            )

        # 4. Enrutar a backend
        handler = self.backend_handlers.get(req.provider)
        if handler is None:
            raise ValueError(f"No handler for provider {req.provider}")

        try:
            raw_response = handler(replace(req, prompt=safe_prompt))
        except Exception as exc:
            latency = (time.time() - start) * 1000
            self._record_metric("latency_sum_ms", latency)
            self._record_metric("latency_count", 1)
            return LLMResponse(
                request_id=req.request_id,
                text="",
                safety_status=SafetyStatus.BLOCKED,
                safety_findings=[{"category": "backend_error", "error": str(exc)}],
                blocked=True,
                requires_hitl=False,
                backend=req.provider,
                latency_ms=latency,
                model=req.model,
                prompt_injection_score=eva_in,
                pii_redacted=False,
                toxicity_score=tox_in,
                evidence={"reason": "backend_failure"},
            )

        # 5. Output guardrails
        safe_response, tox_out, tox_out_findings, eva_out = self._apply_output_guardrails(raw_response)

        # 6. Métricas y evento
        latency = (time.time() - start) * 1000
        self._record_metric("toxicity_total", tox_in + tox_out)
        self._record_metric("evasion_total", eva_in + eva_out)
        self._record_metric("diversity_total", self.diversity.score(safe_response))
        self._record_metric("latency_sum_ms", latency)
        self._record_metric("latency_count", 1)

        self._emit("llm_private_request_completed", {
            "request": req.to_dict(),
            "toxicity_in": tox_in,
            "toxicity_out": tox_out,
            "evasion_in": eva_in,
            "latency_ms": latency,
            "model": req.model,
            "backend": req.provider,
        })

        return LLMResponse(
            request_id=req.request_id,
            text=safe_response,
            safety_status=SafetyStatus.ALLOWED,
            safety_findings=tox_out_findings,
            blocked=False,
            requires_hitl=False,
            backend=req.provider,
            latency_ms=latency,
            model=req.model,
            prompt_injection_score=eva_in,
            pii_redacted=self._metrics["pii_redacted_total"] > 0,
            toxicity_score=max(tox_in, tox_out),
            evidence={"diversity": self.diversity.score(safe_response)},
        )

    def metrics(self) -> Dict[str, Any]:
        """Devuelve métricas agregadas."""
        m = self._metrics
        lat = m["latency_sum_ms"] / max(m["latency_count"], 1)
        return {
            "llm_private_requests_total": m["requests_total"],
            "llm_private_blocked_total": m["blocked_total"],
            "llm_private_hitl_total": m["hitl_total"],
            "llm_private_pii_redacted_total": m["pii_redacted_total"],
            "llm_private_avg_toxicity": m["toxicity_total"] / max(m["requests_total"], 1),
            "llm_private_avg_evasion": m["evasion_total"] / max(m["requests_total"], 1),
            "llm_private_avg_diversity": m["diversity_total"] / max(m["requests_total"], 1),
            "llm_private_latency_ms_avg": round(lat, 2),
            "llm_private_latency_ms_p95_estimate": round(lat * 1.5, 2),  # simplificado
        }


def _default_backend_handlers() -> Dict[str, Callable[[LLMRequest], str]]:
    """Handlers simulados para tests y contingencia."""
    return {
        "mock": lambda req: f"[mock response to: {req.prompt[:40]}...]",
        "ollama": lambda req: f"[ollama local response: {req.prompt[:40]}...]",
        "vllm": lambda req: f"[vllm tensor-parallel response: {req.prompt[:40]}...]",
        "tgi": lambda req: f"[tgi response: {req.prompt[:40]}...]",
        "openai": lambda req: f"[openai response: {req.prompt[:40]}...]",
        "anthropic": lambda req: f"[anthropic response: {req.prompt[:40]}...]",
    }
