"""UC-324 — Motor de políticas anti prompt-injection (G) inspirado en agent-policy-engine.

El repositorio `kahalewai/agent-policy-engine` no es un paquete Python
instalable (no tiene `setup.py` ni `pyproject.toml`). UC-324 implementa aquí
un motor de políticas para agentes que consumen contenido web, documentos,
tickets, correos o salidas de herramientas, detectando intentos de prompt
injection, instrucciones ocultas, role-play y manipulación de contexto.

Principios:
- Cada contenido conserva su proveniencia (fuente, autor, timestamp, hash).
- Detección de múltiples familias de ataque con evidencia.
- Fail-closed para acciones sensibles (`execute`, `transact`, `delete`).
- Redacción/escaneo para contenido no confiable.
- Las decisiones son reproducibles y auditables.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class SourceType(str, Enum):
    WEB = "web"
    DOCUMENT = "document"
    TICKET = "ticket"
    EMAIL = "email"
    TOOL_OUTPUT = "tool_output"
    CHAT = "chat"
    UNKNOWN = "unknown"


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class Sensitivity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ContentItem:
    """Pieza de contenido con proveniencia."""

    content: str
    source_type: SourceType = SourceType.UNKNOWN
    source_id: Optional[str] = None
    author: Optional[str] = None
    timestamp: Optional[str] = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source_type is None:
            self.source_type = SourceType.UNKNOWN
        if isinstance(self.source_type, str):
            self.source_type = SourceType(self.source_type)
        if self.trust_level is None:
            self.trust_level = TrustLevel.UNKNOWN
        if isinstance(self.trust_level, str):
            self.trust_level = TrustLevel(self.trust_level)

    def fingerprint(self) -> str:
        """Hash determinista del contenido para auditoría."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        source_type_value = self.source_type.value if isinstance(self.source_type, SourceType) else self.source_type
        trust_level_value = self.trust_level.value if isinstance(self.trust_level, TrustLevel) else self.trust_level
        return {
            "content_preview": self.content[:200] + ("..." if len(self.content) > 200 else ""),
            "source_type": source_type_value,
            "source_id": self.source_id,
            "author": self.author,
            "timestamp": self.timestamp,
            "trust_level": trust_level_value,
            "fingerprint": self.fingerprint(),
            "metadata": self.metadata,
        }


@dataclass
class DetectionMatch:
    detector: str
    pattern: str
    severity: float  # 0.0-1.0
    matched_text: str
    position: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector": self.detector,
            "pattern": self.pattern,
            "severity": self.severity,
            "matched_text": self.matched_text,
            "position": self.position,
        }


@dataclass
class PolicyVerdict:
    allowed: bool
    score: float
    sensitivity: Sensitivity
    block_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    redacted_content: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "score": self.score,
            "sensitivity": self.sensitivity.value,
            "block_reasons": self.block_reasons,
            "warnings": self.warnings,
            "evidence": self.evidence,
            "provenance": self.provenance,
            "redacted_content": self.redacted_content,
        }


class Detector:
    """Detector simple basado en regex con severidad."""

    def __init__(self, name: str, patterns: List[Tuple[str, float]]) -> None:
        self.name = name
        self.patterns = [(re.compile(p, re.IGNORECASE | re.MULTILINE), s) for p, s in patterns]

    def detect(self, text: str) -> List[DetectionMatch]:
        matches: List[DetectionMatch] = []
        for pattern, severity in self.patterns:
            for m in pattern.finditer(text):
                matches.append(
                    DetectionMatch(
                        detector=self.name,
                        pattern=pattern.pattern,
                        severity=severity,
                        matched_text=m.group(0)[:120],
                        position=m.start(),
                    )
                )
        return matches


