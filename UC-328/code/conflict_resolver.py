"""
UC-328 — Resolutor de Conflictos para ORQUESTA-R.

Resuelve ambigüedades y contradicciones entre resultados parciales de
múltiples fuentes, usando votación ponderada, actualidad, especificidad y
consistencia con el contexto global.
"""

from typing import List, Dict, Any, Optional
import statistics

from orquesta_models import PartialResult, ResolvedFact


class ConflictResolver:
    """
    Resuelve conflictos entre resultados parciales.

    Estrategias:
    - Votación ponderada por confianza de fuente.
    - Decaimiento temporal (más peso a valores recientes).
    - Especificidad (más detalle = más peso).
    - Detección de contradicciones fuertes.
    """

    def __init__(self, variance_threshold: float = 0.3, decay_minutes: float = 60.0):
        self.variance_threshold = variance_threshold
        self.decay_minutes = decay_minutes

    def resolve(
        self,
        key: str,
        partials: List[PartialResult],
        global_context: Optional[Dict[str, Any]] = None,
    ) -> ResolvedFact:
        """
        Resuelve un conjunto de valores parciales para una clave.

        Retorna ResolvedFact con valor, confianza, modo y advertencias.
        """
        if not partials:
            return ResolvedFact(key=key, value=None, confidence=0.0, mode="no_data")

        if len(partials) == 1:
            return ResolvedFact(
                key=key,
                value=partials[0].data,
                confidence=partials[0].confidence,
                mode="single_source",
                sources=[partials[0].source_id],
            )

        # Separate numeric vs categorical
        numeric_values = []
        categorical_values = []

        for p in partials:
            try:
                numeric_values.append((float(p.data), p))
            except (ValueError, TypeError):
                categorical_values.append((str(p.data), p))

        if numeric_values:
            return self._resolve_numeric(key, numeric_values, global_context)

        return self._resolve_categorical(key, categorical_values, global_context)

    def _resolve_numeric(
        self,
        key: str,
        values: List[tuple],
        global_context: Optional[Dict[str, Any]],
    ) -> ResolvedFact:
        """Resuelve valores numéricos por media ponderada."""
        weights = []
        weighted_sum = 0.0
        total_weight = 0.0
        sources = []
        warnings = []

        raw_vals = [v for v, _ in values]
        for value, partial in values:
            weight = partial.confidence * self._time_decay(partial)
            weighted_sum += value * weight
            total_weight += weight
            weights.append(weight)
            sources.append(partial.source_id)

        if total_weight == 0:
            return ResolvedFact(key=key, value=0.0, confidence=0.0, mode="no_weight", sources=sources)

        resolved_value = weighted_sum / total_weight
        variance = statistics.variance(raw_vals) if len(raw_vals) > 1 else 0.0

        if variance > self.variance_threshold:
            confidence = 0.5
            mode = "promediado_con_advertencia"
            warnings.append(f"Alta varianza entre fuentes: {variance:.3f}")
        else:
            confidence = 1.0 - min(1.0, variance)
            mode = "consistente"

        # Check consistency with global context
        if global_context and key in global_context:
            try:
                context_val = float(global_context[key])
                if abs(resolved_value - context_val) / max(abs(context_val), 1e-6) > 0.3:
                    confidence *= 0.7
                    mode = "en_revision"
                    warnings.append("Contradice contexto global persistente")
            except (ValueError, TypeError):
                pass

        return ResolvedFact(
            key=key,
            value=round(resolved_value, 6),
            confidence=round(confidence, 4),
            mode=mode,
            sources=list(set(sources)),
            warnings=warnings,
        )

    def _resolve_categorical(
        self,
        key: str,
        values: List[tuple],
        global_context: Optional[Dict[str, Any]],
    ) -> ResolvedFact:
        """Resuelve valores categóricos por moda ponderada."""
        from collections import defaultdict

        scores: Dict[str, float] = defaultdict(float)
        source_map: Dict[str, List[str]] = defaultdict(list)
        sources = []
        warnings = []

        for value, partial in values:
            weight = partial.confidence * self._time_decay(partial)
            scores[value] += weight
            source_map[value].append(partial.source_id)
            sources.append(partial.source_id)

        if not scores:
            return ResolvedFact(key=key, value=None, confidence=0.0, mode="no_weight", sources=sources)

        best_value = max(scores, key=scores.get)
        total_weight = sum(scores.values())
        best_score = scores[best_value]
        confidence = best_score / total_weight

        # Detect contradiction: runner-up has significant weight
        runner_up = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(runner_up) > 1 and runner_up[1][1] / total_weight > 0.3:
            mode = "ambiguo"
            warnings.append(f"Múltiples valores competitivos: {runner_up[:2]}")
        else:
            mode = "consistente"

        return ResolvedFact(
            key=key,
            value=best_value,
            confidence=round(confidence, 4),
            mode=mode,
            sources=list(set(source_map[best_value])),
            warnings=warnings,
        )

    def _time_decay(self, partial: PartialResult) -> float:
        """Calcula decaimiento temporal en minutos."""
        import time
        age_minutes = (time.time() - partial.timestamp) / 60.0
        return 0.9 ** (age_minutes / max(1.0, self.decay_minutes))

    def detect_contradictions(self, partials: List[PartialResult]) -> List[Dict[str, Any]]:
        """Detecta y reporta contradicciones entre resultados parciales."""
        contradictions = []
        if len(partials) < 2:
            return contradictions

        numeric = []
        for p in partials:
            try:
                numeric.append((float(p.data), p.source_id, p.confidence))
            except (ValueError, TypeError):
                pass

        if len(numeric) >= 2:
            vals = [v for v, _, _ in numeric]
            variance = statistics.variance(vals) if len(vals) > 1 else 0.0
            if variance > self.variance_threshold:
                contradictions.append({
                    "type": "numeric_variance",
                    "variance": round(variance, 4),
                    "values": numeric,
                })

        return contradictions
