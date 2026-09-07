"""
UC-329 — Graph Memory para GraphRAG-GoT.

Persiste y recupera subgrafos y sesiones de razonamiento. En producción
se conectaría con UC-296; aquí es un stub en memoria.
"""

from typing import Dict, List, Optional, Any
import json
import time

from knowledge_graph import KnowledgeGraph
from graph_models import GraphRAGGoTResult, ReasoningPath


class GraphMemory:
    """
    Memoria de grafos y sesiones de razonamiento para UC-329.

    Permite:
    - Almacenar subgrafos por query/domino.
    - Cachear caminos de razonamiento exitosos.
    - Recuperar sesiones previas para reutilización.
    """

    def __init__(self):
        self._graphs: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._path_cache: Dict[str, List[Dict[str, Any]]] = {}

    def save_graph(
        self,
        graph: KnowledgeGraph,
        key: str,
        domain: str = "default",
    ) -> str:
        """Persiste un grafo serializado."""
        storage_key = f"{domain}:{key}"
        self._graphs[storage_key] = {
            "data": graph.to_dict(),
            "timestamp": time.time(),
            "domain": domain,
        }
        return storage_key

    def load_graph(self, key: str, domain: str = "default") -> Optional[KnowledgeGraph]:
        """Carga un grafo previamente persistido."""
        storage_key = f"{domain}:{key}"
        record = self._graphs.get(storage_key)
        if not record:
            return None
        graph = KnowledgeGraph()
        for nid, ndata in record["data"].get("nodes", {}).items():
            from graph_models import GraphNode, NodeType
            node = GraphNode(
                node_id=ndata.get("node_id", nid),
                label=ndata.get("label", ""),
                node_type=NodeType(ndata.get("node_type", "entity")),
                attributes=ndata.get("attributes", {}),
                source_id=ndata.get("source_id"),
                confidence=ndata.get("confidence", 0.7),
                timestamp=ndata.get("timestamp", time.time()),
            )
            graph.add_node(node)
        for eid, edata in record["data"].get("edges", {}).items():
            from graph_models import GraphEdge, EdgeType
            edge = GraphEdge(
                edge_id=edata.get("edge_id", eid),
                source=edata.get("source", ""),
                target=edata.get("target", ""),
                edge_type=EdgeType(edata.get("edge_type", "related_to")),
                weight=edata.get("weight", 1.0),
                semantic_weight=edata.get("semantic_weight", 0.0),
                temporal_weight=edata.get("temporal_weight", 0.0),
                authority_weight=edata.get("authority_weight", 0.0),
                attributes=edata.get("attributes", {}),
                source_id=edata.get("source_id"),
            )
            graph.add_edge(edge)
        return graph

    def save_session(
        self,
        result: GraphRAGGoTResult,
        domain: str = "default",
    ) -> str:
        """Persiste una sesión de razonamiento."""
        session_id = result.trace_id
        self._sessions[session_id] = {
            "query": result.query,
            "domain": domain,
            "timestamp": time.time(),
            "result_summary": {
                "answer": result.answer[:200] if result.answer else "",
                "metrics": result.metrics.to_dict(),
                "path_count": len(result.reasoning_paths),
            },
        }
        return session_id

    def cache_paths(
        self,
        query_signature: str,
        paths: List[ReasoningPath],
    ) -> None:
        """Cachea caminos de razonamiento exitosos."""
        self._path_cache[query_signature] = [p.to_dict() for p in paths]

    def get_cached_paths(self, query_signature: str) -> List[Dict[str, Any]]:
        """Recupera caminos cacheados."""
        return list(self._path_cache.get(query_signature, []))

    def list_sessions(self, domain: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista sesiones almacenadas."""
        sessions = list(self._sessions.values())
        if domain:
            sessions = [s for s in sessions if s.get("domain") == domain]
        return sessions[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de memoria."""
        return {
            "stored_graphs": len(self._graphs),
            "stored_sessions": len(self._sessions),
            "cached_path_signatures": len(self._path_cache),
        }

    def reset(self) -> None:
        self._graphs.clear()
        self._sessions.clear()
        self._path_cache.clear()
