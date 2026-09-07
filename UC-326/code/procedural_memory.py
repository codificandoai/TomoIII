"""
UC-326 — Memoria Procedimental para MAQRI.

Reglas heurísticas sobre CÓMO buscar. Aprende qué estrategias de
refinamiento funcionan mejor en cada contexto.

Ejemplos:
- Si una consulta devuelve menos de 3 documentos relevantes, cambiar a
  términos más amplios.
- Si hay alta redundancia, especializar la consulta.
- Si el score es bajo, divergir con sinónimos.
"""

from typing import List, Dict, Optional, Any

from maqri_models import ProceduralRule, QueryStrategy


class ProceduralMemory:
    """
    Memoria procedimental: reglas heurísticas de búsqueda.

    Cada regla tiene una condición, una acción, prioridad y estadísticas
    de éxito. El motor puede aprender actualizando hits/successes.
    """

    def __init__(self):
        self._rules: List[ProceduralRule] = []
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """Reglas por defecto del sistema."""
        defaults = [
            ProceduralRule(
                name="low_results_expand",
                condition="num_results < 3",
                action=QueryStrategy.EXPAND.value,
                priority=0.8,
            ),
            ProceduralRule(
                name="low_relevance_diverge",
                condition="avg_relevance < 0.3",
                action=QueryStrategy.DIVERGE.value,
                priority=0.9,
            ),
            ProceduralRule(
                name="high_redundancy_specialize",
                condition="redundancy_ratio > 0.6",
                action=QueryStrategy.SPECIALIZE.value,
                priority=0.7,
            ),
            ProceduralRule(
                name="broad_query_focus",
                condition="query_too_broad",
                action=QueryStrategy.SPECIALIZE.value,
                priority=0.6,
            ),
            ProceduralRule(
                name="specific_query_abstract",
                condition="query_too_specific",
                action=QueryStrategy.ABSTRACT.value,
                priority=0.6,
            ),
            ProceduralRule(
                name="add_context",
                condition="domain_context_missing",
                action=QueryStrategy.CONTEXTUALIZE.value,
                priority=0.5,
            ),
        ]
        for rule in defaults:
            self._rules.append(rule)

    def add_rule(self, rule: ProceduralRule) -> None:
        """Agrega una regla personalizada."""
        self._rules.append(rule)

    def evaluate(
        self,
        num_results: int = 0,
        avg_relevance: float = 0.0,
        redundancy_ratio: float = 0.0,
        query_too_broad: bool = False,
        query_too_specific: bool = False,
        domain_context_missing: bool = False,
    ) -> List[ProceduralRule]:
        """
        Evalúa las condiciones y retorna reglas activas ordenadas por
        prioridad.
        """
        active = []

        for rule in self._rules:
            triggered = False

            if rule.condition == "num_results < 3" and num_results < 3:
                triggered = True
            elif rule.condition == "avg_relevance < 0.3" and avg_relevance < 0.3:
                triggered = True
            elif rule.condition == "redundancy_ratio > 0.6" and redundancy_ratio > 0.6:
                triggered = True
            elif rule.condition == "query_too_broad" and query_too_broad:
                triggered = True
            elif rule.condition == "query_too_specific" and query_too_specific:
                triggered = True
            elif rule.condition == "domain_context_missing" and domain_context_missing:
                triggered = True

            if triggered:
                active.append(rule)

        active.sort(key=lambda r: r.priority, reverse=True)
        return active

    def get_recommended_strategies(
        self,
        num_results: int = 0,
        avg_relevance: float = 0.0,
        redundancy_ratio: float = 0.0,
        **kwargs: Any,
    ) -> List[QueryStrategy]:
        """Retorna estrategias recomendadas según el estado actual."""
        active = self.evaluate(
            num_results=num_results,
            avg_relevance=avg_relevance,
            redundancy_ratio=redundancy_ratio,
            **kwargs,
        )
        strategies = []
        seen = set()
        for rule in active:
            try:
                strategy = QueryStrategy(rule.action)
            except ValueError:
                continue
            if strategy not in seen:
                seen.add(strategy)
                strategies.append(strategy)
        return strategies

    def update_rule_success(self, rule_id: str, success: bool) -> None:
        """Actualiza estadísticas de una regla."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.hits += 1
                if success:
                    rule.successes += 1
                return

    def get_rules(self) -> List[Dict[str, Any]]:
        """Retorna todas las reglas como diccionarios."""
        return [r.to_dict() for r in self._rules]

    def get_best_rules(self, min_hits: int = 1) -> List[ProceduralRule]:
        """Retorna reglas con mejor tasa de éxito."""
        return sorted(
            [r for r in self._rules if r.hits >= min_hits],
            key=lambda r: r.success_rate,
            reverse=True,
        )

    def reset_statistics(self) -> None:
        """Resetea estadísticas de todas las reglas."""
        for rule in self._rules:
            rule.hits = 0
            rule.successes = 0

    def reset(self) -> None:
        """Limpia y reinicializa reglas por defecto."""
        self._rules.clear()
        self._initialize_default_rules()
