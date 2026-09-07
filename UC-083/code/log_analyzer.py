"""
UC-083 — Analizador de logs para respuesta a incidentes de inferencia batch.

Detecta patrones de error (OOM, timeout, excepciones, terminación de workers)
a partir de logs estructurados o semi-estructurados.
"""

import re
from typing import List, Dict, Optional, Any
from datetime import datetime

from incident_models import LogEntry


class LogAnalyzer:
    """
    Analiza logs del orquestador y workers para identificar síntomas y
correlacionar eventos por trace_id.
    """

    # Patrones comunes de fallas en pipelines batch
    PATTERNS = {
        "oom": re.compile(r"(killed|out of memory|oom|memory limit exceeded)", re.IGNORECASE),
        "timeout": re.compile(r"(timeout|deadline exceeded|took too long)", re.IGNORECASE),
        "worker_death": re.compile(r"(worker died|worker terminated|worker killed|exit code)", re.IGNORECASE),
        "exception": re.compile(r"(exception|error|traceback|failed)", re.IGNORECASE),
        "volume_warning": re.compile(r"(volumen excesivo|excessive volume|too many rows|large input)", re.IGNORECASE),
    }

    def __init__(self):
        self._entries: List[LogEntry] = []

    def add_log(self, entry: LogEntry) -> None:
        self._entries.append(entry)

    def parse_raw_log(self, raw: str, source: str = "unknown") -> List[LogEntry]:
        """Parsea texto de log simple en entradas estructuradas."""
        entries = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # Intentar extraer timestamp ISO o timestamp unix
            ts_match = re.search(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)", line)
            ts = datetime.now().timestamp()
            if ts_match:
                try:
                    ts = datetime.fromisoformat(ts_match.group(1).replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass

            level = "INFO"
            if re.search(r"\bERROR\b|\bCRITICAL\b|\bFATAL\b", line):
                level = "ERROR"
            elif re.search(r"\bWARN\b|\bWARNING\b", line):
                level = "WARN"

            trace_id_match = re.search(r"trace[_-]?id[:=]([a-zA-Z0-9\-]+)", line, re.IGNORECASE)
            trace_id = trace_id_match.group(1) if trace_id_match else None

            entry = LogEntry(
                timestamp=ts,
                level=level,
                source=source,
                message=line,
                trace_id=trace_id,
                metadata={"parsed": True},
            )
            entries.append(entry)
            self._entries.append(entry)
        return entries

    def find_error_patterns(self) -> Dict[str, int]:
        """Cuenta ocurrencias de patrones de error."""
        counts = {key: 0 for key in self.PATTERNS}
        for entry in self._entries:
            for key, pattern in self.PATTERNS.items():
                if pattern.search(entry.message):
                    counts[key] += 1
        return counts

    def correlate_by_trace(self, trace_id: str) -> List[LogEntry]:
        return [e for e in self._entries if e.trace_id == trace_id]

    def get_error_timeline(self) -> List[Dict[str, Any]]:
        """Retorna cronología de logs de error ordenados."""
        errors = [e for e in self._entries if e.level in ("ERROR", "CRITICAL", "FATAL")]
        errors.sort(key=lambda x: x.timestamp)
        return [e.to_dict() for e in errors]

    def summarize(self) -> Dict[str, Any]:
        patterns = self.find_error_patterns()
        return {
            "total_logs": len(self._entries),
            "error_count": sum(1 for e in self._entries if e.level == "ERROR"),
            "warning_count": sum(1 for e in self._entries if e.level == "WARN"),
            "patterns": patterns,
            "error_timeline": self.get_error_timeline(),
        }

    def reset(self) -> None:
        self._entries.clear()
