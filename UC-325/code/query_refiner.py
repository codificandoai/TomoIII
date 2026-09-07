"""
UC-325 — Refinador de Queries para el Motor de Razonamiento Autorreflexivo.

Genera variantes semánticas del query original, queries específicas para
gaps de conocimiento, y queries de verificación para hipótesis débiles.

Reemplaza las queries estáticas hardcodeadas de brain_memory_pipeline._retrieve_relevant_memories().
"""

from typing import List, Dict, Optional
import hashlib
import re

from reasoning_models import (
    ReasoningState,
    KnowledgeGap,
    Hypothesis,
    QueryRefinementConfig,
    HypothesisStatus,
)


class QueryRefiner:
    """
    Refina queries de forma determinista basándose en el estado del razonamiento.

    Estrategias de refinamiento:
    1. Expansión semántica: sinónimos y paráfrasis del query original.
    2. Especialización: queries más específicas por dominio o aspecto.
    3. Gap-targeting: queries diseñadas para llenar gaps identificados.
    4. Verification: queries para verificar hipótesis débiles.
    5. Generalization: queries más amplias cuando las específicas fallan.
    """

    def __init__(self, config: Optional[QueryRefinementConfig] = None):
        self.config = config or QueryRefinementConfig()
        self._generated_queries: List[str] = []

    def expand_initial(self, query: str, domain: str = "general") -> List[str]:
        """
        Genera expansiones iniciales del query original (Fase DISCOVER).

        Produce hasta max_expansions variantes:
        - Query original (siempre incluido).
        - Variantes con sinónimos y reestructuración.
        - Variantes especializadas por dominio.
        - Variantes de causa/efecto/ejemplo.
        """
        expansions = [query]

        # Variante: como pregunta directa
        if not query.strip().endswith("?"):
            expansions.append(f"¿{query.strip()}?")

        # Variante: pedir ejemplos concretos
        expansions.append(f"ejemplos concretos de {query}")

        # Variante: causas y efectos
        expansions.append(f"causas y consecuencias de {query}")

        # Variante: definición técnica
        expansions.append(f"definición técnica de {query}")

        # Variante: por dominio
        if domain != "general":
            expansions.append(f"{query} en el contexto de {domain}")

        # Variante: comparación
        expansions.append(f"ventajas y desventajas de {query}")

        # Deduplicar y limitar
        seen = set()
        unique = []
        for q in expansions:
            normalized = " ".join(q.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(q)

        result = unique[: self.config.max_expansions]
        self._generated_queries.extend(result)
        return result

    def refine_for_gaps(
        self,
        state: ReasoningState,
        gaps: List[KnowledgeGap],
    ) -> List[str]:
        """
        Genera queries específicas para llenar gaps de conocimiento (Fase REFINE).

        Para cada gap no llenado, genera un query preciso basado en:
        - La descripción del gap.
        - Las sub-preguntas relacionadas.
        - El contexto del query original.
        """
        refined = []

        for gap in gaps:
            if gap.filled or gap.attempts_made >= gap.max_attempts:
                continue

            # Query directo del gap
            refined.append(gap.description)

            # Queries de sub-preguntas
            for subq in gap.related_questions[:2]:
                refined.append(subq)

            # Query contextualizado
            if state.query:
                refined.append(
                    f"{gap.description} en relación con {state.query}"
                )

        # Deduplicar
        seen = set()
        unique = []
        for q in refined:
            normalized = " ".join(q.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(q)

        result = unique[: self.config.max_expansions * 2]
        self._generated_queries.extend(result)
        return result

    def refine_for_verification(
        self,
        hypotheses: List[Hypothesis],
        query: str,
    ) -> List[str]:
        """
        Genera queries para verificar hipótesis débiles (Fase REFINE).

        Para hipótesis con confianza entre 0.3 y 0.7, genera queries
        que buscan evidencia confirmatoria o contradictoria.
        """
        verification_queries = []

        for hyp in hypotheses:
            if hyp.status != HypothesisStatus.ACTIVE:
                continue
            if not (0.3 <= hyp.confidence <= 0.7):
                continue

            # Buscar evidencia a favor
            verification_queries.append(
                f"evidencia que soporte: {hyp.statement[:100]}"
            )

            # Buscar contra-evidencia
            verification_queries.append(
                f"argumentos en contra de: {hyp.statement[:100]}"
            )

        result = verification_queries[: self.config.max_expansions]
        self._generated_queries.extend(result)
        return result

    def generalize(self, query: str, failed_specifics: List[str]) -> List[str]:
        """
        Genera queries más amplias cuando las queries específicas no dan resultados.

        Elimina calificadores, generaliza términos, y amplía el scope.
        """
        generalized = []

        # Extraer palabras clave principales (más de 4 caracteres)
        words = [w for w in query.split() if len(w) > 4]
        if len(words) >= 2:
            # Query con solo las dos palabras clave más largas
            key_words = sorted(words, key=len, reverse=True)[:2]
            generalized.append(" ".join(key_words))

        # Eliminar calificadores de dominio
        domain_qualifiers = [
            "específicamente", "en el contexto de", "para el caso de",
            "en particular", "concretamente", "specifically",
            "in the context of", "for the case of",
        ]
        stripped = query
        for qual in domain_qualifiers:
            stripped = stripped.replace(qual, "").strip()
        if stripped != query:
            generalized.append(stripped)

        # Query simplificado
        simple_words = [w for w in query.split() if len(w) > 3][:5]
        if simple_words:
            generalized.append(" ".join(simple_words))

        result = generalized[: self.config.max_expansions]
        self._generated_queries.extend(result)
        return result

    def get_all_generated(self) -> List[str]:
        """Retorna todas las queries generadas."""
        return list(self._generated_queries)

    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de refinamiento."""
        return {
            "total_queries_generated": len(self._generated_queries),
            "unique_queries": len(set(
                " ".join(q.lower().split()) for q in self._generated_queries
            )),
        }

    def reset(self) -> None:
        """Resetea estado interno."""
        self._generated_queries.clear()
