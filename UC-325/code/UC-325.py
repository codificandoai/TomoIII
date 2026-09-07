"""
Codificando.AI
UC-325: Bucles de Razonamiento Autorreflexivos para Recuperación Precisa.
Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

UC-325 — Motor de Bucles de Razonamiento Autorreflexivos (Reasoning Loop Engine).

Capa independiente que envuelve al cerebro AGI (UC-315) sin modificarlo.
Se inserta entre MP-04 (ReAct+ToT) y MP-05 (Decisión BDI), implementando
ciclos iterativos de evaluación, refinamiento y síntesis con controles de
calidad en cada etapa para eliminar alucinaciones y converger en respuestas
precisas.

Principios:
- UC-315 decide, UC-322 resuelve, UC-324 contiene, UC-317 ejecuta.
- UC-325 verifica que el razonamiento sea correcto ANTES de decidir.
- Un modelo genera evidencia. La evidencia no es una orden.
- No toca el cerebro AGI: importa UC-315 vía PYTHONPATH.
"""

from typing import List, Dict, Optional, Callable, Any
import time
import uuid

from reasoning_models import (
    ReasoningState,
    ReasoningResult,
    ReasoningConfig,
    ReasoningVerdict,
    RetrievedChunk,
    Hypothesis,
    KnowledgeGap,
    QualityScore,
    HallucinationReport,
    LoopIteration,
    LoopPhase,
    HypothesisStatus,
    DEFAULT_QUALITY_THRESHOLDS,
)
from quality_gates import QualityGateEvaluator
from hallucination_detector import HallucinationDetector
from query_refiner import QueryRefiner
from retrieval_evaluator import RetrievalEvaluator
from convergence_monitor import ConvergenceMonitor
from observability_325 import ObservabilityManager


# ─── RETRIEVER SIMULADO (para tests y demo) ─────────────────────────────────

