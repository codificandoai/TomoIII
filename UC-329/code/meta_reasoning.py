"""
UC-329 — Meta Reasoning para GraphRAG-GoT.

Modela el propio proceso de razonamiento de UC-329: qué caminos se
exploraron, por qué se descartaron, qué incertidumbres persisten y qué
acciones recomienda al AGI.
"""

from typing import Dict, List, Any, Optional
import time

from graph_models import ReasoningPath, ThoughtNode, ThoughtEdge


class MetaReasoning:
    """
    Genera un informe metacognitivo del proceso de razonamiento.

    Permite al AGI (UC-315) reflexionar sobre cómo se llegó a una
    conclusión y qué perspectivas no fueron exploradas.
    """

    def __init__(self):
        self._exploration_trace: List[Dict[str, Any]] = []

    def record_exploration(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registra una acción del proceso de razonamiento."""
        self._exploration_trace.append({
            "timestamp": time.time(),
            "action": action,
            "details": details or {},
        })

    def generate_report(
        self,
        query: str,
        paths: List[ReasoningPath],
        thoughts: Dict[str, ThoughtNode],
        contradictions: List[Dict[str, Any]],
        metrics: Any,
    ) -> Dict[str, Any]:
        """Genera informe metacognitivo."""
        reasoning_types = {}
        for p in paths:
            rt = p.reasoning_type.value
            reasoning_types[rt] = reasoning_types.get(rt, 0) + 1

        uncovered = self._identify_uncovered_dimensions(paths, thoughts)

        return {
            "query": query,
            "exploration_steps": len(self._exploration_trace),
            "paths_explored": len(paths),
            "reasoning_types_used": reasoning_types,
            "contradictions_found": len(contradictions),
            "uncovered_dimensions": uncovered,
            "recommendations": self._generate_recommendations(paths, metrics, contradictions),
            "trace": self._exploration_trace[-20:],
        }

    def _identify_uncovered_dimensions(
        self,
        paths: List[ReasoningPath],
        thoughts: Dict[str, ThoughtNode],
    ) -> List[str]:
        """Identifica dimensiones posiblemente no exploradas."""
        uncovered = []
        type_counts = {}
        for p in paths:
            rt = p.reasoning_type.value
            type_counts[rt] = type_counts.get(rt, 0) + 1

        expected = ["causal", "comparative", "hierarchical", "temporal", "associative"]
        for dim in expected:
            if type_counts.get(dim, 0) == 0:
                uncovered.append(dim)
        return uncovered

    def _generate_recommendations(
        self,
        paths: List[ReasoningPath],
        metrics: Any,
        contradictions: List[Dict[str, Any]],
    ) -> List[str]:
        """Genera recomendaciones para el AGI."""
        recs = []
        if len(paths) < 3:
            recs.append("Explorar más caminos de razonamiento para diversidad.")
        if metrics and getattr(metrics, "consistency", 1.0) < 0.8:
            recs.append("Resolver contradicciones antes de decidir.")
        if contradictions:
            recs.append("Solicitar evidencia adicional para aristas conflictivas.")
        if metrics and getattr(metrics, "diversity", 0.0) < 0.5:
            recs.append("Ampliar búsqueda para incluir perspectivas alternativas.")
        return recs

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_trace_events": len(self._exploration_trace),
        }

    def reset(self) -> None:
        self._exploration_trace.clear()
