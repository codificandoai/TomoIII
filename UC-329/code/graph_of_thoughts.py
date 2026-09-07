"""
UC-329 — Graph of Thoughts Engine para GraphRAG-GoT.

Construye un Grafo del Pensamiento a partir de un subgrafo de
conocimiento, fusionando caminos de razonamiento y organizando nodos
en capas de abstracción.
"""

from typing import Dict, List, Optional, Any, Set
from collections import defaultdict

from graph_models import (
    ThoughtNode, ThoughtEdge, ReasoningPath, ThoughtRole, EdgeType, GraphMetrics,
)
from knowledge_graph import KnowledgeGraph


class GraphOfThoughts:
    """
    Construye y gestiona el Grafo del Pensamiento (GoT).

    Responsabilidades:
    - Fusionar caminos de razonamiento en un grafo unificado.
    - Asignar roles y niveles de abstracción.
    - Detectar comunidades/perspectivas.
    """

    def __init__(self):
        self._thoughts: Dict[str, ThoughtNode] = {}
        self._edges: Dict[str, ThoughtEdge] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)

    def build_from_paths(
        self,
        paths: List[ReasoningPath],
        knowledge_graph: KnowledgeGraph,
        node_scores: Optional[Dict[str, float]] = None,
    ) -> "GraphOfThoughts":
        """
        Construye el GoT a partir de caminos de razonamiento.

        Cada nodo del knowledge graph se convierte en un ThoughtNode.
        Las aristas que aparecen en al menos 2 caminos se conservan.
        """
        node_scores = node_scores or {}
        edge_appearance: Dict[str, int] = defaultdict(int)
        edge_to_type: Dict[str, EdgeType] = {}

        for path in paths:
            for i, edge_id in enumerate(path.edges):
                edge = knowledge_graph.get_edge(edge_id)
                if edge:
                    edge_appearance[edge_id] += 1
                    edge_to_type[edge_id] = edge.edge_type

        # Include all nodes from paths
        used_node_ids: Set[str] = set()
        for path in paths:
            used_node_ids.update(path.nodes)

        # Create thought nodes
        for node_id in used_node_ids:
            kg_node = knowledge_graph.get_node(node_id)
            if not kg_node:
                continue
            thought = ThoughtNode(
                thought_id=node_id,
                label=kg_node.label,
                role=self._infer_role(kg_node, paths),
                node_refs=[node_id],
                abstraction_level=self._infer_abstraction_level(kg_node, paths),
                support_score=node_scores.get(node_id, 0.0),
                confidence=kg_node.confidence,
                attributes=kg_node.attributes,
            )
            self._thoughts[thought.thought_id] = thought

        # Create thought edges that appear in at least 2 paths or strong edges
        for edge_id, count in edge_appearance.items():
            if count < 2:
                continue
            edge = knowledge_graph.get_edge(edge_id)
            if not edge:
                continue
            tedge = ThoughtEdge(
                source=edge.source,
                target=edge.target,
                edge_type=edge_to_type.get(edge_id, EdgeType.RELATED_TO),
                weight=1.0 + 0.5 * (count - 1),
                justification=f"Arista presente en {count} caminos de razonamiento.",
            )
            self._edges[tedge.thought_edge_id] = tedge
            self._adjacency[tedge.source].append(tedge.target)

        # Assign community ids via connected components approximation
        communities = self._connected_components()
        for idx, component in enumerate(communities):
            for thought_id in component:
                if thought_id in self._thoughts:
                    self._thoughts[thought_id].community_id = f"community_{idx}"

        return self

    def _infer_role(self, kg_node: Any, paths: List[ReasoningPath]) -> ThoughtRole:
        """Infiere el rol de un nodo en el razonamiento."""
        node_id = kg_node.node_id
        appears_first = any(path.nodes and path.nodes[0] == node_id for path in paths)
        appears_last = any(path.nodes and path.nodes[-1] == node_id for path in paths)
        if appears_first:
            return ThoughtRole.PREMISE
        if appears_last:
            return ThoughtRole.CONCLUSION
        if kg_node.node_type.value in ["hypothesis", "concept"]:
            return ThoughtRole.HYPOTHESIS
        return ThoughtRole.EVIDENCE

    def _infer_abstraction_level(self, kg_node: Any, paths: List[ReasoningPath]) -> int:
        """Infiere nivel de abstracción (1 concreto, 2-3 intermedio, 4 meta)."""
        if kg_node.node_type.value in ["evidence", "entity"]:
            return 1
        if kg_node.node_type.value in ["concept", "hypothesis"]:
            return 2
        if kg_node.node_type.value == "conclusion":
            return 3
        return 2

    def _connected_components(self) -> List[Set[str]]:
        """Encuentra componentes conectadas no dirigidas."""
        visited = set()
        components = []
        for thought_id in self._thoughts:
            if thought_id in visited:
                continue
            component = set()
            stack = [thought_id]
            while stack:
                current = stack.pop()
                if current in component:
                    continue
                component.add(current)
                for neighbor in self._adjacency.get(current, []):
                    if neighbor not in component:
                        stack.append(neighbor)
                # reverse adjacency
                for src, tgts in self._adjacency.items():
                    if current in tgts and src not in component:
                        stack.append(src)
            visited.update(component)
            components.append(component)
        return components

    def add_meta_thought(self, label: str, role: ThoughtRole, refs: List[str]) -> ThoughtNode:
        """Agrega un nodo meta al grafo del pensamiento."""
        thought = ThoughtNode(
            label=label,
            role=role,
            node_refs=refs,
            abstraction_level=4,
        )
        self._thoughts[thought.thought_id] = thought
        return thought

    def compute_metrics(self) -> GraphMetrics:
        """Calcula métricas del GoT."""
        n = len(self._thoughts)
        m = len(self._edges)
        density = 0.0
        if n > 1:
            density = (2.0 * m) / (n * (n - 1.0))
        return GraphMetrics(
            node_count=n,
            edge_count=m,
            density=density,
            community_count=len(self._connected_components()),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thoughts": {tid: t.to_dict() for tid, t in self._thoughts.items()},
            "edges": {eid: e.to_dict() for eid, e in self._edges.items()},
            "node_count": len(self._thoughts),
            "edge_count": len(self._edges),
        }

    def get_thought(self, thought_id: str) -> Optional[ThoughtNode]:
        return self._thoughts.get(thought_id)
