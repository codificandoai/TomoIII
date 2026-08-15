"""
Codificando.AI - UC-129
Logging estructurado en JSON, compatible con Loki/Promtail (mismo patrón
usado en UC-119/UC-127 para mantener consistencia entre casos de uso).
"""

import json
import logging
import sys
from datetime import datetime, timezone

from config import CONFIG


class JsonFormatter(logging.Formatter):
    """Formatea registros de logging como JSON de una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in ("incident_id", "incident_type", "source", "trace_id"):
            if hasattr(record, attr):
                payload[attr] = getattr(record, attr)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = None, json_format: bool = None) -> None:
    """Configura el logging raíz del proceso."""
    level = level or CONFIG.logging.level
    json_format = CONFIG.logging.json_format if json_format is None else json_format

    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    root.addHandler(handler)


def get_incident_logger(logger: logging.Logger, incident_id: str, incident_type: str = None,
                         source: str = None):
    """Devuelve un `LoggerAdapter` que añade `incident_id`/`incident_type`
    a cada línea de log, para correlacionar con Loki."""
    extra = {"incident_id": incident_id}
    if incident_type:
        extra["incident_type"] = incident_type
    if source:
        extra["source"] = source
    return logging.LoggerAdapter(logger, extra)
