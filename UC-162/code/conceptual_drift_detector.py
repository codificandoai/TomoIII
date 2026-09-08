"""
UC-162 — Detector de drift conceptual.

UC-087 detecta drift estadístico (la distribución cambia). UC-162 detecta
drift conceptual: el significado de un feature cambia aunque su
distribución no.

Tipos de drift conceptual:
- SEMANTIC: el concepto que representa un feature cambia.
- CONTEXTUAL: el contexto en que se usa un feature cambia.
- TEMPORAL: el significado evoluciona con el tiempo.
- COMBINED: combinación de los anteriores.

Ejemplo: "spread" en trading puede significar:
- Bid-ask spread (mercado normal).
- Credit spread (bonos).
- Spread de volatilidad (opciones).
Si el corpus cambia de dominio, el significado de "spread" cambia sin
que la distribución de la palabra cambie.
"""

import math
import time
from collections import Counter
from typing import Dict, List, Optional, Any, Tuple

from models_162 import DriftReport, DriftType, LLMOpsConfig


class ConceptualDriftDetector:
    """Detecta drift conceptual entre un baseline y el estado actual."""

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.config = config or LLMOpsConfig()
        self.baselines: Dict[str, Dict[str, Any]] = {}

    def set_baseline(
        self,
        concept_name: str,
        contexts: List[str],
        co_occurrences: List[List[str]] = None,
    ):
        """Establece un baseline conceptual."""
        self.baselines[concept_name] = {
            "context_distribution": self._context_distribution(contexts),
            "co_occurrence_distribution": self._co_occurrence_distribution(
                co_occurrences or []
            ),
            "sample_count": len(contexts),
            "set_at": time.time(),
        }

    def detect(
        self,
        concept_name: str,
        current_contexts: List[str],
        current_co_occurrences: List[List[str]] = None,
        trace_id: str = "",
    ) -> DriftReport:
        """Detecta drift conceptual para un concepto."""
        report = DriftReport(trace_id=trace_id)
        report.baseline_concept = concept_name

        baseline = self.baselines.get(concept_name)
        if not baseline:
            report.drift_type = DriftType.NONE.value
            report.is_drift = False
            report.details = {"error": "no baseline set for concept"}
            return report

        current_context_dist = self._context_distribution(current_contexts)
        current_co_dist = self._co_occurrence_distribution(
            current_co_occurrences or []
        )

        # Distancia entre distribuciones (Jensen-Shannon)
        context_drift = self._js_distance(
            baseline["context_distribution"], current_context_dist
        )
        co_drift = self._js_distance(
            baseline["co_occurrence_distribution"], current_co_dist
        )

        report.drift_score = round(max(context_drift, co_drift), 4)
        report.threshold = self.config.drift_semantic_threshold
        report.is_drift = report.drift_score > report.threshold
        report.current_concept = f"{concept_name}_current"

        # Determinar tipo de drift
        if report.is_drift:
            if context_drift > co_drift:
                report.drift_type = DriftType.SEMANTIC.value
                report.affected_features = list(current_context_dist.keys())
            elif co_drift > context_drift:
                report.drift_type = DriftType.CONTEXTUAL.value
                report.affected_features = list(current_co_dist.keys())
            else:
                report.drift_type = DriftType.COMBINED.value
                report.affected_features = (
                    list(current_context_dist.keys())
                    + list(current_co_dist.keys())
                )
        else:
            report.drift_type = DriftType.NONE.value

        report.details = {
            "context_drift": round(context_drift, 4),
            "co_occurrence_drift": round(co_drift, 4),
            "baseline_sample_count": baseline["sample_count"],
            "current_sample_count": len(current_contexts),
            "baseline_context_distribution": baseline["context_distribution"],
            "current_context_distribution": current_context_dist,
        }

        return report

    def _context_distribution(
        self, contexts: List[str]
    ) -> Dict[str, float]:
        """Calcula la distribución de contextos para un concepto."""
        if not contexts:
            return {}
        counter = Counter(contexts)
        total = len(contexts)
        return {k: v / total for k, v in counter.items()}

    def _co_occurrence_distribution(
        self, co_occurrences: List[List[str]]
    ) -> Dict[str, float]:
        """Calcula la distribución de co-ocurrencias."""
        if not co_occurrences:
            return {}
        all_terms = []
        for terms in co_occurrences:
            all_terms.extend(terms)
        if not all_terms:
            return {}
        counter = Counter(all_terms)
        total = len(all_terms)
        return {k: v / total for k, v in counter.items()}

    def _js_distance(
        self,
        dist_a: Dict[str, float],
        dist_b: Dict[str, float],
    ) -> float:
        """
        Distancia de Jensen-Shannon entre dos distribuciones.
        0 = idénticas, 1 = completamente diferentes.
        """
        all_keys = set(dist_a.keys()) | set(dist_b.keys())
        if not all_keys:
            return 0.0
        # Alinear distribuciones
        p = []
        q = []
        for k in all_keys:
            p.append(dist_a.get(k, 0.0))
            q.append(dist_b.get(k, 0.0))
        # Normalizar
        sum_p = sum(p)
        sum_q = sum(q)
        if sum_p == 0 or sum_q == 0:
            return 1.0
        p = [x / sum_p for x in p]
        q = [x / sum_q for x in q]
        # JS divergence = (KL(P||M) + KL(Q||M)) / 2
        m = [(pi + qi) / 2 for pi, qi in zip(p, q)]
        kl_pm = self._kl_divergence(p, m)
        kl_qm = self._kl_divergence(q, m)
        js_div = (kl_pm + kl_qm) / 2
        # JS distance = sqrt(JS divergence)
        return math.sqrt(max(0.0, min(1.0, js_div)))

    @staticmethod
    def _kl_divergence(p: List[float], q: List[float]) -> float:
        """KL divergence D(P||Q)."""
        div = 0.0
        for pi, qi in zip(p, q):
            if pi > 0 and qi > 0:
                div += pi * math.log2(pi / qi)
        return div
