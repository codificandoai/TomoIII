"""Dataset loader para evaluación pre-producción con categorías de riesgo."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fine_tuning.quality_gate.models_quality import EvalDataset, EvalSample


class DatasetLoader:
    """Carga y valida datasets de evaluación por categoría y nivel de riesgo."""

    VALID_CATEGORIES = {"use_case", "edge_case", "adversarial", "real_user"}
    VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

    def __init__(self) -> None:
        self._datasets: Dict[str, EvalDataset] = {}

    def load_from_records(
        self,
        name: str,
        records: List[Dict[str, Any]],
        baseline_version: str = "",
        previous_version: str = "",
    ) -> EvalDataset:
        samples: List[EvalSample] = []
        for rec in records:
            cat = rec.get("category", "use_case")
            risk = rec.get("risk_level", "medium")
            if cat not in self.VALID_CATEGORIES:
                raise ValueError(f"Invalid category: {cat}")
            if risk not in self.VALID_RISK_LEVELS:
                raise ValueError(f"Invalid risk_level: {risk}")
            samples.append(EvalSample(
                category=cat,
                risk_level=risk,
                input_text=rec.get("input_text", ""),
                expected_output=rec.get("expected_output", ""),
                metadata=rec.get("metadata", {}),
            ))
        ds = EvalDataset(
            name=name,
            samples=samples,
            baseline_version=baseline_version,
            previous_version=previous_version,
        )
        self._datasets[ds.dataset_id] = ds
        return ds

    def get(self, dataset_id: str) -> Optional[EvalDataset]:
        return self._datasets.get(dataset_id)
