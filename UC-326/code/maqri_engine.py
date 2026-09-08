"""
UC-326 — Motor MAQRI (Memory-Augmented Query Refinement Iterative).

Orquesta el ciclo de búsqueda inteligente con memoria:
1. Recibe un query del cerebro AGI vía UC-325.
2. Recupera documentos de múltiples stores (semántico, episódico, externos).
3. El Critic evalúa calidad y detecta información faltante.
4. Si no converge, el QueryRefiner326 refina la consulta usando memoria.
5. Repite hasta convergencia o max_iterations.
6. Devuelve chunks refinados a UC-325.
"""

from typing import List, Dict, Optional, Any, Callable
import time

from maqri_models import (
    MaqriResult, MaqriConfig, MaqriIteration, SearchEpisode,
    RetrievedDocument, WorkingMemory, MemoryQuery, RetrievalVerdict,
    QueryVariant,
)
from episodic_memory import EpisodicMemory
from semantic_memory import SemanticMemory
from procedural_memory import ProceduralMemory
from query_refiner_326 import QueryRefiner326
from divergence_strategy import DivergenceStrategy
from critic_evaluator import CriticEvaluator
from cross_retriever import CrossRetriever
from observability_326 import ObservabilityManager


class MaqriEngine:
    """
    Motor principal de MAQRI.

    Proporciona a UC-325 un retrieval inteligente, iterativo y con memoria.
    """

    def __init__(
        self,
        config: Optional[MaqriConfig] = None,
        episodic: Optional[EpisodicMemory] = None,
        semantic: Optional[SemanticMemory] = None,
        external_retrievers: Optional[Dict[str, Callable]] = None,
    ):
        self.config = config or MaqriConfig()

        # Componentes de memoria
        self.episodic = episodic if episodic is not None else EpisodicMemory()
        self.semantic = semantic if semantic is not None else SemanticMemory()
        self.procedural = ProceduralMemory()

        # Componentes de retrieval y refinamiento
        self.cross_retriever = CrossRetriever(
            config=self.config,
            episodic=self.episodic,
            semantic=self.semantic,
            external_retrievers=external_retrievers if external_retrievers is not None else {},
        )
        self.refiner = QueryRefiner326(
            config=self.config,
            episodic=self.episodic,
            procedural=self.procedural,
        )
        self.critic = CriticEvaluator()

        # Observabilidad
        self.observability = ObservabilityManager()

        # Historial de búsquedas
        self._history: List[MaqriResult] = []

    def search(
        self,
        query: str,
        context: str = "",
        domain: str = "general",
        max_iterations: Optional[int] = None,
    ) -> MaqriResult:
        """
        Ejecuta una búsqueda MAQRI iterativa.

        Args:
            query: consulta original del cerebro AGI.
            context: contexto adicional de la tarea actual.
            domain: dominio (trading, agi, reservations, etc.).
            max_iterations: override del máximo de iteraciones.

        Returns:
            MaqriResult con documentos refinados y traza completa.
        """
        start_time = time.time()
        max_iter = max_iterations or self.config.max_iterations

        result = MaqriResult(query=query)
        wm = WorkingMemory(original_goal=query, accumulated_facts=[], failed_approaches=[])

        # Span principal
        root_span = self.observability.start_span(
            operation="maqri_search",
            trace_id=result.trace_id,
            attributes={"query": query, "domain": domain, "context": context},
        )

        self.observability.log(
            "INFO", f"Starting MAQRI search: {query[:120]}",
            trace_id=result.trace_id,
        )

        current_query = query
        all_docs: List[RetrievedDocument] = []
        current_assessment = None

        try:
            for iteration in range(1, max_iter + 1):
                iter_start = time.time()

                iter_span = self.observability.start_span(
                    operation=f"maqri_iteration_{iteration}",
                    trace_id=result.trace_id,
                    parent_span_id=root_span.span_id,
                    attributes={"iteration": iteration, "query": current_query},
                )

                # PASO 1: Cross-retrieval con query actual y variantes
                variants = self.refiner.generate_variants(
                    query=current_query,
                    context=context,
                    failed_approaches=wm.failed_approaches,
                    assessment=current_assessment,
                )

                variant_queries = [v.query for v in variants]
                docs_from_variants = []
                for vq in variant_queries:
                    docs_from_variants.extend(self.cross_retriever.search(
                        query=vq,
                        working_memory=wm,
                        iteration=iteration,
                    ))

                # Agregar docs de la query principal
                docs = self.cross_retriever.search(
                    query=current_query,
                    working_memory=wm,
                    iteration=iteration,
                )
                docs.extend(docs_from_variants)

                # Dedup interno
                seen = {}
                unique = []
                for d in sorted(docs, key=lambda x: x.score, reverse=True):
                    if d.fingerprint not in seen:
                        seen[d.fingerprint] = d
                        unique.append(d)
                docs = unique

                all_docs.extend(docs)

                # PASO 2: Critic evalúa la recuperación
                assessment = self.critic.evaluate(
                    query=current_query,
                    docs=docs,
                    working_memory=wm,
                )
                current_assessment = assessment

                # PASO 3: Actualizar memoria de trabajo
                for d in docs[:5]:
                    wm.accumulated_facts.append(d.content)

                # PASO 4: Guardar episodio
                episode = SearchEpisode(
                    original_query=query,
                    refined_query=current_query,
                    retrieved_docs=docs,
                    relevance_score=assessment.overall_score,
                    missing_info=assessment.missing_info,
                    failure_reason=assessment.failure_reason,
                    iteration=iteration,
                )
                self.episodic.add(episode)
                result.episodes.append(episode)

                # Detectar divergencia
                divergence_applied = self.episodic.is_redundant(
                    current_query,
                    window=self.config.similarity_window,
                    threshold=self.config.redundancy_threshold,
                )

                # PASO 5: Registrar iteración
                iter_duration = (time.time() - iter_start) * 1000
                maqri_iter = MaqriIteration(
                    iteration=iteration,
                    query=current_query,
                    variants_used=variant_queries,
                    docs_retrieved=len(docs),
                    docs_unique=len(set(d.fingerprint for d in docs)),
                    assessment=assessment,
                    divergence_applied=divergence_applied,
                    duration_ms=iter_duration,
                )
                result.iterations.append(maqri_iter)

                # Métricas
                self.observability.inc_counter("maqri_iterations_total")
                self.observability.observe_histogram("maqri_iteration_duration_ms", iter_duration)
                self.observability.set_gauge("maqri_confidence", assessment.confidence)
                self.observability.set_gauge("maqri_docs_retrieved", len(docs))

                self.observability.log(
                    "INFO",
                    f"Iteration {iteration}: score={assessment.overall_score:.3f}, "
                    f"confidence={assessment.confidence:.3f}, docs={len(docs)}, "
                    f"redundant={divergence_applied}",
                    trace_id=result.trace_id,
                    iteration=iteration,
                )

                self.observability.end_span(iter_span.span_id)

                # PASO 6: Condición de convergencia
                if assessment.confidence >= self.config.convergence_threshold:
                    result.verdict = RetrievalVerdict.CONVERGED
                    self.observability.log(
                        "INFO",
                        f"MAQRI converged at iteration {iteration}",
                        trace_id=result.trace_id,
                    )
                    break

                # PASO 7: Si no converge, refinar query
                if iteration < max_iter:
                    variant = self.refiner.refine_from_failure(
                        query=current_query,
                        missing_info=assessment.missing_info,
                        failure_reason=assessment.failure_reason,
                        accumulated_facts=wm.accumulated_facts,
                    )
                    current_query = variant.query
                    wm.failed_approaches.append(assessment.failure_reason)

                    self.observability.log(
                        "INFO",
                        f"Refined query: {current_query[:120]}",
                        trace_id=result.trace_id,
                        iteration=iteration,
                    )

            else:
                # Se agotaron iteraciones sin convergencia
                result.verdict = RetrievalVerdict.MAX_ITERATIONS
                self.observability.log(
                    "INFO",
                    f"MAQRI reached max iterations ({max_iter})",
                    trace_id=result.trace_id,
                )

            # Resultado final
            result.final_query = current_query
            result.working_memory = wm
            result.iterations_executed = len(result.iterations)
            result.docs = self._deduplicate_and_rank(all_docs)
            result.final_score = (
                result.iterations[-1].assessment.confidence
                if result.iterations and result.iterations[-1].assessment
                else 0.0
            )
            result.success = result.verdict in (
                RetrievalVerdict.CONVERGED,
                RetrievalVerdict.MAX_ITERATIONS,
            )
            result.duration_ms = (time.time() - start_time) * 1000

            self.observability.observe_histogram(
                "maqri_total_duration_ms", result.duration_ms
            )
            self.observability.observe_histogram(
                "maqri_iterations_to_completion", float(result.iterations_executed)
            )

            if result.verdict == RetrievalVerdict.CONVERGED:
                self.observability.inc_counter("maqri_convergence_total")

            self.observability.end_span(root_span.span_id)

        except Exception as e:
            self.observability.log(
                "ERROR", f"MAQRI search failed: {str(e)}",
                trace_id=result.trace_id,
            )
            self.observability.end_span(root_span.span_id, status="ERROR")
            result.verdict = RetrievalVerdict.INSUFFICIENT_DATA
            result.success = False
            result.duration_ms = (time.time() - start_time) * 1000

        self._history.append(result)
        return result

    def _deduplicate_and_rank(
        self,
        docs: List[RetrievedDocument],
    ) -> List[RetrievedDocument]:
        """Deduplica y ordena documentos por score."""
        seen: Dict[str, RetrievedDocument] = {}
        for doc in docs:
            if doc.fingerprint in seen:
                if doc.score > seen[doc.fingerprint].score:
                    seen[doc.fingerprint] = doc
            else:
                seen[doc.fingerprint] = doc

        unique = list(seen.values())
        unique.sort(key=lambda d: d.score, reverse=True)
        return unique

    def register_external_retriever(
        self,
        name: str,
        retriever: Callable[[str, int], List[Dict[str, Any]]],
    ) -> None:
        """Registra un retriever externo."""
        self.cross_retriever.register_external_retriever(name, retriever)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna historial de búsquedas."""
        return [r.to_dict() for r in self._history[-limit:]]

    def get_observability_summary(self) -> Dict[str, Any]:
        """Retorna resumen de observabilidad."""
        return self.observability.get_summary()

    # -------------------------------------------------------------------
    # UC-324 Safe Shutdown: redacted memory snapshot
    # -------------------------------------------------------------------

    def redacted_snapshot(self, shutdown_id: str = "") -> Dict[str, Any]:
        """Return a redacted memory snapshot for UC-324 safe shutdown.

        Returns hash/manifest and counts/safe metadata, NOT raw memory
        contents, private memory, or chain-of-thought.
        """
        import hashlib as _hl

        # Collect safe metadata counts
        episodic_count = len(self.episodic._episodes) if hasattr(self.episodic, "_episodes") else 0
        semantic_count = len(self.semantic._entries) if hasattr(self.semantic, "_entries") else 0
        history_count = len(self._history)

        # Compute manifest hash over counts (not raw data)
        manifest_data = f"episodic:{episodic_count}|semantic:{semantic_count}|history:{history_count}|sid:{shutdown_id}"
        manifest_hash = _hl.sha256(manifest_data.encode()).hexdigest()

        return {
            "adapter": "uc326_maqri",
            "shutdown_id": shutdown_id,
            "manifest_hash": manifest_hash,
            "episodic_entry_count": episodic_count,
            "semantic_entry_count": semantic_count,
            "search_history_count": history_count,
            "raw_data_included": False,
        }

    def reset(self) -> None:
        """Resetea todo el estado."""
        self.episodic.reset()
        self.semantic.reset()
        self.procedural.reset_statistics()
        self.cross_retriever.reset()
        self.refiner.reset()
        self.observability.reset()
        self._history.clear()
