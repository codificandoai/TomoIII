"""
UC-329 — GraphRAG Retriever para GraphRAG-GoT.

Recupera subgrafos relevantes para una consulta usando similitud
semántica simple (basada en vectores TF-IDF-like) y expansión por
vecindad.
"""

import math
import re
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque

from knowledge_graph import KnowledgeGraph
from graph_models import GraphNode, GraphRAGGoTConfig


class GraphRAGRetriever:
    """
    Recupera subgrafos relevantes para una consulta.

    Usa una representación vectorial simple (bag-of-words con frecuencia)
para calcular similitud coseno entre query y nodos.
    """

    def __init__(self, config: Optional[GraphRAGGoTConfig] = None):
        self.config = config or GraphRAGGoTConfig()

    def _tokenize(self, text: str) -> List[str]:
        """Tokeniza y normaliza texto."""
        return re.findall(r"[a-zA-Záéíóúñü0-9]+", text.lower())

    def _tf_vector(self, text: str) -> Dict[str, float]:
        """Calcula vector TF simple."""
        tokens = self._tokenize(text)
        vec: Dict[str, float] = defaultdict(float)
        for t in tokens:
            vec[t] += 1.0
        return dict(vec)

    def _cosine_similarity(self, v1: Dict[str, float], v2: Dict[str, float]) -> float:
        """Similitud coseno entre dos vectores TF."""
        keys = set(v1.keys()) | set(v2.keys())
        dot = sum(v1.get(k, 0.0) * v2.get(k, 0.0) for k in keys)
        norm1 = math.sqrt(sum(x * x for x in v1.values()))
        norm2 = math.sqrt(sum(x * x for x in v2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def embed_query(self, query: str) -> Dict[str, float]:
        """Genera embedding de consulta."""
        return self._tf_vector(query)

    def seed_nodes(
        self,
        graph: KnowledgeGraph,
        query: str,
        top_k: int = 10,
    ) -> List[Tuple[GraphNode, float]]:
        """Identifica nodos semilla por similitud con la consulta."""
        query_vec = self.embed_query(query)
        scored = []
        for node in graph._nodes.values():
            node_text = f"{node.label} {' '.join(str(v) for v in node.attributes.values())}"
            node_vec = self._tf_vector(node_text)
            sim = self._cosine_similarity(query_vec, node_vec)
            if sim >= self.config.relevance_threshold:
                scored.append((node, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def expand_subgraph(
        self,
        graph: KnowledgeGraph,
        seed_node_ids: List[str],
        max_depth: Optional[int] = None,
        min_weight: float = 0.0,
    ) -> KnowledgeGraph:
        """
        Expande un subgrafo a partir de nodos semilla usando BFS.

        Retorna un nuevo KnowledgeGraph con el subgrafo candidato.
        """
        max_depth = max_depth or self.config.max_search_depth
        subgraph = KnowledgeGraph()
        visited_depth: Dict[str, int] = {}
        queue = deque()

        for seed_id in seed_node_ids:
            node = graph.get_node(seed_id)
            if node:
                subgraph.add_node(node)
                visited_depth[seed_id] = 0
                queue.append((seed_id, 0))

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in [e for e in graph._edges.values() if e.source == current_id]:
                if edge.composite_weight < min_weight:
                    continue
                target = graph.get_node(edge.target)
                if target is None:
                    continue
                if edge.target not in visited_depth:
                    visited_depth[edge.target] = depth + 1
                    subgraph.add_node(target)
                    queue.append((edge.target, depth + 1))
                subgraph.add_edge(edge)

        return subgraph

    def score_nodes(
        self,
        subgraph: KnowledgeGraph,
        query: str,
    ) -> Dict[str, float]:
        """
        Calcula relevancia de cada nodo considerando similitud y
centralidad simple en el subgrafo.
        """
        query_vec = self.embed_query(query)
        scores: Dict[str, float] = {}
        # Approximate centrality by degree
        degrees = {nid: len(subgraph._adjacency.get(nid, [])) for nid in subgraph._nodes}
        max_degree = max(degrees.values()) if degrees else 1

        for nid, node in subgraph._nodes.items():
            node_text = f"{node.label} {' '.join(str(v) for v in node.attributes.values())}"
            sim = self._cosine_similarity(query_vec, self._tf_vector(node_text))
            centrality = degrees.get(nid, 0) / max(1, max_degree)
            scores[nid] = sim * (1 + 0.5 * centrality)
        return scores

    def retrieve(
        self,
        graph: KnowledgeGraph,
        query: str,
    ) -> Tuple[KnowledgeGraph, Dict[str, float]]:
        """
        Recupera el subgrafo candidato relevante para una consulta.

        Retorna (subgraph, scores).
        """
        seeds = self.seed_nodes(graph, query)
        seed_ids = [n.node_id for n, _ in seeds]
        if not seed_ids:
            return KnowledgeGraph(), {}
        subgraph = self.expand_subgraph(graph, seed_ids)
        scores = self.score_nodes(subgraph, query)
        return subgraph, scores

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
        }
