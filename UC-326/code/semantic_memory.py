"""
UC-326 — Memoria Semántica para MAQRI.

Simula una base de conocimiento vectorial del dominio. Permite indexar
documentos y recuperarlos por similitud léxica (stub reemplazable por
vector DB real como Pinecone, Milvus, FAISS).
"""

from typing import List, Dict, Optional, Any

from maqri_models import RetrievedDocument, MemoryType


class SemanticMemory:
    """
    Memoria semántica: base de conocimiento del dominio.

    Provee:
    - Indexación de documentos con metadata.
    - Recuperación por similitud léxica (stub).
    - Soporte para múltiples colecciones/sources.
    """

    def __init__(self, name: str = "domain_kb"):
        self.name = name
        self._documents: List[RetrievedDocument] = []
        self._by_source: Dict[str, List[RetrievedDocument]] = {}

    def add_document(
        self,
        content: str,
        source: str = "kb",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RetrievedDocument:
        """Indexa un documento en la memoria semántica."""
        doc = RetrievedDocument(
            content=content,
            source=source,
            memory_type=MemoryType.SEMANTIC,
            score=0.0,
            metadata=metadata or {},
        )
        self._documents.append(doc)
        self._by_source.setdefault(source, []).append(doc)
        return doc

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        source: str = "kb",
    ) -> List[RetrievedDocument]:
        """Indexa múltiples documentos."""
        added = []
        for doc in documents:
            added.append(self.add_document(
                content=doc.get("content", ""),
                source=doc.get("source", source),
                metadata=doc.get("metadata", {}),
            ))
        return added

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        source_filter: Optional[str] = None,
        min_score: float = 0.1,
    ) -> List[RetrievedDocument]:
        """
        Recupera documentos por similitud léxica con el query.

        En producción, esto usaría embeddings + cosine similarity.
        """
        query_words = set(query.lower().split())
        if not query_words:
            return []

        docs = self._documents
        if source_filter:
            docs = self._by_source.get(source_filter, [])

        scored = []
        for doc in docs:
            doc_words = set(doc.content.lower().split())
            if not doc_words:
                continue
            intersection = len(query_words & doc_words)
            union = len(query_words | doc_words)
            score = intersection / union if union > 0 else 0.0
            if score >= min_score:
                doc.score = round(score, 4)
                scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    def get_document_by_id(self, doc_id: str) -> Optional[RetrievedDocument]:
        """Busca un documento por ID."""
        for doc in self._documents:
            if doc.doc_id == doc_id:
                return doc
        return None

    def get_sources(self) -> List[str]:
        """Retorna todas las fuentes indexadas."""
        return list(self._by_source.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de la memoria semántica."""
        return {
            "name": self.name,
            "total_documents": len(self._documents),
            "sources": self.get_sources(),
            "documents_per_source": {
                src: len(docs) for src, docs in self._by_source.items()
            },
        }

    def reset(self) -> None:
        """Limpia la memoria semántica."""
        self._documents.clear()
        self._by_source.clear()

    def __len__(self) -> int:
        return len(self._documents)
