"""
UC-329 — Knowledge Graph para GraphRAG-GoT.

Almacena nodos y aristas, soporta búsqueda por vecindad, cálculo de
métricas básicas y serialización.
"""

from typing import Dict, List, Optional, Any, Set
from collections import defaultdict, deque

from graph_models import GraphNode, GraphEdge, GraphMetrics


class KnowledgeGraph:
    """
    Grafo de conocimiento persistente en memoria.

    Soporta inserción, vecindad, caminos simples y métricas estructurales.
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._edge_index: Dict[str, List[str]] = defaultdict(list)

    def add_node(self, node: GraphNode) -> GraphNode:
        """Agrega un nodo al grafo."""
        self._nodes[node.node_id] = node
        if node.node_id not in self._adjacency:
            self._adjacency[node.node_id] = []
        return node

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        """Agrega una arista al grafo."""
        if edge.source not in self._nodes or edge.target not in self._nodes:
            return edge
        self._edges[edge.edge_id] = edge
        self._adjacency[edge.source].append(edge.target)
        self._edge_index[f"{edge.source}:{edge.target}"].append(edge.edge_id)
        return edge

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        return self._edges.get(edge_id)

    def neighbors(self, node_id: str) -> List[GraphNode]:
        """Retorna nodos vecinos."""
        return [self._nodes[nid] for nid in self._adjacency.get(node_id, []) if nid in self._nodes]

    def edges_from(self, source_id: str) -> List[GraphEdge]:
        """Retorna aristas que salen de un nodo."""
        return [self._edges[eid] for eid in self._edge_index.get(f"{source_id}:*", [])]

    def all_edges_between(self, source_id: str, target_id: str) -> List[GraphEdge]:
        return [self._edges[eid] for eid in self._edge_index.get(f"{source_id}:{target_id}", [])]

    def bfs(
        self,
        start_node_id: str,
        max_depth: int = 3,
        min_weight: float = 0.0,
    ) -> Dict[str, int]:
        """BFS con control de profundidad y peso mínimo de arista."""
        visited = {start_node_id: 0}
        queue = deque([(start_node_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for target_id, edge_ids in [(k, v) for k, v in self._edge_index.items() if k.startswith(f"{current}:")]:
                if not edge_ids:
                    continue
                edge = self._edges[edge_ids[0]]
                if edge.composite_weight < min_weight:
                    continue
                _, neighbor = target_id.split(":", 1)
                if neighbor not in visited:
                    visited[neighbor] = depth + 1
                    queue.append((neighbor, depth + 1))
        return visited

    def find_paths(
        self,
        start: str,
        end: str,
        max_depth: int = 4,
        top_k: int = 5,
    ) -> List[List[str]]:
        """
        Encuentra los top_k caminos simples entre dos nodos usando DFS.

        Simples = sin repetir nodos.
        """
        paths = []

        def dfs(current: str, target: str, path: List[str], depth: int):
            if len(paths) >= top_k:
                return
            if depth > max_depth:
                return
            if current == target and len(path) > 1:
                paths.append(list(path))
                return
            for neighbor_id in self._adjacency.get(current, []):
                if neighbor_id in path:
                    continue
                path.append(neighbor_id)
                dfs(neighbor_id, target, path, depth + 1)
                path.pop()

        dfs(start, end, [start], 0)
        return paths

    def compute_metrics(self) -> GraphMetrics:
        """Calcula métricas estructurales básicas del grafo."""
        n = len(self._nodes)
        m = len(self._edges)
        density = 0.0
        if n > 1:
            density = (2.0 * m) / (n * (n - 1.0))

        # Approximate diameter via BFS from random sample
        diameter = 0
        sample = list(self._nodes.keys())[:10]
        for start in sample:
            levels = self.bfs(start, max_depth=10)
            if levels:
                diameter = max(diameter, max(levels.values()))

        return GraphMetrics(
            node_count=n,
            edge_count=m,
            density=density,
            diameter=diameter,
        )

    def connected_components(self) -> List[Set[str]]:
        """Encuentra componentes conectadas (no dirigido)."""
        visited = set()
        components = []
        for node_id in self._nodes:
            if node_id in visited:
                continue
            component = set()
            queue = deque([node_id])
            while queue:
                current = queue.popleft()
                if current in component:
                    continue
                component.add(current)
                for neighbor in self._adjacency.get(current, []):
                    if neighbor not in component:
                        queue.append(neighbor)
            visited.update(component)
            components.append(component)
        return components

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
            "edges": {eid: e.to_dict() for eid, e in self._edges.items()},
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
        }

    def reset(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._adjacency.clear()
        self._edge_index.clear()

    def __len__(self) -> int:
        return len(self._nodes)
