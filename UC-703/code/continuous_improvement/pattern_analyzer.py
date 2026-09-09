"""Análisis de patrones: clusteriza feedback y logs para distinguir bugs aislados de fallos sistémicos."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from continuous_improvement.models_ci import (
    ExecutionLogRef,
    FeedbackCluster,
    FeedbackItem,
    IncidentRef,
)


class PatternAnalyzer:
    """
    Agrupa feedback, logs de ejecución e incidentes por categoría/modelo/patrón
    y determina si el patrón es sistémico.
    """

    SYSTEMIC_THRESHOLD = 3

    def __init__(self, systemic_threshold: int = 3) -> None:
        self.systemic_threshold = systemic_threshold
        self._clusters: List[FeedbackCluster] = []

    def analyze(
        self,
        feedback_items: List[FeedbackItem],
        log_refs: Optional[List[ExecutionLogRef]] = None,
        incident_refs: Optional[List[IncidentRef]] = None,
    ) -> List[FeedbackCluster]:
        log_refs = log_refs or []
        incident_refs = incident_refs or []
        clusters: Dict[str, FeedbackCluster] = {}
        for item in feedback_items:
            key = f"{item.category}|{item.model_version}|{item.prompt_version_id}"
            cluster = clusters.setdefault(
                key,
                FeedbackCluster(pattern=key, dominant_category=item.category),
            )
            cluster.feedback_ids.append(item.feedback_id)
            cluster.count += 1

        # Enrich with logs and incidents
        for log in log_refs:
            if log.error_category:
                key = f"{log.error_category}|{log.tool_name}"
                cluster = clusters.setdefault(
                    key,
                    FeedbackCluster(pattern=key, dominant_category=log.error_category),
                )
                cluster.log_refs.append(log)
                cluster.count += 1

        for inc in incident_refs:
            if inc.root_cause:
                key = f"incident:{inc.root_cause}"
                cluster = clusters.setdefault(
                    key,
                    FeedbackCluster(pattern=key, dominant_category="incident"),
                )
                cluster.incident_refs.append(inc)
                if inc.recurring:
                    cluster.count += 2
                else:
                    cluster.count += 1

        # Determine systemic flag and dominant severity
        for cluster in clusters.values():
            cluster.systemic = cluster.count >= self.systemic_threshold
            severities = ["low", "medium", "high", "critical"]
            max_sev = 0
            for fid in cluster.feedback_ids:
                item = next((f for f in feedback_items if f.feedback_id == fid), None)
                if item and item.severity in severities:
                    max_sev = max(max_sev, severities.index(item.severity))
            cluster.dominant_severity = severities[max_sev]

        self._clusters = list(clusters.values())
        return self._clusters

    def top_systemic(self, n: int = 5) -> List[FeedbackCluster]:
        systemic = [c for c in self._clusters if c.systemic]
        return sorted(systemic, key=lambda c: c.count, reverse=True)[:n]
