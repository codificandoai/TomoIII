"""Trazabilidad de datasets: provenance, transformaciones, consentimiento, retención."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from compliance_as_code.models_compliance import DatasetLineage


class DataLineageTracker:
    """Registra linaje, consentimiento, transformaciones y controles de datasets."""

    def __init__(self) -> None:
        self._datasets: Dict[str, DatasetLineage] = {}

    def register(
        self,
        dataset_id: str,
        source: str,
        transformations: Optional[List[Dict[str, Any]]] = None,
        consent_tags: Optional[List[str]] = None,
        retention_hours: float = 168.0,
        purpose: str = "",
        privacy_controls: Optional[List[str]] = None,
    ) -> DatasetLineage:
        lineage = DatasetLineage(
            dataset_id=dataset_id,
            source=source,
            transformations=transformations or [],
            consent_tags=consent_tags or [],
            retention_hours=retention_hours,
            purpose=purpose,
            privacy_controls=privacy_controls or [],
        )
        self._datasets[dataset_id] = lineage
        return lineage

    def add_transformation(
        self,
        dataset_id: str,
        name: str,
        description: str,
        tool: str = "",
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[DatasetLineage]:
        lineage = self._datasets.get(dataset_id)
        if not lineage:
            return None
        lineage.transformations.append({
            "name": name,
            "description": description,
            "tool": tool,
            "params": params or {},
            "timestamp": __import__("time").time(),
        })
        return lineage

    def get(self, dataset_id: str) -> Optional[DatasetLineage]:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> List[DatasetLineage]:
        return list(self._datasets.values())
