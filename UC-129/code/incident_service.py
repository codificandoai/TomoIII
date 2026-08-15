"""
Codificando.AI - UC-129
Servicio central de métricas de resiliencia LLMOps: gestiona el ciclo de
vida de cada incidente (ocurrencia -> detección -> resolución/falso
positivo/escalamiento), calcula MTTD/MTTR, actualiza las métricas de
Prometheus (`prometheus_metrics.py`) y mantiene un historial en memoria
para exponer analítica agregada (frecuencia por tipo, tasa de resolución,
tasa de falsos positivos, frecuencia de escalamiento) vía API.

También integra la ingesta de telemetría normalizada
(`incident_metrics_types.IngestedTrace`) proveniente de los conectores de
Langfuse/LangSmith/LangGraph: cada traza actualiza las métricas genéricas
de latencia/carga/tokens y, si el `TelemetryClassifier` detecta un patrón
de riesgo, abre automáticamente un incidente (detectado en el mismo
instante de la ingesta).
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from classifier import TelemetryClassifier
from config import CONFIG
from incident_metrics_types import (
    DetectionSource,
    IncidentRecord,
    IncidentStatus,
    IncidentType,
    IngestedTrace,
    ResolutionType,
    Severity,
)
from logging_utils import get_incident_logger
import prometheus_metrics as pm

logger = logging.getLogger(__name__)


class IncidentMetricsService:
    """Orquesta el ciclo de vida de los incidentes y la ingesta de
    telemetría externa, manteniendo sincronizadas las métricas de
    Prometheus con el historial de auditoría en memoria."""

    def __init__(self):
        self._lock = threading.Lock()
        self._incidents: Dict[str, IncidentRecord] = {}
        self.classifier = TelemetryClassifier()

    # ------------------------------------------------------------------
    # Ciclo de vida manual de incidentes (API directa)
    # ------------------------------------------------------------------
    def report_event(self, incident_type: IncidentType, severity: Severity = Severity.MEDIUM,
                      source: DetectionSource = DetectionSource.MONITORING_ALERT,
                      model: str = "unknown", summary: str = "",
                      trace_id: Optional[str] = None,
                      event_time: Optional[float] = None) -> IncidentRecord:
        """Registra el instante real en que ocurrió el evento (puede ser
        anterior al de detección; ver `record_detection`)."""
        record = IncidentRecord(
            incident_type=incident_type, severity=severity, source=source,
            model=model, summary=summary, trace_id=trace_id,
            event_time=event_time if event_time is not None else time.time(),
        )
        with self._lock:
            self._incidents[record.incident_id] = record

        pm.INCIDENTS_TOTAL.labels(
            incident_type=incident_type.value, severity=severity.value,
            source=source.value, phase="during_incident",
        ).inc()
        pm.ACTIVE_INCIDENTS_GAUGE.labels(incident_type=incident_type.value).inc()

        ilog = get_incident_logger(logger, record.incident_id, incident_type.value, source.value)
        ilog.info(f"Incidente reportado: {incident_type.value} ({severity.value})")
        return record

    def record_detection(self, incident_id: str, detection_method: str) -> IncidentRecord:
        record = self._require(incident_id)
        record.detect_time = time.time()
        record.detection_method = detection_method
        record.updated_at = datetime.now(timezone.utc).isoformat()

        pm.MTTD_SECONDS.labels(
            incident_type=record.incident_type.value, detection_method=detection_method,
        ).observe(record.mttd_seconds or 0.0)

        ilog = get_incident_logger(logger, incident_id, record.incident_type.value)
        ilog.info(f"Incidente detectado. MTTD={record.mttd_seconds:.2f}s (método={detection_method})")
        return record

    def record_resolution(self, incident_id: str, resolution_type: ResolutionType, success: bool,
                           tokens_during_incident: int = 0,
                           latency_during_incident_s: Optional[float] = None) -> IncidentRecord:
        record = self._require(incident_id)
        if record.detect_time is None:
            # Autodetección implícita: si nunca se llamó a record_detection
            # (p.ej. resolución inmediata automatizada), se asume detección
            # simultánea a la ocurrencia.
            self.record_detection(incident_id, detection_method="immediate")

        record.resolve_time = time.time()
        record.resolution_type = resolution_type
        record.resolution_success = success
        record.status = IncidentStatus.RESOLVED
        record.tokens_during_incident = tokens_during_incident
        record.latency_during_incident_s = latency_during_incident_s
        record.updated_at = datetime.now(timezone.utc).isoformat()

        pm.MTTR_SECONDS.labels(
            incident_type=record.incident_type.value, resolution_type=resolution_type.value,
        ).observe(record.mttr_seconds or 0.0)
        pm.RESOLUTIONS_TOTAL.labels(
            incident_type=record.incident_type.value, resolution_type=resolution_type.value,
            success=str(success).lower(),
        ).inc()
        pm.INCIDENTS_TOTAL.labels(
            incident_type=record.incident_type.value, severity=record.severity.value,
            source=record.source.value, phase="post_incident",
        ).inc()
        pm.ACTIVE_INCIDENTS_GAUGE.labels(incident_type=record.incident_type.value).dec()

        if tokens_during_incident:
            pm.TOKENS_DURING_INCIDENT.labels(
                incident_type=record.incident_type.value, model=record.model,
            ).inc(tokens_during_incident)
        if latency_during_incident_s is not None:
            pm.LATENCY_DURING_INCIDENT.labels(incident_type=record.incident_type.value).observe(
                latency_during_incident_s)

        ilog = get_incident_logger(logger, incident_id, record.incident_type.value)
        ilog.info(f"Incidente resuelto. MTTR={record.mttr_seconds:.2f}s (método={resolution_type.value}, "
                   f"éxito={success})")
        return record

    def record_false_positive(self, incident_id: str) -> IncidentRecord:
        record = self._require(incident_id)
        record.is_false_positive = True
        record.status = IncidentStatus.FALSE_POSITIVE
        record.updated_at = datetime.now(timezone.utc).isoformat()

        pm.FALSE_POSITIVES_TOTAL.labels(
            incident_type=record.incident_type.value,
            detection_method=record.detection_method or "unknown",
        ).inc()
        pm.ACTIVE_INCIDENTS_GAUGE.labels(incident_type=record.incident_type.value).dec()

        ilog = get_incident_logger(logger, incident_id, record.incident_type.value)
        ilog.info("Incidente marcado como falso positivo")
        return record

    def record_hitl_escalation(self, incident_id: str, reason: str, reviewer_role: str) -> IncidentRecord:
        record = self._require(incident_id)
        record.hitl_escalated = True
        record.escalation_reason = reason
        record.reviewer_role = reviewer_role
        record.updated_at = datetime.now(timezone.utc).isoformat()

        pm.HITL_ESCALATIONS_TOTAL.labels(
            incident_type=record.incident_type.value, escalation_reason=reason,
            reviewer_role=reviewer_role,
        ).inc()

        ilog = get_incident_logger(logger, incident_id, record.incident_type.value)
        ilog.info(f"Incidente escalado a HITL: {reason} (revisor={reviewer_role})")
        return record

    def close_incident(self, incident_id: str, root_cause: str) -> IncidentRecord:
        record = self._require(incident_id)
        record.root_cause = root_cause
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return record

    # ------------------------------------------------------------------
    # Ingesta de telemetría (Langfuse / LangSmith / LangGraph)
    # ------------------------------------------------------------------
    def ingest_trace(self, trace: IngestedTrace) -> Optional[IncidentRecord]:
        """Registra la telemetría genérica de la traza y, si corresponde,
        abre automáticamente un incidente."""
        phase = "post_incident"  # las trazas ingeridas reflejan interacciones ya completadas
        pm.TELEMETRY_REQUESTS_TOTAL.labels(
            source=trace.source.value, model=trace.model, status=trace.status, phase=phase,
        ).inc()
        pm.TELEMETRY_LATENCY_SECONDS.labels(
            source=trace.source.value, model=trace.model, phase=phase,
        ).observe(trace.latency_seconds)
        if trace.input_tokens:
            pm.TELEMETRY_TOKENS_TOTAL.labels(
                source=trace.source.value, model=trace.model, token_type="input", phase=phase,
            ).inc(trace.input_tokens)
        if trace.output_tokens:
            pm.TELEMETRY_TOKENS_TOTAL.labels(
                source=trace.source.value, model=trace.model, token_type="output", phase=phase,
            ).inc(trace.output_tokens)

        pm.SYSTEM_AVAILABILITY_GAUGE.labels(source=trace.source.value).set(
            0.0 if trace.status == "error" else 1.0)

        if not CONFIG.telemetry.auto_create_incidents:
            return None

        candidate = self.classifier.classify(trace)
        if candidate is None:
            return None

        event_time = time.time() - max(trace.latency_seconds, 0.0)
        record = self.report_event(
            incident_type=candidate.incident_type, severity=candidate.severity,
            source=trace.source, model=trace.model, summary=candidate.reason,
            trace_id=trace.trace_id, event_time=event_time,
        )
        # La ingesta ocurre en el mismo instante en que la plataforma de
        # observabilidad reporta la traza: se considera detección inmediata.
        self.record_detection(record.incident_id, detection_method=trace.source.value)
        return record

    # ------------------------------------------------------------------
    # Consultas y analítica
    # ------------------------------------------------------------------
    def get(self, incident_id: str) -> Optional[IncidentRecord]:
        return self._incidents.get(incident_id)

    def list(self, incident_type: Optional[IncidentType] = None,
              status: Optional[IncidentStatus] = None) -> List[IncidentRecord]:
        records = list(self._incidents.values())
        if incident_type:
            records = [r for r in records if r.incident_type == incident_type]
        if status:
            records = [r for r in records if r.status == status]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def summary(self, window_hours: Optional[int] = None) -> Dict[str, object]:
        """Analítica agregada: frecuencia por tipo, MTTD/MTTR promedio,
        tasa de resolución, tasa de falsos positivos y frecuencia de
        escalamiento HITL — la base del panel "Estado General" del
        dashboard de Grafana."""
        records = list(self._incidents.values())
        if window_hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            records = [r for r in records if datetime.fromisoformat(r.created_at) >= cutoff]

        total = len(records)
        by_type: Dict[str, int] = {}
        mttd_values, mttr_values = [], []
        resolved, false_positives, escalated = 0, 0, 0

        for r in records:
            by_type[r.incident_type.value] = by_type.get(r.incident_type.value, 0) + 1
            if r.mttd_seconds is not None:
                mttd_values.append(r.mttd_seconds)
            if r.mttr_seconds is not None:
                mttr_values.append(r.mttr_seconds)
            if r.status == IncidentStatus.RESOLVED:
                resolved += 1
            if r.is_false_positive:
                false_positives += 1
            if r.hitl_escalated:
                escalated += 1

        return {
            "total_incidents": total,
            "incidents_by_type": by_type,
            "mttd_seconds_avg": sum(mttd_values) / len(mttd_values) if mttd_values else None,
            "mttr_seconds_avg": sum(mttr_values) / len(mttr_values) if mttr_values else None,
            "resolution_rate": (resolved / total) if total else None,
            "false_positive_rate": (false_positives / total) if total else None,
            "hitl_escalation_rate": (escalated / total) if total else None,
            "active_incidents": sum(1 for r in records if r.status == IncidentStatus.DETECTED),
        }

    def _require(self, incident_id: str) -> IncidentRecord:
        record = self._incidents.get(incident_id)
        if record is None:
            raise KeyError(f"Incidente no encontrado: {incident_id}")
        return record
