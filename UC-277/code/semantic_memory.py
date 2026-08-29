"""SemanticMemory — Grafo de conocimiento para UC-277.

Memoria semantica: hechos, preferencias, conceptos y relaciones.
- Nodos: hechos, preferencias, entidades.
- Aristas: relaciones con fuerza y evidencia.
- Deduplicacion por similitud.
- Refuerzo de nodos existentes.

Inspirado en agiresearch/A-mem: memoria agenticaja dinamica.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional
from uuid import uuid4

from embeddings import SimpleEmbeddingModel
from models import SemanticEdge, SemanticNode


class SemanticMemory:
    """Memoria semantica: grafo de conocimiento relacional."""

    def __init__(self, embedding_model: SimpleEmbeddingModel,
                 similarity_threshold: float = 0.85) -> None:
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.nodes: Dict[str, SemanticNode] = {}
        self.edges: List[SemanticEdge] = []
        self._adjacency: Dict[str, List[SemanticEdge]] = defaultdict(list)

    def add_fact(self, agent_id: str, content: str,
                 node_type: str = "fact",
                 source_episode_id: Optional[str] = None,
                 confidence: float = 0.8) -> str:
        """Agrega hecho (deduplica si ya existe similar)."""
        existing = self._find_similar(agent_id, content)
        if existing:
            self._strengthen(existing.node_id, source_episode_id, confidence)
            return existing.node_id

        node_id = f"{agent_id}:{node_type}:{uuid4().hex[:10]}"
        embedding = self.embedding_model.encode(content)
        node = SemanticNode(
            node_id=node_id, agent_id=agent_id, node_type=node_type,
            content=content, embedding=embedding, confidence=confidence,
            source_episodes=[source_episode_id] if source_episode_id else [],
        )
        self.nodes[node_id] = node
        return node_id

    def add_preference(self, agent_id: str, preference: str,
                       sentiment: float,
                       source_episode_id: Optional[str] = None) -> str:
        """Agrega preferencia (positiva o negativa)."""
        node_type = "preference_positive" if sentiment > 0 else "preference_negative"
        return self.add_fact(agent_id, preference, node_type, source_episode_id, abs(sentiment))

    def add_relation(self, source_id: str, target_id: str,
                     relation: str, strength: float = 0.5) -> None:
        """Agrega o refuerza relacion entre nodos."""
        existing = next(
            (e for e in self.edges
             if e.source_id == source_id and e.target_id == target_id and e.relation == relation),
            None
        )
        if existing:
            existing.strength = min(1.0, existing.strength + 0.1)
            existing.evidence_count += 1
        else:
            edge = SemanticEdge(source_id=source_id, target_id=target_id,
                                relation=relation, strength=strength)
            self.edges.append(edge)
            self._adjacency[source_id].append(edge)

    def query(self, agent_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Consulta memoria semantica por similitud."""
        query_emb = self.embedding_model.encode(query)
        scored = []
        for node in self.nodes.values():
            if node.agent_id != agent_id:
                continue
            sim = self.embedding_model.similarity(query_emb, node.embedding)
            scored.append((sim * node.confidence, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, node in scored[:top_k]:
            related = self._get_related(node.node_id)
            results.append({"node_id": node.node_id, "content": node.content,
                            "type": node.node_type, "confidence": node.confidence,
                            "score": round(score, 4), "related": related})
        return results

    def get_preferences(self, agent_id: str) -> Dict[str, List[Dict]]:
        """Retorna preferencias del agente."""
        prefs: Dict[str, List[Dict]] = {"positive": [], "negative": []}
        for node in self.nodes.values():
            if node.agent_id != agent_id:
                continue
            if node.node_type == "preference_positive":
                prefs["positive"].append({"content": node.content, "confidence": node.confidence})
            elif node.node_type == "preference_negative":
                prefs["negative"].append({"content": node.content, "confidence": node.confidence})
        return prefs

    def get_stats(self, agent_id: str) -> Dict[str, Any]:
        agent_nodes = [n for n in self.nodes.values() if n.agent_id == agent_id]
        by_type: Dict[str, int] = defaultdict(int)
        for n in agent_nodes:
            by_type[n.node_type] += 1
        return {"total_nodes": len(agent_nodes), "by_type": dict(by_type),
                "total_edges": len(self.edges)}

    def _find_similar(self, agent_id: str, content: str) -> Optional[SemanticNode]:
        query_emb = self.embedding_model.encode(content)
        for node in self.nodes.values():
            if node.agent_id != agent_id:
                continue
            sim = self.embedding_model.similarity(query_emb, node.embedding)
            if sim >= self.similarity_threshold:
                return node
        return None

    def _strengthen(self, node_id: str, source_episode_id: Optional[str],
                    new_confidence: float) -> None:
        node = self.nodes[node_id]
        node.confidence = min(1.0, (node.confidence + new_confidence) / 2 + 0.05)
        node.last_validated = time.time()
        if source_episode_id and source_episode_id not in node.source_episodes:
            node.source_episodes.append(source_episode_id)

    def _get_related(self, node_id: str) -> List[Dict[str, Any]]:
        related = []
        for edge in self._adjacency.get(node_id, []):
            target = self.nodes.get(edge.target_id)
            if target:
                related.append({"node_id": target.node_id, "content": target.content,
                                "relation": edge.relation, "strength": edge.strength})
        return related
