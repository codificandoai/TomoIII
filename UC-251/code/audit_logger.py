"""Trazabilidad y auditoría de consultas RAG."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import RAGConfig
from models import AuditLog, RAGASMetrics, RAGResponse
from security import SecurityChecker

logger = logging.getLogger("uc251-audit")


class AuditLogger:
    """Registra en memoria y, opcionalmente, en disco cada interacción RAG."""

    def __init__(self, config: RAGConfig, security: Optional[SecurityChecker] = None):
        self.config = config
        self.security = security
        self._logs: List[AuditLog] = []
        self._lock = threading.Lock()
        self._path: Optional[Path] = None
        work_dir = Path(config.vector_store.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        self._path = work_dir / "audit.jsonl"

    def log(
        self,
        query: str,
        response: RAGResponse,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metrics: Optional[RAGASMetrics] = None,
    ) -> AuditLog:
        sanitized_query = (
            self.security.sanitize_for_logging(query) if self.security else query
        )
        sanitized_response = (
            self.security.sanitize_for_logging(response.answer)
            if self.security
            else response.answer
        )
        log = AuditLog(
            trace_id=response.trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            query=query,
            sanitized_query=sanitized_query,
            retrieved_chunk_ids=[r.chunk.chunk_id for r in response.retrieved_chunks],
            response_text=sanitized_response,
            latency_ms=response.latency_ms,
            tenant_id=tenant_id,
            user_id=user_id,
            security_flags=response.security_flags,
            metrics=metrics,
        )
        with self._lock:
            self._logs.append(log)
            self._append_to_disk(log)
        return log

    def _append_to_disk(self, log: AuditLog) -> None:
        if self._path is None:
            return
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(log.to_dict(), ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover
            logger.warning("No se pudo escribir auditoría: %s", exc)

    def list_logs(
        self,
        trace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        with self._lock:
            filtered = [
                log
                for log in reversed(self._logs)
                if (trace_id is None or log.trace_id == trace_id)
                and (tenant_id is None or log.tenant_id == tenant_id)
            ]
            return filtered[:limit]

    def get_by_trace_id(self, trace_id: str) -> Optional[AuditLog]:
        for log in reversed(self._logs):
            if log.trace_id == trace_id:
                return log
        return None
