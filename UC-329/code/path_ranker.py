"""
UC-329 — Path Ranker para GraphRAG-GoT.

Genera, ranquea y selecciona caminos de razonamiento diversos sobre un
subgrafo de conocimiento.
"""

from typing import List, Dict, Optional, Any, Set
from collections import defaultdict

from graph_models import ReasoningPath, ReasoningType, EdgeType
from knowledge_graph import KnowledgeGraph


class PathRanker:
    """
    Genera y ranquea caminos de razonamiento diversos.

    Métodos:
    - Encontrar caminos simples entre pares de nodos relevantes.
    - Calcular score por peso de aristas e importancia de nodos.
    - Clasificar tipo de razonamiento del camino.
    - Seleccionar subconjunto diverso usando distancia de Jaccard.
    """

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def generate_paths(
        self,
        graph: KnowledgeGraph,
        start_nodes: List[str],
        end_nodes: List[str],
        max_depth: int = 4,
    ) -> List[ReasoningPath]:
        """Genera caminos entre pares relevantes de nodos."""
        paths = []
        seen_paths: Set[str] = set()
        for start in start_nodes:
            for end in end_nodes:
                if start == end:
                    continue
                simple_paths = graph.find_paths(start, end, max_depth=max_depth, top_k=self.top_k)
                for p in simple_paths:
                    key = "->".join(p)
                    if key in seen_paths:
                        continue
                    seen_paths.add(key)
                    path_obj = self._build_path(graph, p)
                    if path_obj:
                        paths.append(path_obj)
        return paths

    def _build_path(self, graph: KnowledgeGraph, node_ids: List[str]) -> Optional[ReasoningPath]:
        """Construye un ReasoningPath a partir de una lista de IDs."""
        if len(node_ids) < 2:
            return None
        edge_ids = []
        for i in range(len(node_ids) - 1):
            edges = graph.all_edges_between(node_ids[i], node_ids[i + 1])
            if not edges:
                return None
            edge_ids.append(edges[0].edge_id)

        reasoning_type = self._classify_reasoning(graph, edge_ids)
        score = self._score_path(graph, node_ids, edge_ids)

        return ReasoningPath(
            nodes=node_ids,
            edges=edge_ids,
            score=score,
            reasoning_type=reasoning_type,
        )

    def _classify_reasoning(self, graph: KnowledgeGraph, edge_ids: List[str]) -> ReasoningType:
        """Clasifica el tipo de razonamiento predominante."""
        type_counts: Dict[ReasoningType, int] = defaultdict(int)
        for eid in edge_ids:
            edge = graph.get_edge(eid)
            if not edge:
                continue
            if edge.edge_type in (EdgeType.CAUSES,):
                type_counts[ReasoningType.CAUSAL] += 1
            elif edge.edge_type in (EdgeType.SIMILAR_TO, EdgeType.CONTRADICTS):
                type_counts[ReasoningType.COMPARATIVE] += 1
            elif edge.edge_type in (EdgeType.PART_OF, EdgeType.IS_A):
                type_counts[ReasoningType.HIERARCHICAL] += 1
            elif edge.edge_type in (EdgeType.BEFORE, EdgeType.AFTER):
                type_counts[ReasoningType.TEMPORAL] += 1
            else:
                type_counts[ReasoningType.ASSOCIATIVE] += 1
        if not type_counts:
            return ReasoningType.ASSOCIATIVE
        return max(type_counts, key=type_counts.get)

    def _score_path(
        self,
        graph: KnowledgeGraph,
        node_ids: List[str],
        edge_ids: List[str],
    ) -> float:
        """Calcula score del camino sumando pesos de aristas."""
        total = 0.0
        for eid in edge_ids:
            edge = graph.get_edge(eid)
            if edge:
                total += edge.composite_weight
        # Node importance: prefer nodes with high confidence
        for nid in node_ids:
            node = graph.get_node(nid)
            if node:
                total += node.confidence
        return total

    def select_diverse_paths(self, paths: List[ReasoningPath], k: Optional[int] = None) -> List[ReasoningPath]:
        """
        Selecciona subconjunto diverso de caminos.

        Greedy: en cada paso elige el camino con mayor score mínimo de
        diversidad (Jaccard) respecto a los ya seleccionados.
        """
        k = k or self.top_k
        if len(paths) <= k:
            return paths

        selected = []
        remaining = list(paths)
        remaining.sort(key=lambda p: p.score, reverse=True)
        selected.append(remaining.pop(0))

        while remaining and len(selected) < k:
            best = None
            best_score = -1.0
            for path in remaining:
                min_div = min(self._jaccard_distance(path, s) for s in selected)
                combined = path.score * (1 + min_div)
                if combined > best_score:
                    best_score = combined
                    best = path
            if best:
                selected.append(best)
                remaining.remove(best)

        return selected

    def _jaccard_distance(self, p1: ReasoningPath, p2: ReasoningPath) -> float:
        """Distancia de Jaccard entre conjuntos de nodos de dos caminos."""
        set1 = set(p1.nodes)
        set2 = set(p2.nodes)
        union = set1 | set2
        if not union:
            return 0.0
        return 1.0 - len(set1 & set2) / len(union)

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "top_k": self.top_k,
        }
