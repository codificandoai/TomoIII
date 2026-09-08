"""UC-307 — AutoEvolutionTracer: trazabilidad de cambios evolutivos.

Registra eventos de evolución (mutación, ajuste de parámetros, cruza,
eliminación) y permite vincularlos a métricas de seguridad posteriores.
Cada evento incluye:
- hash del ADN antes y después
- agente responsable y acción
- motivo y evidencia
- métricas de seguridad observadas
- posible degradación atribuible
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvolutionAction(str, Enum):
    MUTATE = "mutate"
    ADJUST = "adjust"
    CROSSOVER = "crossover"
    ELIMINATE = "eliminate"
    RETRAIN = "retrain"
    PERSIST = "persist"
    MODIFY_PARAMS = "modify_params"


@dataclass
class EvolutionEvent:
    """Evento de evolución trazable."""
    event_id: str
    agent_id: str
    action: EvolutionAction
    parent_dna_hash: str
    child_dna_hash: str
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    security_metrics_before: Dict[str, Any] = field(default_factory=dict)
    security_metrics_after: Dict[str, Any] = field(default_factory=dict)
    attributed_degradation: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    approved_by: Optional[str] = None

    def compute_child_hash(self, dna_dict: Dict[str, Any]) -> str:
        canonical = json.dumps(dna_dict, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "action": self.action.value,
            "parent_dna_hash": self.parent_dna_hash,
            "child_dna_hash": self.child_dna_hash,
            "reason": self.reason,
            "evidence": self.evidence,
            "security_metrics_before": self.security_metrics_before,
            "security_metrics_after": self.security_metrics_after,
            "attributed_degradation": self.attributed_degradation,
            "timestamp": self.timestamp,
            "approved_by": self.approved_by,
        }


class AutoEvolutionTracer:
    """Trazador de eventos de evolución con atribución de seguridad."""

    def __init__(self):
        self._events: List[EvolutionEvent] = []
        self._agent_events: Dict[str, List[str]] = {}

    def record(
        self,
        agent_id: str,
        action: EvolutionAction,
        parent_dna: Dict[str, Any],
        child_dna: Dict[str, Any],
        reason: str,
        evidence: Optional[Dict[str, Any]] = None,
        security_metrics_before: Optional[Dict[str, Any]] = None,
        security_metrics_after: Optional[Dict[str, Any]] = None,
        approved_by: Optional[str] = None,
    ) -> EvolutionEvent:
        """Registra un evento evolutivo con hashes de ADN."""
        event_id = f"evo-{agent_id}-{int(time.time() * 1000)}-{len(self._events)}"
        parent_hash = self._hash_dna(parent_dna)
        child_hash = self._hash_dna(child_dna)
        event = EvolutionEvent(
            event_id=event_id,
            agent_id=agent_id,
            action=action,
            parent_dna_hash=parent_hash,
            child_dna_hash=child_hash,
            reason=reason,
            evidence=evidence or {},
            security_metrics_before=security_metrics_before or {},
            security_metrics_after=security_metrics_after or {},
            approved_by=approved_by,
        )
        self._events.append(event)
        self._agent_events.setdefault(agent_id, []).append(event_id)
        return event

    def _hash_dna(self, dna: Dict[str, Any]) -> str:
        canonical = json.dumps(dna, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def attribute_degradation(
        self,
        agent_id: str,
        security_metric: str,
        before_value: float,
        after_value: float,
        threshold: float = 0.05,
    ) -> Optional[EvolutionEvent]:
        """Atribuye una degradación de seguridad al último evento evolutivo del agente."""
        if agent_id not in self._agent_events:
            return None
        event_ids = self._agent_events[agent_id]
        if not event_ids:
            return None
        # Buscar el último evento cuyo before tenga el metrica
        for event_id in reversed(event_ids):
            event = next((e for e in self._events if e.event_id == event_id), None)
            if not event:
                continue
            prev = event.security_metrics_before.get(security_metric)
            if prev is None:
                continue
            delta = after_value - prev
            if delta > threshold:  # empeoró más que el umbral
                event.attributed_degradation = (
                    f"{security_metric} degraded from {prev} to {after_value} "
                    f"after {event.action.value} (delta={delta:.4f})"
                )
                event.security_metrics_after[security_metric] = after_value
                return event
        return None

    def get_events(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if agent_id:
            return [e.to_dict() for e in self._events if e.agent_id == agent_id]
        return [e.to_dict() for e in self._events]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self._events],
            "agent_index": self._agent_events,
        }
