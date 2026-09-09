"""Congela la traza completa de un incidente en un registro inmutable."""
from __future__ import annotations

from typing import Any, Dict, Optional

from postmortem_loop.models_pm import IncidentRecord


class ContextFreezer:
    """
    Persiste la traza de un incidente: prompt, salida, versiones, logs de
    herramientas, diffs de configuración y estado conversacional.
    """

    def __init__(self) -> None:
        self._records: Dict[str, IncidentRecord] = {}

    def freeze(
        self,
        incident_id: str,
        title: str,
        severity: str,
        category: str,
        prompt: str,
        output: str,
        description: str = "",
        model_version: str = "",
        prompt_version: str = "",
        tool_logs: Optional[Any] = None,
        config_diffs: Optional[Any] = None,
        embeddings_state: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IncidentRecord:
        record = IncidentRecord(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            prompt=prompt,
            output=output,
            model_version=model_version,
            prompt_version=prompt_version,
            tool_logs=tool_logs or [],
            config_diffs=config_diffs or [],
            embeddings_state=embeddings_state or [],
            metadata=metadata or {},
        )
        self._records[record.record_id] = record
        return record

    def get(self, record_id: str) -> Optional[IncidentRecord]:
        return self._records.get(record_id)

    def list_records(self) -> Dict[str, IncidentRecord]:
        return dict(self._records)
