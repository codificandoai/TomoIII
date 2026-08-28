"""Protocolo Gossip (difusión epidémica) para UC-272.

Los agentes difunden conocimiento parcial a sus vecinos sin necesidad de pizarra central.
Cada fragmento decae en confianza con cada hop y tiene un límite de propagación.

Inspirado en: gossipcat-ai/gossipcat-ai.
"""
from __future__ import annotations

from typing import Dict, List, Set
from uuid import UUID

from config import GossipConfig, get_config
from models import KnowledgeFragment


class GossipProtocol:
    """Protocolo de difusión epidémica de conocimiento."""

    def __init__(
        self, agent_id: str, neighbors: List[str], config: GossipConfig | None = None
    ) -> None:
        self.agent_id = agent_id
        self.neighbors = set(neighbors)
        self.config = config or get_config().gossip
        self.knowledge_base: Dict[str, KnowledgeFragment] = {}
        self._seen: Set[UUID] = set()
        self._outbox: List[tuple[str, KnowledgeFragment]] = []

    def create_fragment(self, topic: str, content: Dict, confidence: float = 1.0) -> KnowledgeFragment:
        """Crea y registra un fragmento de conocimiento propio."""
        fragment = KnowledgeFragment(
            source_agent=self.agent_id,
            topic=topic,
            content=content,
            confidence=confidence,
            max_hops=self.config.max_hops,
            seen_by=[self.agent_id],
        )
        self.knowledge_base[topic] = fragment
        self._seen.add(fragment.fragment_id)
        # Programar broadcast
        for neighbor in self.neighbors:
            self._outbox.append((neighbor, fragment))
        return fragment

    def receive(self, fragment: KnowledgeFragment) -> bool:
        """Recibe un fragmento de un vecino. Retorna True si se aceptó."""
        if fragment.fragment_id in self._seen:
            return False
        if fragment.hop_count >= fragment.max_hops:
            return False

        self._seen.add(fragment.fragment_id)

        # Actualizar knowledge base si es mejor
        existing = self.knowledge_base.get(fragment.topic)
        if existing is None or fragment.confidence > existing.confidence:
            self.knowledge_base[fragment.topic] = fragment

        # Re-difundir con decay
        forwarded = KnowledgeFragment(
            fragment_id=fragment.fragment_id,
            source_agent=fragment.source_agent,
            topic=fragment.topic,
            content=fragment.content,
            confidence=round(fragment.confidence * self.config.decay_factor, 6),
            hop_count=fragment.hop_count + 1,
            max_hops=fragment.max_hops,
            seen_by=fragment.seen_by + [self.agent_id],
        )
        for neighbor in self.neighbors:
            if neighbor not in forwarded.seen_by:
                self._outbox.append((neighbor, forwarded))

        return True

    def flush_outbox(self) -> List[tuple[str, KnowledgeFragment]]:
        """Vacía y retorna los mensajes pendientes de envío."""
        out = list(self._outbox)
        self._outbox.clear()
        return out

    @property
    def topics(self) -> List[str]:
        return list(self.knowledge_base.keys())
