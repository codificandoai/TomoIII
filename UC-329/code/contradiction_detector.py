"""
UC-329 — Contradiction Detector para GraphRAG-GoT.

Detecta inconsistencias lógicas y temporales en el grafo del
pensamiento, como aristas contradictorias, ciclos negativos y
relaciones causales invertidas.
"""

from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from graph_models import ThoughtNode, ThoughtEdge, EdgeType


class ContradictionDetector:
    """
    Detecta contradicciones en grafos de pensamiento.

    Tipos:
    - Aristas contradictorias directas (A → B y A ↔ B).
    - Ciclos negativos en relaciones de soporte/refutación.
    - Inconsistencias temporales (A before B, B before A).
    - Inconsistencias causales invertidas.
    """

    def __init__(self):
        self.contradiction_types = [
            "direct_contradiction",
            "temporal_inversion",
            "causal_inversion",
            "negative_cycle",
        ]

    def detect(
        self,
        thoughts: Dict[str, ThoughtNode],
        edges: Dict[str, ThoughtEdge],
    ) -> List[Dict[str, Any]]:
        """Detecta todas las inconsistencias en el grafo."""
        contradictions = []
        contradictions.extend(self._detect_direct_contradictions(edges))
        contradictions.extend(self._detect_temporal_inversions(edges))
        contradictions.extend(self._detect_causal_inversions(edges))
        contradictions.extend(self._detect_negative_cycles(thoughts, edges))
        return contradictions

    def _detect_direct_contradictions(
        self,
        edges: Dict[str, ThoughtEdge],
    ) -> List[Dict[str, Any]]:
        """Detecta pares de aristas entre mismos nodos con tipos opuestos."""
        contradictions = []
        pairs: Dict[Tuple[str, str], List[ThoughtEdge]] = defaultdict(list)
        for edge in edges.values():
            key = tuple(sorted((edge.source, edge.target)))
            pairs[key].append(edge)

        for (src, tgt), edge_list in pairs.items():
            types = {e.edge_type for e in edge_list}
            if (EdgeType.SUPPORTS in types and EdgeType.REFUTES in types) or \
               (EdgeType.CAUSES in types and EdgeType.CONTRADICTS in types):
                contradictions.append({
                    "type": "direct_contradiction",
                    "source": src,
                    "target": tgt,
                    "edges": [e.thought_edge_id for e in edge_list],
                    "message": f"Nodos {src} y {tgt} tienen relaciones opuestas.",
                })
        return contradictions

    def _detect_temporal_inversions(
        self,
        edges: Dict[str, ThoughtEdge],
    ) -> List[Dict[str, Any]]:
        """Detecta ciclos temporales A before B y B before A."""
        contradictions = []
        before_pairs: List[Tuple[str, str]] = []
        for edge in edges.values():
            if edge.edge_type == EdgeType.BEFORE:
                before_pairs.append((edge.source, edge.target))

        for a, b in before_pairs:
            for edge in edges.values():
                if edge.edge_type == EdgeType.BEFORE and edge.source == b and edge.target == a:
                    contradictions.append({
                        "type": "temporal_inversion",
                        "source": a,
                        "target": b,
                        "message": f"Inversión temporal: {a} antes que {b} y viceversa.",
                    })
        return contradictions

    def _detect_causal_inversions(
        self,
        edges: Dict[str, ThoughtEdge],
    ) -> List[Dict[str, Any]]:
        """Detecta causas invertidas transitivas A→B→C y C→A."""
        contradictions = []
        causal_pairs = [(e.source, e.target) for e in edges.values() if e.edge_type == EdgeType.CAUSES]
        for a, b in causal_pairs:
            for c, d in causal_pairs:
                if b == c and a == d:
                    contradictions.append({
                        "type": "causal_inversion",
                        "cycle": [a, b, d],
                        "message": f"Ciclo causal invertido: {a} → {b} → {a}.",
                    })
        return contradictions

    def _detect_negative_cycles(
        self,
        thoughts: Dict[str, ThoughtNode],
        edges: Dict[str, ThoughtEdge],
    ) -> List[Dict[str, Any]]:
        """
        Detecta ciclos negativos simples: soporte → refutación → soporte.
        """
        contradictions = []
        adjacency: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        for edge in edges.values():
            weight = -1.0 if edge.edge_type in (EdgeType.REFUTES, EdgeType.CONTRADICTS) else 1.0
            adjacency[edge.source].append((edge.target, weight))

        for start in thoughts:
            cycle = self._find_cycle(start, start, adjacency, set(), 0, 3)
            if cycle and cycle[1] < 0:
                contradictions.append({
                    "type": "negative_cycle",
                    "nodes": cycle[0],
                    "weight": cycle[1],
                    "message": f"Ciclo negativo detectado: {' -> '.join(cycle[0])}",
                })
        return contradictions

    def _find_cycle(
        self,
        current: str,
        target: str,
        adjacency: Dict[str, List[Tuple[str, float]]],
        visited: set,
        weight: float,
        max_depth: int,
    ) -> Optional[Tuple[List[str], float]]:
        """Busca ciclos de longitud limitada."""
        if max_depth == 0:
            return None
        visited.add(current)
        for neighbor, w in adjacency.get(current, []):
            if neighbor == target and len(visited) > 1:
                return (list(visited) + [neighbor], weight + w)
            if neighbor not in visited:
                result = self._find_cycle(neighbor, target, adjacency, visited.copy(), weight + w, max_depth - 1)
                if result:
                    return result
        return None

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "detectable_types": self.contradiction_types,
        }
