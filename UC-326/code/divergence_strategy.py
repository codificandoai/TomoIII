"""
UC-326 — Estrategias de Divergencia Forzada para MAQRI.

Cuando una consulta es demasiado similar a consultas recientes (mínimo local
de búsqueda), MAQRI aplica estrategias de divergencia para salir del bucle.

Técnicas:
1. Sinónimos y reemplazos conceptuales.
2. Cambio de alcance (ampliar/restringir).
3. Cambio de perspectiva (cómo, por qué, ejemplos).
4. Inversión de la pregunta.
5. Adición de contexto técnico o dominio.
"""

from typing import List, Dict

from maqri_models import QueryStrategy


class DivergenceStrategy:
    """
    Aplica estrategias de divergencia a queries para evitar redundancia
    y mínimos locales.
    """

    def __init__(self):
        self._synonyms: Dict[str, List[str]] = {
            "pricing": ["cost optimization", "monetization", "fare strategy", "tariff design"],
            "api": ["endpoints", "integration interface", "REST service", "webhooks"],
            "strategies": ["tactics", "approaches", "methods", "frameworks"],
            "digital twin": ["simulation model", "virtual replica", "mirror system"],
            "integrate": ["connect", "embed", "interface with", "plug into"],
            "predict": ["forecast", "estimate", "project", "anticipate"],
            "optimize": ["improve", "enhance", "tune", "refine"],
            "search": ["retrieve", "find", "lookup", "explore"],
            "memory": ["recall", "storage", "experience log", "knowledge base"],
            "agent": ["system", "assistant", "autonomous program", "bot"],
        }

        self._perspectives = [
            "how does {query} work",
            "why is {query} important",
            "examples of {query}",
            "common problems with {query}",
            "benefits of {query}",
            "architecture of {query}",
        ]

    def diverge(
        self,
        query: str,
        failed_approaches: List[str],
        strategy: QueryStrategy = QueryStrategy.DIVERGE,
    ) -> str:
        """
        Aplica una estrategia de divergencia a la query.

        Retorna una query modificada.
        """
        if strategy == QueryStrategy.EXPAND:
            return self._expand(query)
        elif strategy == QueryStrategy.SPECIALIZE:
            return self._specialize(query, failed_approaches)
        elif strategy == QueryStrategy.CONTEXTUALIZE:
            return self._contextualize(query)
        elif strategy == QueryStrategy.ABSTRACT:
            return self._abstract(query)
        else:
            return self._default_diverge(query)

    def _default_diverge(self, query: str) -> str:
        """Divergencia por defecto: sinónimos + perspectiva alternativa."""
        modified = self._apply_synonyms(query)
        if modified == query:
            modified = self._change_perspective(query)
        if modified == query:
            modified = query + " alternative perspective"
        return modified

    def _expand(self, query: str) -> str:
        """Amplía el alcance de la query."""
        expansions = [
            f"overview of {query}",
            f"{query} and related concepts",
            f"broader context of {query}",
        ]
        return self._pick_different(query, expansions)

    def _specialize(self, query: str, failed_approaches: List[str]) -> str:
        """Especializa la query, evitando enfoques fallidos."""
        base = query
        if failed_approaches:
            # Añadir información faltante del último fallo
            last_failure = failed_approaches[-1]
            if "broad" in last_failure.lower():
                base += " detailed technical implementation"
            elif "specific" in last_failure.lower():
                base += " general principles"
            else:
                base += " concrete examples"
        else:
            base += " specific implementation details"
        return base

    def _contextualize(self, query: str) -> str:
        """Añade contexto de dominio o caso de uso."""
        contexts = [
            "in production systems",
            "for enterprise applications",
            "in real-time scenarios",
            "with practical examples",
        ]
        return f"{query} {contexts[0]}"

    def _abstract(self, query: str) -> str:
        """Abstrae la query a conceptos más generales."""
        words = query.split()
        if len(words) <= 3:
            return f"general principles behind {query}"
        # Tomar solo palabras clave (simplificación)
        key_words = [w for w in words if len(w) > 4][:3]
        return f"fundamentals of {' '.join(key_words)}"

    def _apply_synonyms(self, query: str) -> str:
        """Reemplaza palabras por sinónimos."""
        modified = query.lower()
        for word, synonyms in self._synonyms.items():
            if word in modified:
                # Usar el primer sinónimo que no esté ya en la query
                for synonym in synonyms:
                    if synonym not in modified:
                        modified = modified.replace(word, synonym, 1)
                        break
                break
        return modified

    def _change_perspective(self, query: str) -> str:
        """Cambia la perspectiva de la pregunta."""
        for perspective in self._perspectives:
            candidate = perspective.format(query=query)
            if candidate != query:
                return candidate
        return query

    def _pick_different(self, query: str, candidates: List[str]) -> str:
        """Elige una variante diferente a la query original."""
        query_norm = " ".join(query.lower().split())
        for candidate in candidates:
            if " ".join(candidate.lower().split()) != query_norm:
                return candidate
        return candidates[0] if candidates else query

    def generate_divergent_variants(
        self,
        query: str,
        n: int = 3,
    ) -> List[str]:
        """Genera múltiples variantes divergentes de una query."""
        strategies = [
            QueryStrategy.EXPAND,
            QueryStrategy.SPECIALIZE,
            QueryStrategy.CONTEXTUALIZE,
            QueryStrategy.ABSTRACT,
            QueryStrategy.DIVERGE,
        ]

        variants = []
        seen = {" ".join(query.lower().split())}
        for strategy in strategies[:n]:
            variant = self.diverge(query, [], strategy=strategy)
            normalized = " ".join(variant.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                variants.append(variant)

        return variants[:n]
