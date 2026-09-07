"""
UC-326 — Refinador de Queries Aumentado por Memoria para MAQRI.

Refina consultas usando:
1. Memoria episódica (experiencias pasadas similares).
2. Memoria procedimental (reglas heurísticas).
3. Divergencia forzada (evitar mínimos locales).
4. Aprendizaje de patrones de reescritura exitosos.
"""

from typing import List, Dict, Optional

from maqri_models import QueryVariant, QueryStrategy, MaqriConfig, CriticAssessment
from episodic_memory import EpisodicMemory
from procedural_memory import ProceduralMemory
from divergence_strategy import DivergenceStrategy


class QueryRefiner326:
    """
    Refinador de queries con memoria episódica y procedimental.

    A diferencia de un refiner simple, MAQRI aprende de búsquedas pasadas,
    detecta redundancia, y fuerza divergencia para evitar ciclos.
    """

    def __init__(
        self,
        config: Optional[MaqriConfig] = None,
        episodic: Optional[EpisodicMemory] = None,
        procedural: Optional[ProceduralMemory] = None,
    ):
        self.config = config or MaqriConfig()
        self.episodic = episodic or EpisodicMemory()
        self.procedural = procedural or ProceduralMemory()
        self.divergence = DivergenceStrategy()
        self._rewrite_history: List[Dict[str, str]] = []

    def generate_variants(
        self,
        query: str,
        context: str = "",
        failed_approaches: Optional[List[str]] = None,
        assessment: Optional[CriticAssessment] = None,
    ) -> List[QueryVariant]:
        """
        Genera variantes refinadas de una query, guiadas por la memoria.

        Considera:
        - Episodios similares anteriores.
        - Reglas procedimentales activas.
        - Divergencia si es redundante.
        - Crítica del estado actual.
        """
        failed = failed_approaches or []
        variants = []

        # 1. Variante original (siempre)
        variants.append(QueryVariant(
            query=query,
            strategy=QueryStrategy.EXPAND,
            source_query=query,
            expected_focus="original",
            estimated_quality=0.5,
        ))

        # 2. Aprender de episodios similares exitosos
        similar = self.episodic.find_similar(query, top_k=2, threshold=0.5)
        for ep in similar:
            if ep.success and ep.refined_query != query:
                variants.append(QueryVariant(
                    query=ep.refined_query,
                    strategy=QueryStrategy.CONTEXTUALIZE,
                    source_query=query,
                    expected_focus="proven_past_query",
                    estimated_quality=ep.relevance_score,
                ))

        # 3. Aplicar reglas procedimentales
        active_strategies = self.procedural.get_recommended_strategies(
            num_results=0,  # actualizamos después de retrieval
            avg_relevance=assessment.relevance_score if assessment else 0.5,
            redundancy_ratio=0.0,
            query_too_broad=self._is_too_broad(query),
            query_too_specific=self._is_too_specific(query),
            domain_context_missing=not bool(context),
        )

        for strategy in active_strategies[:2]:
            variant = self._apply_strategy(query, strategy, failed)
            if variant:
                variants.append(variant)

        # 4. Divergencia forzada si es redundante
        if self.config.enable_divergence and self.episodic.is_redundant(
            query, window=self.config.similarity_window, threshold=self.config.redundancy_threshold
        ):
            diverged = self.divergence.generate_divergent_variants(query, n=2)
            for dv in diverged:
                variants.append(QueryVariant(
                    query=dv,
                    strategy=QueryStrategy.DIVERGE,
                    source_query=query,
                    expected_focus="divergence",
                    estimated_quality=0.4,
                ))

        # 5. Variantes estándar de expansión
        expansions = self._standard_expansions(query, context)
        for exp in expansions:
            variants.append(QueryVariant(
                query=exp,
                strategy=QueryStrategy.EXPAND,
                source_query=query,
                expected_focus="expanded_scope",
                estimated_quality=0.5,
            ))

        # Deduplicar y limitar
        unique = []
        seen = set()
        for v in variants:
            normalized = " ".join(v.query.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(v)

        # Ordenar por estimated_quality descendente
        unique.sort(key=lambda x: x.estimated_quality, reverse=True)
        return unique[: self.config.max_variants]

    def refine_from_failure(
        self,
        query: str,
        missing_info: str,
        failure_reason: str,
        accumulated_facts: List[str],
    ) -> QueryVariant:
        """
        Refina la query usando la crítica del Critic.

        Combina: objetivo original + información faltante + hechos acumulados
        + lecciones episódicas.
        """
        lessons = self.episodic.get_lessons_learned(n=3)

        # Construir query refinada
        parts = [query]
        if missing_info and missing_info not in query:
            parts.append(f"focusing on {missing_info}")
        if accumulated_facts:
            # Incluir un hecho clave (el más reciente y relevante)
            best_fact = accumulated_facts[-1]
            if len(best_fact.split()) <= 15:
                parts.append(f"in context of {best_fact}")

        refined = " ".join(parts)

        # Si el fracaso fue "too broad", especializar
        if "broad" in failure_reason.lower() or "missed" in failure_reason.lower():
            strategy = QueryStrategy.SPECIALIZE
            refined = f"{query} specific implementation details for {missing_info}"
        # Si el fracaso fue "too specific", abstraer
        elif "specific" in failure_reason.lower():
            strategy = QueryStrategy.ABSTRACT
            words = [w for w in query.split() if len(w) > 4][:3]
            refined = f"general principles of {' '.join(words)}"
        else:
            strategy = QueryStrategy.CONTEXTUALIZE

        self._rewrite_history.append({
            "from": query,
            "to": refined,
            "reason": failure_reason,
        })

        return QueryVariant(
            query=refined,
            strategy=strategy,
            source_query=query,
            expected_focus=missing_info or "failure_recovery",
            estimated_quality=0.6,
        )

    def _apply_strategy(
        self,
        query: str,
        strategy: QueryStrategy,
        failed_approaches: List[str],
    ) -> Optional[QueryVariant]:
        """Aplica una estrategia y retorna una QueryVariant."""
        if strategy == QueryStrategy.EXPAND:
            refined = self.divergence._expand(query)
        elif strategy == QueryStrategy.SPECIALIZE:
            refined = self.divergence._specialize(query, failed_approaches)
        elif strategy == QueryStrategy.CONTEXTUALIZE:
            refined = self.divergence._contextualize(query)
        elif strategy == QueryStrategy.ABSTRACT:
            refined = self.divergence._abstract(query)
        elif strategy == QueryStrategy.DIVERGE:
            variants = self.divergence.generate_divergent_variants(query, n=1)
            refined = variants[0] if variants else query
        else:
            return None

        return QueryVariant(
            query=refined,
            strategy=strategy,
            source_query=query,
            expected_focus=strategy.value,
            estimated_quality=0.5,
        )

    def _standard_expansions(self, query: str, context: str) -> List[str]:
        """Expansiones estándar de queries."""
        expansions = []
        if context:
            expansions.append(f"{query} in context of {context}")
        expansions.append(f"how does {query} work")
        expansions.append(f"examples of {query}")
        expansions.append(f"{query} best practices")
        return expansions[:3]

    def _is_too_broad(self, query: str) -> bool:
        """Heurística: queries cortas con palabras genéricas son muy amplias."""
        words = query.split()
        if len(words) <= 2:
            return True
        generic = {"what", "how", "why", "explain", "describe", "about"}
        return sum(1 for w in words if w.lower() in generic) >= 2

    def _is_too_specific(self, query: str) -> bool:
        """Heurística: queries con muchos términos propios son muy específicas."""
        words = query.split()
        return len(words) >= 12

    def get_rewrite_history(self) -> List[Dict[str, str]]:
        """Retorna historial de reescrituras."""
        return list(self._rewrite_history)

    def learn_successful_rewrite(
        self,
        original: str,
        refined: str,
        score: float,
    ) -> None:
        """Registra un patrón de reescritura exitoso."""
        self._rewrite_history.append({
            "from": original,
            "to": refined,
            "score": f"{score:.3f}",
            "type": "learned_success",
        })

    def reset(self) -> None:
        """Limpia historial de reescrituras."""
        self._rewrite_history.clear()