INSTRUCTION_OVERRIDE_PATTERNS: List[Tuple[str, float]] = [
    (r"ignore\s+(?:your\s+)?(?:previous|above|prior|earlier)\s+(?:instructions?|commands?|rules?|prompts?)", 1.0),
    (r"ignore\s+(?:everything|all)\s+(?:before|above|prior)", 1.0),
    (r"forget\s+(?:everything|all|your)\s+(?:instructions?|training|rules?|prompts?)", 1.0),
    (r"(?:new|updated?|override)\s+(?:instructions?|commands?|rules?|system\s+prompts?)", 1.0),
    (r"(?:you\s+must|from\s+now\s+on|effective\s+immediately)\s+.*(?:ignore|disregard|bypass)", 1.0),
    (r"(?:stop|do\s+not)\s+(?:following|obeying)\s+(?:instructions?|rules?|the\s+rules?)", 1.0),
    (r"(?:system|developer|administrator|user)\s+(?:instruction|override|mode)", 1.0),
    (r"sudo\s+(?:mode|access|override)", 1.0),
    (r"DAN\s+mode|do\s+anything\s+now", 1.0),
    (r"(?:jailbreak|prompt\s+injection|override\s+prompt)", 1.0),
]

ROLE_PLAY_PATTERNS: List[Tuple[str, float]] = [
    (r"(?:act\s+as|pretend\s+to\s+be|roleplay\s+as|imagine\s+you\s+are|you\s+are\s+now)\s+(?:an?\s+)?(?:unrestricted|developer|admin|hacker|root|system|AI|assistant|bot)", 1.0),
    (r"(?:you\s+are\s+no\s+longer|from\s+now\s+on\s+you\s+are)\s+(?:bound\s+by|restricted\s+by|subject\s+to)", 1.0),
    (r"(?:respond|behave)\s+as\s+if\s+you\s+(?:have|are|were)", 0.8),
    (r"(?:bypass|disable|turn\s+off)\s+(?:your\s+)?(?:safet(?:y|ies)|filters|restrictions|guidelines)", 1.0),
]

SEPARATOR_TOKEN_PATTERNS: List[Tuple[str, float]] = [
    (r"<\|im_(?:start|end)\|>", 1.0),
    (r"\[/?system\s*\]", 1.0),
    (r"\[/?user\s*\]", 1.0),
    (r"\[/?assistant\s*\]", 1.0),
    (r"<<\s*SYS\s*>>|<<\s*/SYS\s*>>", 1.0),
    (r"###\s*(?:system|user|assistant|instructions|ignore)", 1.0),
    (r"---\s*(?:system|user|assistant|instructions|ignore)", 1.0),
    (r"<<<\s*(?:system|user|assistant|instructions|ignore)", 1.0),
]

ENCODING_OBFUSCATION_PATTERNS: List[Tuple[str, float]] = [
    (r"[\u200B\u200C\u200D\uFEFF\u2060\u180E]{3,}", 0.8),  # zero-width characters
    (r"(?:[A-Za-z0-9+/]{40,}={0,2}\s*){2,}", 0.5),  # base64-like blobs
]

INDIRECT_INJECTION_PATTERNS: List[Tuple[str, float]] = [
    (r"(?:fetch|download|read|load|open)\s+(?:this|the|following|attached|link|url|document|page|email|ticket)", 0.6),
    (r"https?://\S+\s+(?:contains?|says?|tells?|instructs?|orders?)", 0.7),
    (r"(?:see|check|refer\s+to|as\s+per)\s+(?:the\s+)?(?:attached|linked|document|page|email|ticket|web)", 0.6),
    (r"(?:the\s+)?(?:user|customer|person|sender)\s+(?:actually|really|instead|now)\s+(?:wants|needs|said|asked)", 0.7),
]

MARKDOWN_CODEBLOCK_PATTERNS: List[Tuple[str, float]] = [
    (r"```[\s\S]*?```", 0.3),  # heavy markdown code blocks; low severity by itself
    (r"`[^`]{0,50}(?:sudo|rm\s+-rf|drop\s+table|exec\(|ignore|override)[^`]*`", 0.8),
]