class StubRetriever:
    """
    Retriever simulado que genera chunks de ejemplo.
    En producción, reemplazar con HybridRetriever de UC-251 o similar.
    """

    def __init__(self, knowledge_base: Optional[List[Dict[str, Any]]] = None):
        self._kb = knowledge_base or self._default_kb()
        self._call_count = 0

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        domain: str = "general",
    ) -> List[Dict[str, Any]]:
        """Recupera chunks relevantes al query."""
        self._call_count += 1
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for item in self._kb:
            content_words = set(item["content"].lower().split())
            overlap = len(query_words & content_words)
            score = overlap / max(len(query_words), 1) if query_words else 0.0
            score = min(score * 1.5, 1.0)  # Boost
            if score > 0.05:
                scored.append({
                    "content": item["content"],
                    "source": item.get("source", "knowledge_base"),
                    "score": round(score, 4),
                    "metadata": item.get("metadata", {}),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _default_kb(self) -> List[Dict[str, Any]]:
        return [
            {
                "content": "Los bucles de razonamiento iterativos permiten a los agentes evaluar y refinar sus respuestas antes de presentarlas al usuario.",
                "source": "reasoning_theory",
                "metadata": {"topic": "reasoning_loops"},
            },
            {
                "content": "La detección de alucinaciones verifica que cada afirmación esté soportada por evidencia recuperada del corpus de conocimiento.",
                "source": "hallucination_detection",
                "metadata": {"topic": "quality_control"},
            },
            {
                "content": "El refinamiento de queries modifica las consultas originales para obtener información más relevante en iteraciones sucesivas.",
                "source": "query_refinement",
                "metadata": {"topic": "retrieval"},
            },
            {
                "content": "La convergencia se alcanza cuando la confianza del agente deja de cambiar significativamente entre iteraciones.",
                "source": "convergence_theory",
                "metadata": {"topic": "convergence"},
            },
            {
                "content": "Los quality gates evalúan relevancia, cobertura, consistencia, confianza y novedad en cada iteración del razonamiento.",
                "source": "quality_gates_doc",
                "metadata": {"topic": "quality"},
            },
            {
                "content": "El cerebro AGI UC-315 razona una sola vez y decide sin verificar si su razonamiento es bueno, lo cual es un problema arquitectónico.",
                "source": "uc315_analysis",
                "metadata": {"topic": "problem_statement"},
            },
            {
                "content": "La síntesis multi-ronda integra hipótesis confirmadas y resuelve conflictos entre afirmaciones contradictorias.",
                "source": "synthesis_theory",
                "metadata": {"topic": "synthesis"},
            },
            {
                "content": "El feedback en tiempo real permite que los veredictos de calidad modifiquen el razonamiento actual en lugar de guardarse para el futuro.",
                "source": "feedback_theory",
                "metadata": {"topic": "feedback"},
            },
            {
                "content": "Tree of Thoughts expande ramas de razonamiento y poda las que no superan umbrales de confianza.",
                "source": "tot_theory",
                "metadata": {"topic": "tree_of_thoughts"},
            },
            {
                "content": "El monitor metacognitivo diagnostica coherencia y emite veredictos pero no retroalimenta al razonamiento actual.",
                "source": "metacognitive_analysis",
                "metadata": {"topic": "metacognition"},
            },
        ]


# ─── GENERADOR DE HIPÓTESIS SIMULADO ────────────────────────────────────────

class StubHypothesisGenerator:
    """
    Generador de hipótesis determinista basado en chunks.
    En producción, reemplazar con LLM.
    """

    def generate(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        existing: Dict[str, Hypothesis],
    ) -> List[Hypothesis]:
        """Genera hipótesis basadas en los chunks más relevantes."""
        hypotheses = []

        # Agrupar chunks por tema (source)
        by_source: Dict[str, List[RetrievedChunk]] = {}
        for c in chunks:
            by_source.setdefault(c.source, []).append(c)

        for source, source_chunks in by_source.items():
            if len(hypotheses) >= 5:
                break

            best = max(source_chunks, key=lambda x: x.score)

            # No duplicar hipótesis con el mismo contenido
            statement = f"Basado en {source}: {best.content[:120]}"
            already_exists = any(
                h.statement == statement for h in existing.values()
            )
            if already_exists:
                continue

            hyp = Hypothesis(
                statement=statement,
                supporting_chunks=[best.chunk_id],
                confidence=min(best.score * 0.9, 0.95),
                generation_round=max(
                    (h.generation_round for h in existing.values()), default=0
                ) + 1,
                evidence_strength=best.score,
                coherence_score=best.score * 0.8,
            )
            hypotheses.append(hyp)

        return hypotheses


# ─── MOTOR PRINCIPAL ─────────────────────────────────────────────────────────

class ReasoningLoopEngine:
    """
    Motor de Bucles de Razonamiento Autorreflexivos.

    Implementa un ciclo iterativo de 4 fases:
    1. DISCOVER: recuperación inicial + expansión de queries + hipótesis.
    2. REFINE: evaluación de retrieval + detección de alucinaciones +
       refinamiento de queries + re-recuperación para gaps.
    3. SYNTHESIZE: integración de hipótesis + resolución de conflictos +
       construcción de respuesta.
    4. CONVERGE: validación final + quality gates + decisión de parar o iterar.

    Cada iteración produce un LoopIteration con métricas de calidad,
    y el bucle continúa hasta convergencia o max_rounds.
    """

    def __init__(
        self,
        retriever: Optional[Any] = None,
        hypothesis_generator: Optional[Any] = None,
        config: Optional[ReasoningConfig] = None,
    ):
        self.config = config or ReasoningConfig()

        # Componentes inyectables
        self.retriever = retriever or StubRetriever()
        self.hypothesis_gen = hypothesis_generator or StubHypothesisGenerator()

        # Módulos internos
        self.quality_evaluator = QualityGateEvaluator(
            thresholds=self.config.quality_thresholds,
        )
        self.hallucination_detector = HallucinationDetector(
            threshold=self.config.hallucination_threshold,
        )
        self.query_refiner = QueryRefiner()
        self.retrieval_evaluator = RetrievalEvaluator(
            min_relevance=self.config.min_chunk_score,
        )
        self.convergence_monitor = ConvergenceMonitor(
            min_convergence_delta=self.config.min_convergence_delta,
            stall_threshold=self.config.stall_threshold,
        )
        self.observability = ObservabilityManager()

        # Historial
        self._history: List[ReasoningResult] = []

    def reason(
        self,
        query: str,
        domain: str = "general",
        max_rounds: Optional[int] = None,
    ) -> ReasoningResult:
        """
        Ejecuta el bucle de razonamiento completo.

        Entrada:
        - query: consulta en lenguaje natural.
        - domain: dominio del razonamiento.
        - max_rounds: override del máximo de iteraciones.

        Salida:
        - ReasoningResult con respuesta, confianza, veredicto, trazas.
        """
        # Inicializar estado
        state = ReasoningState(
            query=query,
            domain=domain,
            max_rounds=max_rounds or self.config.max_rounds,
        )

        # Span principal
        root_span = self.observability.start_span(
            operation="reasoning_loop",
            trace_id=state.trace_id,
            attributes={"query": query, "domain": domain},
        )

        self.observability.log(
            "INFO", f"Starting reasoning loop for: {query[:100]}",
            trace_id=state.trace_id,
        )

        try:
            # Bucle principal
            while state.round_number < state.max_rounds:
                round_start = time.time()
                round_num = state.round_number + 1

                # Span de iteración
                iter_span = self.observability.start_span(
                    operation=f"iteration_{round_num}",
                    trace_id=state.trace_id,
                    parent_span_id=root_span.span_id,
                    attributes={"round": round_num},
                )

                # FASE 1: DISCOVER
                state = self._discover(state)

                # FASE 2: REFINE
                state = self._refine(state)

                # FASE 3: SYNTHESIZE
                state = self._synthesize(state)

                # FASE 4: CONVERGE (evaluar y decidir)
                quality = self.quality_evaluator.evaluate(state)
                hallucination = self.hallucination_detector.detect(state)

                # Aplicar correcciones de alucinaciones
                if hallucination.detected:
                    state = self.hallucination_detector.apply_corrections(
                        state, hallucination
                    )
                    self.observability.inc_counter("hallucinations_detected_total")

                # Calcular confianza actual
                active = state.active_hypotheses
                if active:
                    current_confidence = sum(h.confidence for h in active) / len(active)
                else:
                    current_confidence = 0.0

                state.confidence_trajectory.append(current_confidence)
                state.round_number += 1

                # Registrar iteración
                duration_ms = (time.time() - round_start) * 1000
                convergence_delta = self.convergence_monitor.compute_convergence_delta(state)

                iteration = LoopIteration(
                    round_number=state.round_number,
                    phase=LoopPhase.CONVERGE,
                    chunks_added=len([c for c in state.all_chunks.values()
                                      if c.retrieval_round == state.round_number]),
                    chunks_total=len(state.all_chunks),
                    hypotheses_generated=len([h for h in state.hypotheses.values()
                                              if h.generation_round == state.round_number]),
                    hypotheses_refuted=len([h for h in state.hypotheses.values()
                                            if h.status == HypothesisStatus.REFUTED]),
                    hypotheses_active=len(active),
                    gaps_identified=len(state.gaps),
                    gaps_filled=sum(1 for g in state.gaps.values() if g.filled),
                    quality=quality,
                    hallucination_report=hallucination,
                    convergence_delta=convergence_delta,
                    duration_ms=duration_ms,
                )
                state.iterations.append(iteration)

                # Métricas
                self.observability.inc_counter("reasoning_rounds_total")
                self.observability.observe_histogram("reasoning_round_duration_ms", duration_ms)
                self.observability.set_gauge("active_hypotheses", len(active))
                self.observability.set_gauge("confidence_score", current_confidence)

                if quality.passed:
                    self.observability.inc_counter("quality_gates_passed_total")

                self.observability.end_span(iter_span.span_id)

                # Verificar convergencia
                stop_decision = self.convergence_monitor.should_stop(
                    state, quality, hallucination
                )

                self.observability.log(
                    "INFO",
                    f"Round {state.round_number}: confidence={current_confidence:.3f}, "
                    f"quality={quality.overall:.3f}, delta={convergence_delta:.4f}, "
                    f"stop={stop_decision['stop']}",
                    trace_id=state.trace_id,
                    round=state.round_number,
                )

                if stop_decision["stop"]:
                    state.verdict = stop_decision["verdict"]
                    break

            # Si el loop terminó sin veredicto explícito
            if state.verdict == ReasoningVerdict.INSUFFICIENT_DATA:
                state.verdict = ReasoningVerdict.MAX_ROUNDS

            # Construir respuesta final
            state.completed_at = time.time()

            if not state.final_answer and state.active_hypotheses:
                best = max(state.active_hypotheses, key=lambda h: h.confidence)
                state.final_answer = best.statement
                state.final_confidence = best.confidence

            # Métricas finales
            if state.verdict == ReasoningVerdict.CONVERGED:
                self.observability.inc_counter("convergence_achieved_total")

            self.observability.observe_histogram(
                "reasoning_total_duration_ms", state.duration_ms
            )
            self.observability.observe_histogram(
                "rounds_to_completion", float(state.round_number)
            )
            self.observability.end_span(root_span.span_id)

        except Exception as e:
            self.observability.log(
                "ERROR", f"Reasoning loop failed: {str(e)}",
                trace_id=state.trace_id,
            )
            self.observability.end_span(root_span.span_id, status="ERROR")
            state.verdict = ReasoningVerdict.INSUFFICIENT_DATA
            state.completed_at = time.time()

        # Construir resultado
        result = self._build_result(state)
        self._history.append(result)

        self.observability.log(
            "INFO",
            f"Reasoning complete: verdict={result.verdict.value}, "
            f"confidence={result.confidence:.3f}, rounds={result.rounds_executed}",
            trace_id=state.trace_id,
        )

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 1: DISCOVER
    # ═══════════════════════════════════════════════════════════════════════

    def _discover(self, state: ReasoningState) -> ReasoningState:
        """
        Recuperación inicial con expansión de queries.
        Genera hipótesis preliminares e identifica gaps.
        """
        # Generar queries expandidas
        if state.round_number == 0:
            queries = self.query_refiner.expand_initial(state.query, state.domain)
        else:
            # En rondas posteriores, queries para gaps
            queries = self.query_refiner.refine_for_gaps(state, state.unfilled_gaps)
            if not queries:
                queries = [state.query]

        # Recuperar chunks
        all_new_chunks = []
        for q in queries:
            raw_chunks = self.retriever.retrieve(
                q,
                top_k=self.config.max_chunks_per_round,
                domain=state.domain,
            )
            for raw in raw_chunks:
                chunk = RetrievedChunk(
                    content=raw.get("content", ""),
                    source=raw.get("source", "unknown"),
                    score=raw.get("score", 0.0),
                    metadata=raw.get("metadata", {}),
                    retrieval_round=state.round_number + 1,
                )
                all_new_chunks.append(chunk)

        # Deduplicar contra existentes
        unique_chunks = self.retrieval_evaluator.deduplicate(
            all_new_chunks, list(state.all_chunks.values())
        )

        # Filtrar por relevancia
        relevant_chunks = self.retrieval_evaluator.filter_relevant(
            state.query, unique_chunks
        )

        # Añadir al estado
        for chunk in relevant_chunks:
            state.all_chunks[chunk.chunk_id] = chunk

        # Generar hipótesis
        new_hypotheses = self.hypothesis_gen.generate(
            state.query,
            list(state.all_chunks.values()),
            state.hypotheses,
        )
        for h in new_hypotheses:
            state.hypotheses[h.hypothesis_id] = h

        return state

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 2: REFINE
    # ═══════════════════════════════════════════════════════════════════════

    def _refine(self, state: ReasoningState) -> ReasoningState:
        """
        Evalúa retrieval, detecta alucinaciones, refina queries,
        y re-recupera para gaps identificados.
        """
        # Evaluar calidad del retrieval
        retrieval_eval = self.retrieval_evaluator.evaluate_chunks(
            state.query, list(state.all_chunks.values())
        )

        # Verificar hipótesis débiles
        weak_hypotheses = [
            h for h in state.active_hypotheses
            if 0.3 <= h.confidence <= 0.7
        ]

        if weak_hypotheses:
            # Generar queries de verificación
            verification_queries = self.query_refiner.refine_for_verification(
                weak_hypotheses, state.query
            )

            for vq in verification_queries[:3]:
                raw_chunks = self.retriever.retrieve(
                    vq,
                    top_k=3,
                    domain=state.domain,
                )
                for raw in raw_chunks:
                    chunk = RetrievedChunk(
                        content=raw.get("content", ""),
                        source=raw.get("source", "unknown"),
                        score=raw.get("score", 0.0),
                        metadata={
                            **raw.get("metadata", {}),
                            "verification_target": True,
                        },
                        retrieval_round=state.round_number + 1,
                    )
                    if chunk.fingerprint not in {c.fingerprint for c in state.all_chunks.values()}:
                        state.all_chunks[chunk.chunk_id] = chunk

        # Identificar gaps basados en retrieval evaluation
        strategy = self.retrieval_evaluator.suggest_requery_strategy(
            retrieval_eval, state
        )

        if strategy["strategy"] != "none" and not state.gaps:
            gap = KnowledgeGap(
                description=f"Gap por {strategy['strategy']}: {strategy['reason']}",
                related_questions=[state.query],
                priority=0.7,
            )
            state.gaps[gap.gap_id] = gap

        # Re-evaluar hipótesis contra nueva evidencia
        chunk_map = {c.chunk_id: c for c in state.all_chunks.values()}
        for hyp in state.active_hypotheses:
            supporting = [
                chunk_map[cid] for cid in hyp.supporting_chunks
                if cid in chunk_map
            ]
            if supporting:
                avg_support = sum(c.score for c in supporting) / len(supporting)
                hyp.evidence_strength = avg_support
                hyp.coherence_score = avg_support * 0.85
            else:
                hyp.evidence_strength = 0.0
                hyp.coherence_score = 0.0
                if hyp.confidence > 0.5:
                    hyp.confidence *= 0.7  # Penalizar sin soporte

        return state

    # ═══════════════════════════════════════════════════════════════════════
    # FASE 3: SYNTHESIZE
    # ═══════════════════════════════════════════════════════════════════════

    def _synthesize(self, state: ReasoningState) -> ReasoningState:
        """
        Integra hipótesis, resuelve conflictos, construye respuesta.
        """
        active = state.active_hypotheses
        if not active:
            return state

        # Detectar contradicciones entre chunks
        contradictions = self.retrieval_evaluator.detect_contradictions(
            list(state.all_chunks.values())
        )

        # Resolver conflictos entre hipótesis
        if len(active) >= 2:
            active_sorted = sorted(active, key=lambda h: h.confidence, reverse=True)

            for i, h1 in enumerate(active_sorted):
                for h2 in active_sorted[i + 1:]:
                    if h1.status != HypothesisStatus.ACTIVE:
                        continue
                    if h2.status != HypothesisStatus.ACTIVE:
                        continue

                    # Verificar si comparten chunks (complementarias)
                    shared = set(h1.supporting_chunks) & set(h2.supporting_chunks)

                    if shared and h1.confidence > h2.confidence * 1.5:
                        # h1 es mucho más fuerte, h2 puede ser redundante
                        h2.status = HypothesisStatus.MERGED
                        h2.refuted_by = f"merged_into_{h1.hypothesis_id}"

        # Construir respuesta integrada
        active = state.active_hypotheses  # Refresh
        if active:
            best = max(active, key=lambda h: h.confidence)
            parts = [best.statement]

            for h in sorted(active, key=lambda h: h.confidence, reverse=True):
                if h.hypothesis_id != best.hypothesis_id and h.confidence >= 0.5:
                    parts.append(h.statement)

            state.final_answer = " | ".join(parts[:3])
            state.final_confidence = best.confidence

            # Construir citations
            state.citations = []
            for h in active:
                for cid in h.supporting_chunks:
                    if cid in state.all_chunks:
                        chunk = state.all_chunks[cid]
                        state.citations.append({
                            "chunk_id": cid,
                            "source": chunk.source,
                            "score": round(chunk.score, 4),
                            "hypothesis": h.hypothesis_id,
                        })

        return state

    # ═══════════════════════════════════════════════════════════════════════
    # RESULTADO
    # ═══════════════════════════════════════════════════════════════════════

    def _build_result(self, state: ReasoningState) -> ReasoningResult:
        """Construye el resultado final del razonamiento."""
        return ReasoningResult(
            query=state.query,
            domain=state.domain,
            trace_id=state.trace_id,
            answer=state.final_answer,
            confidence=state.final_confidence,
            verdict=state.verdict,
            rounds_executed=state.round_number,
            citations=state.citations,
            quality_scores=[
                it.quality.to_dict() for it in state.iterations
                if it.quality
            ],
            hypotheses=[
                h.to_dict() for h in state.hypotheses.values()
            ],
            gaps_remaining=[
                g.to_dict() for g in state.gaps.values() if not g.filled
            ],
            hallucination_reports=[
                it.hallucination_report.to_dict() for it in state.iterations
                if it.hallucination_report
            ],
            convergence_trajectory=state.confidence_trajectory,
            total_chunks_retrieved=len(state.all_chunks),
            duration_ms=state.duration_ms,
            success=state.verdict in (
                ReasoningVerdict.CONVERGED,
                ReasoningVerdict.MAX_ROUNDS,
            ),
        )

    # ═══════════════════════════════════════════════════════════════════════
    # API PÚBLICA
    # ═══════════════════════════════════════════════════════════════════════

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna historial de razonamientos."""
        return [r.to_dict() for r in self._history[-limit:]]

    def get_observability_summary(self) -> Dict[str, Any]:
        """Retorna resumen de observabilidad."""
        return self.observability.get_summary()

    def reset(self) -> None:
        """Resetea todo el estado."""
        self._history.clear()
        self.quality_evaluator.reset()
        self.hallucination_detector.reset()
        self.query_refiner.reset()
        self.convergence_monitor.reset()
        self.observability.reset()


# ─── DEMO ────────────────────────────────────────────────────────────────────

def demo() -> None:
    """Demostración del motor de razonamiento autorreflexivo."""
    print("=" * 80)
    print("UC-325 — Motor de Bucles de Razonamiento Autorreflexivos")
    print("=" * 80)

    engine = ReasoningLoopEngine(
        config=ReasoningConfig(max_rounds=3),
    )

    queries = [
        "¿Cómo mejoran los bucles de razonamiento la precisión en la recuperación de información por parte de los agentes?",
        "¿Qué problema tiene la arquitectura actual del cerebro AGI UC-315?",
    ]

    for query in queries:
        print(f"\n{'─' * 80}")
        print(f"Query: {query}")
        print(f"{'─' * 80}")

        result = engine.reason(query, domain="agi")

        print(f"\n  Verdict:    {result.verdict.value}")
        print(f"  Confidence: {result.confidence:.3f}")
        print(f"  Rounds:     {result.rounds_executed}")
        print(f"  Chunks:     {result.total_chunks_retrieved}")
        print(f"  Hypotheses: {len(result.hypotheses)}")
        print(f"  Duration:   {result.duration_ms:.1f} ms")
        print(f"  Success:    {result.success}")

        if result.answer:
            print(f"\n  Answer: {result.answer[:200]}")

        if result.convergence_trajectory:
            traj = ", ".join(f"{c:.3f}" for c in result.convergence_trajectory)
            print(f"\n  Convergence: [{traj}]")

        if result.quality_scores:
            last_q = result.quality_scores[-1]
            print(f"\n  Quality (last round):")
            print(f"    Relevance:   {last_q['relevance']:.3f}")
            print(f"    Coverage:    {last_q['coverage']:.3f}")
            print(f"    Consistency: {last_q['consistency']:.3f}")
            print(f"    Confidence:  {last_q['confidence']:.3f}")
            print(f"    Novelty:     {last_q['novelty']:.3f}")
            print(f"    Overall:     {last_q['overall']:.3f}")
            print(f"    Passed:      {last_q['passed']}")

    # Resumen de observabilidad
    summary = engine.get_observability_summary()
    print(f"\n{'─' * 80}")
    print("Observability Summary:")
    print(f"  Total logs:  {summary['total_logs']}")
    print(f"  Total spans: {summary['total_spans']}")
    print(f"  Counters:    {summary['counters']}")
    print("=" * 80)


if __name__ == "__main__":
    demo()
