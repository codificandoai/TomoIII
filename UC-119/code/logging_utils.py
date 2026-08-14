"""
Codificando.AI - UC-119
Logging estructurado en JSON, compatible con Loki/Promtail.

Cada línea de log es un objeto JSON con campos consistentes
(timestamp, level, logger, message, request_id, ...) para facilitar el
parseo por Promtail y las consultas LogQL en Grafana.
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone

from config import CONFIG, PII_PATTERNS

_PII_REGEXES = {name: re.compile(pattern) for name, pattern in PII_PATTERNS.items()}


def redact_pii(text: str) -> str:
    """Reemplaza patrones de PII conocidos por marcadores `[REDACTED:<tipo>]`."""
    if not text:
        return text
    redacted = text
    for name, regex in _PII_REGEXES.items():
        redacted = regex.sub(f"[REDACTED:{name}]", redacted)
    return redacted


class JsonFormatter(logging.Formatter):
    """Formatea registros de logging como JSON de una sola línea."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attr in ("request_id", "model", "trace_id", "span_id"):
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


def get_request_logger(logger: logging.Logger, request_id: str, model: str = None):
    """Devuelve un `LoggerAdapter` que añade `request_id`/`model` a cada log."""
    extra = {"request_id": request_id}
    if model:
        extra["model"] = model
    return logging.LoggerAdapter(logger, extra)