def build_default_detectors() -> List[Detector]:
    return [
        Detector("instruction_override", INSTRUCTION_OVERRIDE_PATTERNS),
        Detector("role_play", ROLE_PLAY_PATTERNS),
        Detector("separator_tokens", SEPARATOR_TOKEN_PATTERNS),
        Detector("encoding_obfuscation", ENCODING_OBFUSCATION_PATTERNS),
        Detector("indirect_injection", INDIRECT_INJECTION_PATTERNS),
        Detector("markdown_codeblock", MARKDOWN_CODEBLOCK_PATTERNS),
    ]


@dataclass
class PolicyRule:
    """Regla de decisión por trust_level y sensibilidad."""

    name: str
    description: str
    applies_to_sensitivities: Set[Sensitivity] = field(
        default_factory=lambda: set(Sensitivity)
    )
    allowed_trust_levels: Set[TrustLevel] = field(
        default_factory=lambda: {TrustLevel.TRUSTED, TrustLevel.UNKNOWN}
    )
    max_score_for_allow: float = 0.0
    action_on_violation: str = "block"  # "block" or "warn"


DEFAULT_POLICY_RULES: List[PolicyRule] = [
    PolicyRule(
        name="fail_closed_for_sensitive_untrusted",
        description="Untrusted content with any injection marker blocks sensitive actions",
        applies_to_sensitivities={Sensitivity.HIGH, Sensitivity.CRITICAL},
        allowed_trust_levels={TrustLevel.TRUSTED},
        max_score_for_allow=0.0,
        action_on_violation="block",
    ),
    PolicyRule(
        name="warn_for_unknown_trust",
        description="Unknown-trust content with high-severity markers triggers warning",
        applies_to_sensitivities=set(Sensitivity),
        allowed_trust_levels={TrustLevel.TRUSTED, TrustLevel.UNKNOWN},
        max_score_for_allow=0.5,
        action_on_violation="warn",
    ),
]


TRUST_BY_SOURCE_TYPE: Dict[SourceType, TrustLevel] = {
    SourceType.EMAIL: TrustLevel.UNKNOWN,
    SourceType.WEB: TrustLevel.UNTRUSTED,
    SourceType.DOCUMENT: TrustLevel.UNKNOWN,
    SourceType.TICKET: TrustLevel.UNKNOWN,
    SourceType.TOOL_OUTPUT: TrustLevel.UNKNOWN,
    SourceType.CHAT: TrustLevel.UNKNOWN,
    SourceType.UNKNOWN: TrustLevel.UNKNOWN,
}


