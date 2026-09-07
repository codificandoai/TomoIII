"""
UC-326 — Cross-Retriever para MAQRI.

Busca simultáneamente en múltiples fuentes de memoria:
- Memoria episódica (experiencias pasadas).
- Memoria semántica (base de conocimiento del dominio).
- Fuentes externas (inyectables).

Fusiona, deduplica y ordena los resultados antes de entregarlos a UC-325.
"""

from typing import List, Dict, Optional, Any, Callable

from maqri_models import (
    RetrievedDocument, MemoryType, MaqriConfig, CriticAssessment, WorkingMemory,
)
from episodic_memory import EpisodicMemory
from semantic_memory import SemanticMemory


class CrossRetriever:
    """
    Recuperador cruzado que combina resultados de múltiples stores.

    Cada fuente retorna documentos con score propio; CrossRetriever fusiona,
    normaliza scores (por rango dentro de cada fuente), deduplica, y ordena.
    """

    def __init__(
        self,
        config: Optional[MaqriConfig] = None,
        episodic: Optional[EpisodicMemory] = None,
        semantic: Optional[SemanticMemory] = None,
        external_retrievers: Optional[Dict[str, Callable]] = None,
    ):
        self.config = config if config is not None else MaqriConfig()
        self.episodic = episodic if episodic is not None else EpisodicMemory()
        self.semantic = semantic if semantic is not None else SemanticMemory()
        self.external_retrievers = external_retrievers if external_retrievers is not None else {}

    def search(
        self,
        query: str,
        working_memory: Optional[WorkingMemory] = None,
        iteration: int = 1,
        preferred_sources: Optional[List[str]] = None,
    ) -> List[RetrievedDocument]:
        """
        Ejecuta cross-retrieval en todas las fuentes configuradas.

        Retorna lista de documentos únicos ordenados por score fusionado.
        """
        all_docs: List[RetrievedDocument] = []

        # 1. Memoria Semántica (Base de conocimiento del dominio)
        semantic_docs = self.semantic.retrieve(
            query,
            top_k=self.config.top_k_per_source,
        )
        all_docs.extend(semantic_docs)

        # 2. Memoria Episódica (experiencias similares)
        if self.config.enable_episodic_memory:
            similar_episodes = self.episodic.find_similar(
                query, top_k=3, threshold=0.3
            )
            for ep in similar_episodes:
                # Convertir docs de episodios anteriores en docs recuperados
                for doc in ep.retrieved_docs[:2]:
                    if doc.memory_type != MemoryType.EPISODIC:
                        doc_copy = RetrievedDocument(
                            content=doc.content,
                            source=f"episodic::{ep.episode_id}",
                            memory_type=MemoryType.EPISODIC,
                            score=ep.relevance_score * doc.score if doc.score else ep.relevance_score,
                            metadata={
                                "episode_id": ep.episode_id,
                                "original_query": ep.original_query,
                                "refined_query": ep.refined_query,
                            },
                            retrieval_round=iteration,
                        )
                        all_docs.append(doc_copy)

        # 3. Fuentes externas inyectables
        for name, retriever in self.external_retrievers.items():
            try:
                external_results = retriever(query, top_k=self.config.top_k_per_source)
                for raw in external_results:
                    doc = RetrievedDocument(
                        content=raw.get("content", ""),
                        source=raw.get("source", name),
                        memory_type=MemoryType.EXTERNAL,
                        score=float(raw.get("score", 0.5)),
                        metadata=raw.get("metadata", {}),
                        retrieval_round=iteration,
                    )
                    all_docs.append(doc)
            except Exception:
                # Fallo silencioso de retriever externo
                continue

        # Normalizar scores por fuente si hay muchos documentos
        all_docs = self._normalize_scores(all_docs)

        # Deduplicar
        unique_docs = self._deduplicate(all_docs)

        # Filtrar por relevancia mínima
        filtered = [
            d for d in unique_docs
            if d.score >= self.config.min_relevance_threshold
        ]

        # Ordenar por score descendente
        filtered.sort(key=lambda d: d.score, reverse=True)

        # Limitar
        return filtered[: self.config.top_k_per_source * 3]

    def _normalize_scores(
        self,
        docs: List[RetrievedDocument],
    ) -> List[RetrievedDocument]:
        """
        Normaliza scores por fuente para que sean comparables.

        Mantiene scores absolutos si ya están en [0, 1]; de lo contrario
        aplica min-max por fuente.
        """
        by_source: Dict[str, List[RetrievedDocument]] = {}
        for doc in docs:
            by_source.setdefault(doc.source, []).append(doc)

        for source, source_docs in by_source.items():
            scores = [d.score for d in source_docs]
            min_score = min(scores) if scores else 0.0
            max_score = max(scores) if scores else 1.0

            if max_score - min_score < 0.01 or (0 <= min_score and max_score <= 1):
                continue

            for doc in source_docs:
                doc.score = (doc.score - min_score) / (max_score - min_score + 1e-6)

        return docs

    def _deduplicate(
        self,
        docs: List[RetrievedDocument],
    ) -> List[RetrievedDocument]:
        """Elimina documentos duplicados por fingerprint."""
        seen: Dict[str, RetrievedDocument] = {}
        for doc in docs:
            if doc.fingerprint in seen:
                existing = seen[doc.fingerprint]
                # Conservar el de mayor score
                if doc.score > existing.score:
                    seen[doc.fingerprint] = doc
            else:
                seen[doc.fingerprint] = doc
        return list(seen.values())

    def register_external_retriever(
        self,
        name: str,
        retriever: Callable[[str, int], List[Dict[str, Any]]],
    ) -> None:
        """Registra un retriever externo."""
        self.external_retrievers[name] = retriever

    def get_source_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de las fuentes configuradas."""
        return {
            "episodic": self.episodic.get_statistics(),
            "semantic": self.semantic.get_stats(),
            "external_sources": list(self.external_retrievers.keys()),
        }

    def reset(self) -> None:
        """Limpia memoria episódica y semántica."""
        self.episodic.reset()
        self.semantic.reset()
