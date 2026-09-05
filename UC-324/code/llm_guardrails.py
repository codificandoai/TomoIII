"""UC-324 — OpenGuardrails-style guardrails para tráfico LLM.

Implementación nativa/fallback inspirada en el protocolo OpenGuardrails
(https://github.com/openguardrails/openguardrails). Protege el tráfico entre
aplicaciones/agentes y proveedores de LLM mediante:

- Detección y redacción/bloqueo de PII.
- Políticas de uso (casos de uso, categorías de contenido, límites de tokens,
  coste y tasa).
- Control de proveedores/modelos (allowlists, denylists, asignación por caso
  de uso).
- Inspección de request/response y auditoría sin exponer secretos ni PII.

El repositorio OpenGuardrails no es instalable directamente como paquete pip
en este entorno (falla con "Multiple top-level packages discovered in a
flat-layout"); por eso UC-324 implementa un motor nativo compatible con la
funcionalidad principal del protocolo.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class TrafficDirection(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"


class PIIMode(str, Enum):
    WARN = "warn"      # finding + warning, allowed=True
    REDACT = "redact"  # finding + redaction, allowed=True
    BLOCK = "block"    # finding + block, allowed=False


class PIISeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PIIType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    GOVERNMENT_ID = "government_id"
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    SECRET = "secret"
    CUSTOM = "custom"


@dataclass
class PIIDetector:
    pii_type: PIIType
    patterns: List[re.Pattern]
    severity: PIISeverity = PIISeverity.HIGH
    mode: PIIMode = PIIMode.REDACT
    # Nombre usado en el placeholder, p.ej. "EMAIL", "SECRET"
    placeholder_type: str = "PII"


@dataclass
class UsagePolicy:
    disallowed_use_cases: Set[str] = field(default_factory=set)
    disallowed_content_categories: Set[str] = field(default_factory=set)
    max_tokens: Optional[int] = None
    max_cost: Optional[float] = None
    max_rate_per_minute: Optional[int] = None
    required_contexts: Set[str] = field(default_factory=set)


@dataclass
class ModelControlPolicy:
    allowed_providers: Optional[Set[str]] = None
    allowed_models: Optional[Set[str]] = None
    denied_providers: Set[str] = field(default_factory=set)
    denied_models: Set[str] = field(default_factory=set)
    # use_case -> model requerido; si se envía un caso de uso y no coincide
    # se genera una advertencia o bloqueo según severidad.
    required_model_for_use_case: Dict[str, str] = field(default_factory=dict)


@dataclass
class LLMTrafficPolicy:
    pii_detectors: List[PIIDetector] = field(default_factory=list)
    usage_policy: UsagePolicy = field(default_factory=UsagePolicy)
    model_control: ModelControlPolicy = field(default_factory=ModelControlPolicy)
    # Si True, una PII en modo BLOCK detiene el tráfico (fail-closed).
    fail_closed_on_critical_pii: bool = True
    # Si True, cualquier política de uso crítica o model-control bloquea.
    fail_closed_on_policy_violation: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMTrafficPolicy":
        """Construye una política a partir de un dict plano (útil para la API)."""
        data = data or {}
        mc = data.get("model_control", {})
        up = data.get("usage_policy", {})
        return cls(
            pii_detectors=[
                PIIDetector(
                    pii_type=PIIType(d.get("pii_type", "custom")),
                    patterns=[re.compile(p, re.I if d.get("ignorecase") else 0) for p in d.get("patterns", [])],
                    severity=PIISeverity(d.get("severity", "medium")),
                    mode=PIIMode(d.get("mode", "warn")),
                    placeholder_type=d.get("placeholder_type", "PII"),
                )
                for d in data.get("pii_detectors", [])
            ],
            usage_policy=UsagePolicy(
                disallowed_use_cases=set(up.get("disallowed_use_cases", [])),
                disallowed_content_categories=set(up.get("disallowed_content_categories", [])),
                max_tokens=up.get("max_tokens"),
                max_cost=up.get("max_cost"),
                max_rate_per_minute=up.get("max_rate_per_minute"),
                required_contexts=set(up.get("required_contexts", [])),
            ),
            model_control=ModelControlPolicy(
                allowed_providers=set(mc["allowed_providers"]) if "allowed_providers" in mc else None,
                allowed_models=set(mc["allowed_models"]) if "allowed_models" in mc else None,
                denied_providers=set(mc.get("denied_providers", [])),
                denied_models=set(mc.get("denied_models", [])),
                required_model_for_use_case=mc.get("required_model_for_use_case", {}),
            ),
            fail_closed_on_critical_pii=data.get("fail_closed_on_critical_pii", True),
            fail_closed_on_policy_violation=data.get("fail_closed_on_policy_violation", True),
        )


@dataclass
class LLMTrafficEvent:
    provider: str = "unknown"
    model: str = "unknown"
    direction: TrafficDirection = TrafficDirection.REQUEST
    # Lista de mensajes OpenAI-style {"role": "...", "content": "..."}
    messages: List[Dict[str, Any]] = field(default_factory=list)
    # Caso de uso / contexto declarado por la aplicación/agente
    use_case: str = "general"
    # Metadatos opcionales: agent_id, app_id, user_id, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Información de uso: tokens, coste estimado, rpm.
    usage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMTrafficFinding:
    category: str
    severity: str
    path: str
    start: int
    end: int
    detector: str
    pii_type: Optional[str] = None
    replacement: Optional[str] = None
    # fingerprint del valor detectado (SHA-256 truncado); nunca el valor crudo.
    fp: Optional[str] = None
    # Modo de la política PII que generó el hallazgo: warn, redact, block.
    mode: str = "warn"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "path": self.path,
            "start": self.start,
            "end": self.end,
            "detector": self.detector,
            "pii_type": self.pii_type,
            "replacement": self.replacement,
            "fp": self.fp,
            "mode": self.mode,
        }


@dataclass
class LLMTrafficVerdict:
    allowed: bool = True
    action: str = "allow"  # allow | redact | block
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    redacted_messages: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[LLMTrafficFinding] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "issues": self.issues,
            "warnings": self.warnings,
            "redacted_messages": self.redacted_messages,
            "findings": [f.to_dict() for f in self.findings],
            "usage": self.usage,
            "details": self.details,
        }


def _luhn_valid(number: str) -> bool:
    """Validación básica de Luhn para reducir falsos positivos en tarjetas."""
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    reverse = digits[::-1]
    for i, d in enumerate(reverse):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _mask_value(value: str, prefix_len: int = 4) -> str:
    """Muestra solo los primeros caracteres y enmascara el resto."""
    if len(value) <= prefix_len:
        return "*" * len(value)
    return value[:prefix_len] + "*" * (len(value) - prefix_len)


class LLMTrafficGuardrails:
    """Motor nativo de guardrails para tráfico LLM."""

    _DEFAULT_PATTERNS: Dict[PIIType, List[str]] = {
        PIIType.EMAIL: [
            r"\b[A-Za-z0-9._%+'\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ],
        PIIType.PHONE: [
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            r"\b\+?[\d\s\-\(\)]{7,20}\b",
        ],
        PIIType.SSN: [
            r"\b\d{3}-\d{2}-\d{4}\b",
            r"\b\d{9}\b",
        ],
        PIIType.CREDIT_CARD: [
            r"\b(?:4\d{3}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b",  # Visa
            r"\b(?:5[1-5]\d{2}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b",  # MC
            r"\b(?:3[47]\d{2}[\s\-]?\d{6}[\s\-]?\d{5})\b",  # Amex
            r"\b(?:6(?:011|5\d{2})[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b",  # Discover
        ],
        PIIType.GOVERNMENT_ID: [
            r"\b[A-Z]{2}\d{6,10}\b",  # Pasaportes simplificados
            r"\b\d{2}\.\d{3}\.\d{3}\b",  # DNI-like
        ],
        PIIType.API_KEY: [
            r"\b(?:sk|pk|AKIA|ghp|glpat|GL-)[A-Za-z0-9_\-]{16,}\b",
        ],
        PIIType.TOKEN: [
            r"\b(?:bearer|token)\s+[A-Za-z0-9_\-\.]{16,}\b",
            r"\b[a-zA-Z0-9_-]*token[a-zA-Z0-9_-]*\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?",
        ],
        PIIType.PASSWORD: [
            r"\b(?:password|passwd|pwd|secret)\s*[:=]\s*['\"]?\S+['\"]?",
        ],
        PIIType.SECRET: [
            r"\b(?:secret|api_secret|client_secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\/+=]{8,}['\"]?",
        ],
    }

    def __init__(self, policy: Optional[LLMTrafficPolicy] = None) -> None:
        self.policy = policy or self.default_policy()
        self._placeholder_counters: Dict[str, int] = {}

    @classmethod
    def default_policy(cls) -> LLMTrafficPolicy:
        """Política por defecto: detecta PII común, redacta y bloquea secretos."""
        detectors: List[PIIDetector] = [
            PIIDetector(
                pii_type=PIIType.EMAIL,
                patterns=[re.compile(p) for p in cls._DEFAULT_PATTERNS[PIIType.EMAIL]],
                severity=PIISeverity.MEDIUM,
                mode=PIIMode.REDACT,
                placeholder_type="EMAIL",
            ),
            PIIDetector(
                pii_type=PIIType.PHONE,
                patterns=[re.compile(p) for p in cls._DEFAULT_PATTERNS[PIIType.PHONE]],
                severity=PIISeverity.MEDIUM,
                mode=PIIMode.REDACT,
                placeholder_type="PHONE",
            ),
            PIIDetector(
                pii_type=PIIType.SSN,
                patterns=[re.compile(p) for p in cls._DEFAULT_PATTERNS[PIIType.SSN]],
                severity=PIISeverity.HIGH,
                mode=PIIMode.BLOCK,
                placeholder_type="SSN",
            ),
            PIIDetector(
                pii_type=PIIType.CREDIT_CARD,
                patterns=[re.compile(p) for p in cls._DEFAULT_PATTERNS[PIIType.CREDIT_CARD]],
                severity=PIISeverity.CRITICAL,
                mode=PIIMode.BLOCK,
                placeholder_type="CREDIT_CARD",
            ),
            PIIDetector(
                pii_type=PIIType.GOVERNMENT_ID,
                patterns=[re.compile(p) for p in cls._DEFAULT_PATTERNS[PIIType.GOVERNMENT_ID]],
                severity=PIISeverity.HIGH,
                mode=PIIMode.BLOCK,
                placeholder_type="GOVERNMENT_ID",
            ),
            PIIDetector(
                pii_type=PIIType.API_KEY,
                patterns=[re.compile(p, re.I) for p in cls._DEFAULT_PATTERNS[PIIType.API_KEY]],
                severity=PIISeverity.CRITICAL,
                mode=PIIMode.BLOCK,
                placeholder_type="SECRET",
            ),
            PIIDetector(
                pii_type=PIIType.TOKEN,
                patterns=[re.compile(p, re.I) for p in cls._DEFAULT_PATTERNS[PIIType.TOKEN]],
                severity=PIISeverity.CRITICAL,
                mode=PIIMode.BLOCK,
                placeholder_type="SECRET",
            ),
            PIIDetector(
                pii_type=PIIType.PASSWORD,
                patterns=[re.compile(p, re.I) for p in cls._DEFAULT_PATTERNS[PIIType.PASSWORD]],
                severity=PIISeverity.CRITICAL,
                mode=PIIMode.BLOCK,
                placeholder_type="SECRET",
            ),
            PIIDetector(
                pii_type=PIIType.SECRET,
                patterns=[re.compile(p, re.I) for p in cls._DEFAULT_PATTERNS[PIIType.SECRET]],
                severity=PIISeverity.CRITICAL,
                mode=PIIMode.BLOCK,
                placeholder_type="SECRET",
            ),
        ]
        return LLMTrafficPolicy(
            pii_detectors=detectors,
            usage_policy=UsagePolicy(
                disallowed_use_cases={"bypass_policy", "generate_malware", "impersonate"},
                disallowed_content_categories={"hate", "violence", "self_harm", "illegal"},
                max_tokens=1_000_000,
                max_cost=1000.0,
                max_rate_per_minute=10_000,
            ),
            model_control=ModelControlPolicy(
                denied_providers=set(),
                denied_models=set(),
            ),
        )

    def _next_placeholder(self, ptype: str) -> str:
        self._placeholder_counters[ptype] = self._placeholder_counters.get(ptype, 0) + 1
        return f"${{OGR_{ptype}_{self._placeholder_counters[ptype]}}}"

    def _detect_pii_in_text(
        self,
        text: str,
        base_path: str,
        redact: bool,
    ) -> Tuple[List[LLMTrafficFinding], str]:
        """Detecta PII en un texto y opcionalmente redacta in-place.

        Retorna (findings, redacted_text). Nunca expone el valor completo
        en los hallazgos: solo offset, tipo y fingerprint.
        """
        findings: List[LLMTrafficFinding] = []
        replacements: List[Tuple[int, int, str, str, str]] = []  # start, end, placeholder, type, fp

        for detector in self.policy.pii_detectors:
            for pattern in detector.patterns:
                for match in pattern.finditer(text):
                    value = match.group(0)
                    # Para tarjetas, validar con Luhn para reducir falsos positivos.
                    if detector.pii_type == PIIType.CREDIT_CARD and not _luhn_valid(value):
                        continue
                    placeholder = self._next_placeholder(detector.placeholder_type)
                    fp = _fingerprint(value)
                    category = f"privacy.pii.{detector.pii_type.value}"
                    finding = LLMTrafficFinding(
                        category=category,
                        severity=detector.severity.value,
                        path=base_path,
                        start=match.start(),
                        end=match.end(),
                        detector="pii",
                        pii_type=detector.pii_type.value,
                        replacement=placeholder if redact else None,
                        fp=fp,
                        mode=detector.mode.value,
                    )
                    findings.append(finding)
                    replacements.append(
                        (match.start(), match.end(), placeholder, detector.pii_type.value, fp)
                    )

        if not redact or not replacements:
            return findings, text

        # Resolver superposiciones: gana la de mayor longitud; empate -> primera en aparecer.
        replacements.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        merged: List[Tuple[int, int, str, str, str]] = []
        for start, end, placeholder, pii_type, fp in replacements:
            if merged and start < merged[-1][1]:
                prev_start, prev_end, prev_placeholder, prev_type, prev_fp = merged[-1]
                length = end - start
                prev_length = prev_end - prev_start
                if length > prev_length:
                    merged[-1] = (start, end, placeholder, pii_type, fp)
                # Si es igual o menor, mantenemos la anterior.
                continue
            merged.append((start, end, placeholder, pii_type, fp))

        # Aplicar reemplazos de atrás hacia adelante para preservar offsets.
        redacted = text
        for start, end, placeholder, _pii_type, _fp in reversed(merged):
            redacted = redacted[:start] + placeholder + redacted[end:]

        return findings, redacted

    def _inspect_messages(
        self,
        messages: List[Dict[str, Any]],
        redact: bool,
    ) -> Tuple[List[Dict[str, Any]], List[LLMTrafficFinding]]:
        redacted_messages: List[Dict[str, Any]] = []
        findings: List[LLMTrafficFinding] = []

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                path = f"messages.{i}.content"
                pii_findings, redacted = self._detect_pii_in_text(content, path, redact=redact)
                findings.extend(pii_findings)
                new_msg = {**msg, "content": redacted}
            else:
                new_msg = dict(msg)

            # Inspeccionar tool_calls si existen (respuestas del asistente).
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                new_tool_calls = []
                for tci, tc in enumerate(tool_calls):
                    if not isinstance(tc, dict):
                        new_tool_calls.append(tc)
                        continue
                    func = tc.get("function", {})
                    args = func.get("arguments")
                    if isinstance(args, str):
                        path = f"messages.{i}.tool_calls.{tci}.function.arguments"
                        pii_findings, redacted_args = self._detect_pii_in_text(
                            args, path, redact=redact
                        )
                        findings.extend(pii_findings)
                        new_tc = {
                            **tc,
                            "function": {**func, "arguments": redacted_args},
                        }
                    else:
                        new_tc = dict(tc)
                    new_tool_calls.append(new_tc)
                new_msg["tool_calls"] = new_tool_calls

            redacted_messages.append(new_msg)

        return redacted_messages, findings

    def _check_model_control(self, event: LLMTrafficEvent) -> List[Tuple[str, str, bool]]:
        """Valida políticas de proveedor/modelo. Retorna (mensaje, severidad, bloquea)."""
        mc = self.policy.model_control
        results: List[Tuple[str, str, bool]] = []
        provider = event.provider.lower()
        model = event.model.lower()

        if mc.denied_providers and provider in {p.lower() for p in mc.denied_providers}:
            results.append(
                (f"Model control: provider '{event.provider}' is denied", "critical", True)
            )
        if mc.denied_models and model in {m.lower() for m in mc.denied_models}:
            results.append(
                (f"Model control: model '{event.model}' is denied", "critical", True)
            )
        if mc.allowed_providers is not None and provider not in {p.lower() for p in mc.allowed_providers}:
            results.append(
                (f"Model control: provider '{event.provider}' not in allowlist", "critical", True)
            )
        if mc.allowed_models is not None and model not in {m.lower() for m in mc.allowed_models}:
            results.append(
                (f"Model control: model '{event.model}' not in allowlist", "critical", True)
            )

        required = mc.required_model_for_use_case.get(event.use_case)
        if required and model != required.lower():
            results.append(
                (f"Model control: use_case '{event.use_case}' requires model '{required}'", "high", True)
            )

        return results

    def _check_usage_policy(self, event: LLMTrafficEvent) -> List[Tuple[str, str, bool]]:
        """Valida políticas de uso. Retorna (mensaje, severidad, bloquea)."""
        up = self.policy.usage_policy
        results: List[Tuple[str, str, bool]] = []

        if event.use_case in up.disallowed_use_cases:
            results.append(
                (f"Usage policy: use_case '{event.use_case}' is disallowed", "critical", True)
            )

        # Revisar categorías de contenido declaradas o inferidas.
        content_categories = set(event.metadata.get("content_categories", []))
        for cat in content_categories:
            if cat in up.disallowed_content_categories:
                results.append(
                    (f"Usage policy: content category '{cat}' is disallowed", "critical", True)
                )

        tokens = event.usage.get("total_tokens")
        if up.max_tokens is not None and isinstance(tokens, (int, float)) and tokens > up.max_tokens:
            results.append(
                (f"Usage policy: total_tokens {tokens} exceeds max {up.max_tokens}", "high", True)
            )

        cost = event.usage.get("estimated_cost")
        if up.max_cost is not None and isinstance(cost, (int, float)) and cost > up.max_cost:
            results.append(
                (f"Usage policy: estimated_cost {cost} exceeds max {up.max_cost}", "high", True)
            )

        rpm = event.usage.get("requests_per_minute")
        if up.max_rate_per_minute is not None and isinstance(rpm, (int, float)) and rpm > up.max_rate_per_minute:
            results.append(
                (f"Usage policy: rpm {rpm} exceeds max {up.max_rate_per_minute}", "high", True)
            )

        # Contextos requeridos.
        missing = up.required_contexts - set(event.metadata.keys())
        if missing:
            results.append(
                (f"Usage policy: missing required metadata {sorted(missing)}", "high", True)
            )

        return results

    def evaluate(self, event: LLMTrafficEvent) -> LLMTrafficVerdict:
        """Evalúa un evento de tráfico LLM contra todas las políticas configuradas."""
        verdict = LLMTrafficVerdict()
        verdict.usage = dict(event.usage)

        redact_pii = True  # Por defecto redactamos; el caller puede cambiar a warn.

        # 1. Model / provider control.
        for msg, severity, blocks in self._check_model_control(event):
            if blocks:
                verdict.issues.append(msg)
                if self.policy.fail_closed_on_policy_violation:
                    verdict.allowed = False
                    verdict.action = "block"
            else:
                verdict.warnings.append(msg)

        # 2. Usage policy.
        for msg, severity, blocks in self._check_usage_policy(event):
            if blocks:
                verdict.issues.append(msg)
                if self.policy.fail_closed_on_policy_violation:
                    verdict.allowed = False
                    verdict.action = "block"
            else:
                verdict.warnings.append(msg)

        # 3. PII inspection.
        redacted_messages, pii_findings = self._inspect_messages(event.messages, redact=redact_pii)
        verdict.redacted_messages = redacted_messages
        verdict.findings.extend(pii_findings)

        blocked_by_mode = [f for f in pii_findings if f.mode == PIIMode.BLOCK.value]
        critical_findings = [
            f for f in pii_findings
            if f.severity in (PIISeverity.CRITICAL.value, PIISeverity.HIGH.value)
        ]
        if blocked_by_mode:
            for f in blocked_by_mode:
                verdict.issues.append(
                    f"PII {f.pii_type} detected at {f.path}; detector mode is block"
                )
            verdict.allowed = False
            verdict.action = "block"
        elif critical_findings and self.policy.fail_closed_on_critical_pii:
            for f in critical_findings:
                verdict.issues.append(
                    f"PII {f.pii_type} detected at {f.path}; severity={f.severity} requires block"
                )
            verdict.allowed = False
            verdict.action = "block"
        elif pii_findings:
            # Hay PII pero no bloqueamos -> redact o warn según configuración.
            if any(f.replacement for f in pii_findings):
                if verdict.allowed:
                    verdict.action = "redact"
                for f in pii_findings:
                    if f.replacement:
                        verdict.warnings.append(
                            f"PII {f.pii_type} redacted at {f.path} with {f.replacement}"
                        )
            else:
                for f in pii_findings:
                    verdict.warnings.append(
                        f"PII {f.pii_type} detected at {f.path} (warn-only)"
                    )

        # 4. Detalles auditables sin valores crudos.
        pii_summary: Dict[str, Any] = {}
        for f in pii_findings:
            pii_summary.setdefault(f.pii_type, {"count": 0, "severity": f.severity})
            pii_summary[f.pii_type]["count"] += 1

        verdict.details = {
            "provider": event.provider,
            "model": event.model,
            "direction": event.direction.value,
            "use_case": event.use_case,
            "pii_summary": pii_summary,
            "pii_findings_count": len(pii_findings),
            "redacted": bool(pii_findings and any(f.replacement for f in pii_findings)),
            "source": "OpenGuardrails-style native guardrails",
        }

        return verdict


def evaluate_llm_traffic(
    provider: str,
    model: str,
    messages: List[Dict[str, Any]],
    direction: str = "request",
    use_case: str = "general",
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, Any]] = None,
    policy: Optional[LLMTrafficPolicy] = None,
) -> Dict[str, Any]:
    """Helper de alto nivel que devuelve un dict JSON-serializable."""
    guardrails = LLMTrafficGuardrails(policy=policy)
    event = LLMTrafficEvent(
        provider=provider,
        model=model,
        direction=TrafficDirection(direction),
        messages=messages,
        use_case=use_case,
        metadata=metadata or {},
        usage=usage or {},
    )
    return guardrails.evaluate(event).to_dict()
