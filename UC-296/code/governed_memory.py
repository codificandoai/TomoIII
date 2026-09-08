"""UC-296 — GovernedMemory: gobernanza de promoción local→global de memoria.

Reglas de selección:
- HIPOTHESIS: candidato a memoria compartida, aún no validado.
- PROMOTED: validado automáticamente y/o por aprobación humana; visible global.
- REJECTED: no cumple criterios de calidad, procedencia o seguridad.
- INVALIDATED: previamente promovido pero posteriormente refutado o superado.

Controles:
- Procedencia obligatoria (source_id, source_type, evidence_hash).
- Ámbitos de visibilidad (visibility_scope).
- Supersesión temporal por version/timestamp.
- No promoción autónoma: requiere validación externa.
- Anti-replay de memory_id.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class MemoryVerdict(str, Enum):
    """Resultado de la revisión de un candidato a memoria compartida."""
    HIPOTHESIS = "hypothesis"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"


class MemoryScope(str, Enum):
    """Ámbitos de visibilidad de la memoria compartida."""
    LOCAL = "local"
    AGENT = "agent"
    DOMAIN = "domain"
    FLEET = "fleet"
    PUBLIC = "public"


@dataclass
class MemoryProvenance:
    """Procedencia requerida para que una memoria sea promovible."""
    source_id: str
    source_type: str
    evidence_hash: str
    agent_id: str
    chain_of_custody: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "evidence_hash": self.evidence_hash,
            "agent_id": self.agent_id,
            "chain_of_custody": self.chain_of_custody,
        }


@dataclass
class GovernedMemoryItem:
    """Item de memoria bajo gobernanza."""
    memory_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    content: str = ""
    content_type: str = "fact"
    local_timestamp: float = field(default_factory=time.time)
    version: int = 1
    scope: MemoryScope = MemoryScope.LOCAL
    verdict: MemoryVerdict = MemoryVerdict.HIPOTHESIS
    provenance: Optional[MemoryProvenance] = None
    confidence: float = 0.0
    ttl_seconds: Optional[float] = None
    superseded_by: Optional[str] = None
    invalidation_reason: str = ""
    promotion_approved_by: Optional[str] = None
    promotion_trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.metadata.get("content_hash"):
            canonical = " ".join(self.content.lower().split())
            self.metadata["content_hash"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def is_expired(self, now: Optional[float] = None) -> bool:
        if self.ttl_seconds is None:
            return False
        now = now or time.time()
        return (self.local_timestamp + self.ttl_seconds) < now

    def promote(self, approved_by: str, trace_id: str) -> None:
        """Promueve la memoria a compartida tras aprobación externa."""
        if self.verdict != MemoryVerdict.HIPOTHESIS:
            raise ValueError(f"cannot promote memory in state {self.verdict}")
        if not self.provenance:
            raise ValueError("memory without provenance cannot be promoted")
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be in [0, 1]")
        self.verdict = MemoryVerdict.PROMOTED
        self.scope = MemoryScope.DOMAIN
        self.promotion_approved_by = approved_by
        self.promotion_trace_id = trace_id

    def reject(self, reason: str) -> None:
        self.verdict = MemoryVerdict.REJECTED
        self.metadata["rejection_reason"] = reason

    def invalidate(self, reason: str, superseded_by: Optional[str] = None) -> None:
        if self.verdict == MemoryVerdict.HIPOTHESIS:
            raise ValueError("cannot invalidate a hypothesis; reject it instead")
        self.verdict = MemoryVerdict.INVALIDATED
        self.invalidation_reason = reason
        self.superseded_by = superseded_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "agent_id": self.agent_id,
            "content": self.content[:250],
            "content_type": self.content_type,
            "local_timestamp": self.local_timestamp,
            "version": self.version,
            "scope": self.scope.value,
            "verdict": self.verdict.value,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "confidence": round(self.confidence, 6),
            "ttl_seconds": self.ttl_seconds,
            "superseded_by": self.superseded_by,
            "invalidation_reason": self.invalidation_reason,
            "promotion_approved_by": self.promotion_approved_by,
            "promotion_trace_id": self.promotion_trace_id,
            "metadata": self.metadata,
        }


class GovernedMemoryStore:
    """Almacén de memoria compartida gobernada."""

    def __init__(self):
        self._items: Dict[str, GovernedMemoryItem] = {}
        self._consumed_ids: Set[str] = set()

    def submit(
        self,
        agent_id: str,
        content: str,
        content_type: str,
        provenance: MemoryProvenance,
        confidence: float,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GovernedMemoryItem:
        """Un agente somete un recuerdo local como hipótesis."""
        item = GovernedMemoryItem(
            agent_id=agent_id,
            content=content,
            content_type=content_type,
            provenance=provenance,
            confidence=confidence,
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )
        # Regla: un agente no puede promover su propia memoria sin aprobación.
        item.metadata["self_promotion_blocked"] = True
        self._items[item.memory_id] = item
        return item

    def validate_for_promotion(
        self,
        memory_id: str,
        approved_by: str,
        trace_id: str,
        automatic_checks: Optional[Dict[str, Any]] = None,
    ) -> GovernedMemoryItem:
        """Validación externa para promover una hipótesis a memoria compartida."""
        if memory_id not in self._items:
            raise ValueError("memory not found")
        item = self._items[memory_id]

        if item.verdict != MemoryVerdict.HIPOTHESIS:
            raise ValueError(f"memory is not a hypothesis: {item.verdict}")

        if not item.provenance or not item.provenance.evidence_hash:
            item.reject("missing provenance")
            return item

        if item.is_expired():
            item.reject("expired before promotion")
            return item

        if item.confidence < 0.5:
            item.reject("confidence below threshold")
            return item

        # Anti-replay del id de memoria
        if memory_id in self._consumed_ids:
            item.reject("memory_id already consumed")
            return item

        # Validación automática adicional (hallucination, contradiction, etc.)
        checks = automatic_checks or {}
        if checks.get("hallucination_detected") or checks.get("contradiction_detected"):
            item.reject("failed automatic quality checks")
            return item

        item.promote(approved_by, trace_id)
        self._consumed_ids.add(memory_id)
        return item

    def invalidate(self, memory_id: str, reason: str, superseded_by: Optional[str] = None) -> GovernedMemoryItem:
        item = self._items[memory_id]
        item.invalidate(reason, superseded_by)
        return item

    def get_visible(self, agent_id: str, scope: MemoryScope) -> List[GovernedMemoryItem]:
        """Devuelve memoria visible para un agente en un ámbito dado."""
        scope_order = [
            MemoryScope.LOCAL,
            MemoryScope.AGENT,
            MemoryScope.DOMAIN,
            MemoryScope.FLEET,
            MemoryScope.PUBLIC,
        ]
        max_level = scope_order.index(scope)
        visible = []
        for item in self._items.values():
            if item.is_expired():
                continue
            if item.verdict not in (MemoryVerdict.PROMOTED, MemoryVerdict.HIPOTHESIS):
                continue
            item_level = scope_order.index(item.scope)
            if item_level > max_level:
                continue
            visible.append(item)
        return sorted(visible, key=lambda x: x.local_timestamp, reverse=True)

    def supersede(self, memory_id: str, new_item: GovernedMemoryItem) -> None:
        """Supersede un recuerdo promovido por una versión más reciente."""
        old = self._items.get(memory_id)
        if not old:
            raise ValueError("old memory not found")
        if old.verdict != MemoryVerdict.PROMOTED:
            raise ValueError("only promoted memories can be superseded")
        old.invalidate("superseded by newer version", new_item.memory_id)
        new_item.version = old.version + 1
        new_item.scope = old.scope
        self._items[new_item.memory_id] = new_item

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": {mid: item.to_dict() for mid, item in self._items.items()},
            "consumed_ids": sorted(self._consumed_ids),
        }