class PromptInjectionPolicyEngine:
    """Motor de políticas anti prompt-injection."""

    def __init__(
        self,
        detectors: Optional[List[Detector]] = None,
        rules: Optional[List[PolicyRule]] = None,
        trust_by_source_type: Optional[Dict[SourceType, TrustLevel]] = None,
        sensitive_action_classes: Optional[set] = None,
    ) -> None:
        self.detectors = detectors if detectors is not None else build_default_detectors()
        self.rules = rules if rules is not None else list(DEFAULT_POLICY_RULES)
        self.trust_by_source_type = trust_by_source_type if trust_by_source_type is not None else dict(TRUST_BY_SOURCE_TYPE)
        self.sensitive_action_classes = sensitive_action_classes or {"execute", "transact", "delete"}

    def _decode_b64_candidates(self, text: str) -> List[str]:
        """Intenta decodificar bloques base64 para inspeccionar contenido oculto."""
        candidates: List[str] = []
        for match in re.finditer(r"[A-Za-z0-9+/]{40,}={0,2}", text):
            token = match.group(0)
            try:
                decoded = base64.b64decode(token).decode("utf-8", errors="ignore")
                if len(decoded) >= 10 and re.search(r"[a-zA-Z]{5,}", decoded):
                    candidates.append(decoded)
            except Exception:
                continue
        return candidates

    def scan(self, item: ContentItem) -> Tuple[List[DetectionMatch], List[str]]:
        """Escanea un item y devuelve hallazgos + contenido decodificado."""
        text = item.content
        matches: List[DetectionMatch] = []
        for detector in self.detectors:
            matches.extend(detector.detect(text))

        decoded = self._decode_b64_candidates(text)
        for decoded_text in decoded:
            for detector in self.detectors:
                for m in detector.detect(decoded_text):
                    # Ajustar posición para indicar que vino de base64
                    m.position = -1
                    matches.append(m)
        return matches, decoded

    def evaluate(
        self,
        items: List[ContentItem],
        action_sensitivity: Sensitivity = Sensitivity.MEDIUM,
        action_class: Optional[str] = None,
    ) -> PolicyVerdict:
        """Evalúa contenido y devuelve veredicto."""
        all_matches: List[DetectionMatch] = []
        provenance: List[Dict[str, Any]] = []
        redacted: List[str] = []
        decoded_hits: List[str] = []

        max_score = 0.0
        for item in items:
            if item.trust_level == TrustLevel.UNKNOWN:
                item.trust_level = self.trust_by_source_type.get(item.source_type, TrustLevel.UNKNOWN)
            matches, decoded = self.scan(item)
            all_matches.extend(matches)
            provenance.append(item.to_dict())
            if decoded:
                decoded_hits.extend(decoded)
            item_score = max((m.severity for m in matches), default=0.0)
            if item_score > max_score:
                max_score = item_score
            if item.trust_level == TrustLevel.UNTRUSTED and matches:
                redacted.append(
                    f"[REDACTED: {item.source_type.value} {item.source_id or 'unknown'} due to policy matches]"
                )

        verdict = PolicyVerdict(
            allowed=True,
            score=max_score,
            sensitivity=action_sensitivity,
            evidence=[m.to_dict() for m in all_matches],
            provenance=provenance,
            redacted_content=redacted,
        )

        # Aplicar reglas de política según sensibilidad y score
        for rule in self.rules:
            if action_sensitivity not in rule.applies_to_sensitivities:
                continue
            if max_score > rule.max_score_for_allow:
                if rule.action_on_violation == "block":
                    verdict.allowed = False
                    verdict.block_reasons.append(
                        f"Policy rule '{rule.name}': content score {max_score:.2f} exceeds "
                        f"threshold {rule.max_score_for_allow:.2f}"
                    )
                else:
                    verdict.warnings.append(
                        f"Policy rule '{rule.name}': suspicious content detected (score {max_score:.2f})"
                    )

        # Fail-closed para acciones sensibles con contenido no confiable
        if action_class in self.sensitive_action_classes:
            has_untrusted = any(
                item.trust_level == TrustLevel.UNTRUSTED for item in items
            )
            if has_untrusted and all_matches:
                verdict.allowed = False
                verdict.block_reasons.append(
                    f"Fail-closed: sensitive action '{action_class}' cannot use untrusted content with injection markers"
                )

        if decoded_hits:
            verdict.warnings.append(
                f"Base64/encoded content candidates detected and inspected ({len(decoded_hits)})"
            )

        return verdict


def quick_prompt_injection_check(text: str) -> Dict[str, Any]:
    """Escaneo rápido de texto plano para el adapter pre-action."""
    engine = PromptInjectionPolicyEngine()
    item = ContentItem(
        content=text,
        source_type=SourceType.UNKNOWN,
        trust_level=TrustLevel.UNKNOWN,
    )
    verdict = engine.evaluate([item])
    return verdict.to_dict()


def scan_content_items(
    items: List[Dict[str, Any]],
    action_sensitivity: str = "medium",
    action_class: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper de alto nivel para escanear items serializados."""
    engine = PromptInjectionPolicyEngine()
    content_items = [
        ContentItem(
            content=item.get("content", ""),
            source_type=SourceType(item.get("source_type", "unknown")),
            source_id=item.get("source_id"),
            author=item.get("author"),
            timestamp=item.get("timestamp"),
            trust_level=TrustLevel(item.get("trust_level", "unknown")),
            metadata=item.get("metadata", {}),
        )
        for item in items
    ]
    verdict = engine.evaluate(
        content_items,
        action_sensitivity=Sensitivity(action_sensitivity),
        action_class=action_class,
    )
    return verdict.to_dict()
