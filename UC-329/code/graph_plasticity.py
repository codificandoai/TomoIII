"""
UC-329 — Graph Plasticity para GraphRAG-GoT.

Ajusta pesos de aristas y confianza de nodos según retroalimentación
proveniente de UC-315/UC-325 (éxito/fracaso de caminos de razonamiento).
"""

from typing import Dict, List, Optional, Any
import time

from knowledge_graph import KnowledgeGraph
from graph_models import GraphEdge, GraphNode


class GraphPlasticity:
    """
    Implementa plasticidad sináptica digital sobre el grafo.

    Reglas:
    - Reforzar aristas/caminos que condujeron a buenas decisiones.
    - Debilitar aristas/caminos que condujeron a malas decisiones.
    - Registrar experiencias positivas/negativas para aprendizaje futuro.
    """

    def __init__(
        self,
        reinforcement_rate: float = 0.1,
        decay_rate: float = 0.05,
        min_weight: float = 0.1,
        max_weight: float = 5.0,
    ):
        self.reinforcement_rate = reinforcement_rate
        self.decay_rate = decay_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self._feedback_log: List[Dict[str, Any]] = []

    def reinforce(
        self,
        graph: KnowledgeGraph,
        node_ids: List[str],
        edge_ids: List[str],
        feedback_score: float = 1.0,
    ) -> None:
        """
        Refuerza nodos y aristas involucrados en un razonamiento exitoso.
        """
        for edge_id in edge_ids:
            edge = graph.get_edge(edge_id)
            if edge:
                edge.weight = min(
                    self.max_weight,
                    edge.weight + self.reinforcement_rate * feedback_score,
                )
                edge.attributes["last_reinforced"] = time.time()

        for node_id in node_ids:
            node = graph.get_node(node_id)
            if node:
                node.confidence = min(
                    1.0,
                    node.confidence + self.reinforcement_rate * feedback_score * 0.5,
                )
                node.attributes["last_reinforced"] = time.time()

        self._log_feedback("reinforce", node_ids, edge_ids, feedback_score)

    def penalize(
        self,
        graph: KnowledgeGraph,
        node_ids: List[str],
        edge_ids: List[str],
        feedback_score: float = 1.0,
    ) -> None:
        """
        Debilita nodos y aristas involucrados en un razonamiento fallido.
        """
        for edge_id in edge_ids:
            edge = graph.get_edge(edge_id)
            if edge:
                edge.weight = max(
                    self.min_weight,
                    edge.weight - self.decay_rate * feedback_score,
                )
                edge.attributes["last_penalized"] = time.time()

        for node_id in node_ids:
            node = graph.get_node(node_id)
            if node:
                node.confidence = max(
                    0.0,
                    node.confidence - self.decay_rate * feedback_score * 0.5,
                )
                node.attributes["last_penalized"] = time.time()

        self._log_feedback("penalize", node_ids, edge_ids, feedback_score)

    def _log_feedback(
        self,
        action: str,
        node_ids: List[str],
        edge_ids: List[str],
        feedback_score: float,
    ) -> None:
        self._feedback_log.append({
            "timestamp": time.time(),
            "action": action,
            "node_ids": node_ids,
            "edge_ids": edge_ids,
            "feedback_score": feedback_score,
        })

    def apply_feedback(
        self,
        graph: KnowledgeGraph,
        path_node_ids: List[str],
        path_edge_ids: List[str],
        outcome: str,
        intensity: float = 1.0,
    ) -> None:
        """
        Aplica retroalimentación a un camino completo.

        outcome: 'success' | 'failure' | 'partial'
        """
        if outcome == "success":
            self.reinforce(graph, path_node_ids, path_edge_ids, intensity)
        elif outcome == "failure":
            self.penalize(graph, path_node_ids, path_edge_ids, intensity)
        elif outcome == "partial":
            self.reinforce(graph, path_node_ids, path_edge_ids, intensity * 0.3)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de plasticidad."""
        reinforces = sum(1 for f in self._feedback_log if f["action"] == "reinforce")
        penalizes = sum(1 for f in self._feedback_log if f["action"] == "penalize")
        return {
            "total_feedback_events": len(self._feedback_log),
            "reinforcements": reinforces,
            "penalizations": penalizes,
            "recent_feedback": self._feedback_log[-10:],
        }

    def reset(self) -> None:
        self._feedback_log.clear()
