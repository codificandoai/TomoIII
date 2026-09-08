"""
UC-162 — Tracker de linaje semántico.

El linaje en LLMOps no es lineal: es un grafo. Cada transformación
(ingesta → limpieza → chunking → embedding → indexación → recuperación → generación)
hereda el hash del antecesor y genera el propio.

A diferencia de UC-087 que rastrea hash → fuente → timestamp (linaje
criptográfico), UC-162 rastrea concepto → transformación → derivación
lógica → modelo (linaje semántico).
"""

import time
import uuid
from typing import Dict, List, Optional, Any

from models_162 import LineageGraph, LineageNode, LineageStage
from logical_data_model import compute_hash


class LineageTracker:
    """
    Mantiene el grafo de linaje semántico a través de todas las
    transformaciones del pipeline LLMOps.
    """

    def __init__(self):
        self.graph = LineageGraph()

    def register_ingest(
        self,
        document_id: str,
        text: str,
        source: str = "",
        source_url: str = "",
        extraction_method: str = "",
    ) -> LineageNode:
        """Registra la ingesta de un documento."""
        data = {
            "document_id": document_id,
            "text": text,
            "source": source,
            "source_url": source_url,
            "extraction_method": extraction_method,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.INGEST.value,
            entity_id=document_id,
            hash=h,
            parent_hash="",
            metadata={
                "source": source,
                "source_url": source_url,
                "extraction_method": extraction_method,
                "text_length": len(text),
            },
        )
        self.graph.add_node(node)
        return node

    def register_clean(
        self,
        document_id: str,
        cleaned_text: str,
        parent_hash: str,
        script_version: str = "v1.0",
        rules_applied: List[str] = None,
        tokens_before: int = 0,
        tokens_after: int = 0,
    ) -> LineageNode:
        """Registra la limpieza de un documento."""
        data = {
            "document_id": document_id,
            "cleaned_text": cleaned_text,
            "parent_hash": parent_hash,
            "script_version": script_version,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.CLEAN.value,
            entity_id=document_id,
            hash=h,
            parent_hash=parent_hash,
            metadata={
                "script_version": script_version,
                "rules_applied": rules_applied or [],
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "tokens_delta": tokens_before - tokens_after,
            },
        )
        self.graph.add_node(node)
        return node

    def register_chunk(
        self,
        chunk_id: str,
        document_id: str,
        text: str,
        parent_hash: str,
        strategy: str = "fixed",
        size: int = 0,
        overlap: int = 0,
        start_char: int = 0,
        end_char: int = 0,
    ) -> LineageNode:
        """Registra un chunk derivado de un documento limpio."""
        data = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "text": text,
            "parent_hash": parent_hash,
            "strategy": strategy,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.CHUNK.value,
            entity_id=chunk_id,
            hash=h,
            parent_hash=parent_hash,
            metadata={
                "document_id": document_id,
                "strategy": strategy,
                "size": size,
                "overlap": overlap,
                "start_char": start_char,
                "end_char": end_char,
            },
        )
        self.graph.add_node(node)
        return node

    def register_embedding(
        self,
        chunk_id: str,
        vector: List[float],
        parent_hash: str,
        model: str = "text-embedding-3",
        dimension: int = 0,
    ) -> LineageNode:
        """Registra la generación de un embedding."""
        data = {
            "chunk_id": chunk_id,
            "vector_dim": len(vector),
            "parent_hash": parent_hash,
            "model": model,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.EMBED.value,
            entity_id=chunk_id,
            hash=h,
            parent_hash=parent_hash,
            metadata={
                "model": model,
                "dimension": dimension or len(vector),
                "generated_at": time.time(),
            },
        )
        self.graph.add_node(node)
        return node

    def register_index(
        self,
        chunk_id: str,
        index_name: str,
        parent_hash: str,
        vector_store: str = "in_memory",
        shard: str = "default",
    ) -> LineageNode:
        """Registra la indexación de un embedding."""
        data = {
            "chunk_id": chunk_id,
            "index_name": index_name,
            "parent_hash": parent_hash,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.INDEX.value,
            entity_id=chunk_id,
            hash=h,
            parent_hash=parent_hash,
            metadata={
                "vector_store": vector_store,
                "index_name": index_name,
                "shard": shard,
            },
        )
        self.graph.add_node(node)
        return node

    def register_retrieval(
        self,
        query: str,
        retrieved_chunk_ids: List[str],
        parent_hashes: List[str],
        top_k: int = 5,
        scores: List[float] = None,
    ) -> LineageNode:
        """Registra la recuperación RAG."""
        data = {
            "query": query,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "top_k": top_k,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.RETRIEVE.value,
            entity_id=query[:50],
            hash=h,
            parent_hash=parent_hashes[0] if parent_hashes else "",
            metadata={
                "query": query,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "top_k": top_k,
                "scores": scores or [],
                "parent_hashes": parent_hashes,
            },
        )
        self.graph.add_node(node)
        return node

    def register_generation(
        self,
        response: str,
        parent_hash: str,
        prompt_version: str = "",
        model: str = "",
        chunk_ids: List[str] = None,
    ) -> LineageNode:
        """Registra la generación final del LLM."""
        data = {
            "response": response,
            "parent_hash": parent_hash,
            "prompt_version": prompt_version,
        }
        h = compute_hash(data)
        node = LineageNode(
            node_id=str(uuid.uuid4()),
            stage=LineageStage.GENERATE.value,
            entity_id=str(uuid.uuid4())[:8],
            hash=h,
            parent_hash=parent_hash,
            metadata={
                "response_length": len(response),
                "prompt_version": prompt_version,
                "model": model,
                "chunk_ids": chunk_ids or [],
            },
        )
        self.graph.add_node(node)
        return node

    def trace_back(self, hash: str) -> List[LineageNode]:
        """Traza el linaje hacia atrás desde un hash dado."""
        chain = []
        node_map = {n.hash: n for n in self.graph.nodes}
        current = node_map.get(hash)
        while current:
            chain.append(current)
            if current.parent_hash:
                current = node_map.get(current.parent_hash)
            else:
                break
        return chain

    def get_full_lineage(self) -> Dict[str, Any]:
        """Retorna el grafo de linaje completo."""
        return self.graph.to_dict()

    def reset(self):
        self.graph = LineageGraph()
