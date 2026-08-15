"""
Codificando.AI - UC-127
Clasificador de incidentes: traduce telemetría cruda (métricas del pipeline
de monitoreo de LLMs, p.ej. UC-119) o webhooks de Alertmanager/Grafana en
un `IncidentAlert` normalizado con tipo y severidad.
"""

import logging
from typing import Any, Dict, Optional

from config import CONFIG, ALERT_NAME_TO_INCIDENT_TYPE
from incident_types import IncidentAlert, IncidentType, Severity

logger = logging.getLogger(__name__)


class IncidentClassifier:
    """Clasifica telemetría e incidentes reportados en tipos y severidades
    de UC-127, aplicando los umbrales de `config.DetectionThresholds`."""

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or CONFIG.thresholds

    # ------------------------------------------------------------------
    # Clasificación desde métricas crudas del pipeline de monitoreo LLM
    # ------------------------------------------------------------------
    def classify_from_metrics(
        self,
        model: str,
        model_version: Optional[str] = None,
        hallucination_rate: Optional[float] = None,
        guardrail_blocked_ratio: Optional[float] = None,
        evasion_attempts_per_min: Optional[float] = None,
        pii_leak_events: Optional[int] = None,
        quality_score: Optional[float] = None,
        tool_error_rate: Optional[float] = None,
        latency_p99_s: Optional[float] = None,
        error_rate: Optional[float] = None,
        cost_increase_ratio: Optional[float] = None,
        toxicity_score: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[IncidentAlert]:
        """Evalúa un conjunto de métricas y devuelve el incidente de mayor
        severidad detectado, o `None` si ninguna métrica supera sus
        umbrales de advertencia."""

        t = self.thresholds
        candidates = []

        if pii_leak_events is not None and pii_leak_events >= t.pii_leak_events_critical:
            candidates.append((IncidentType.DATA_LEAK, Severity.CRITICAL,
                                f"{pii_leak_events} evento(s) de filtración de PII detectados"))

        if evasion_attempts_per_min is not None:
            if evasion_attempts_per_min >= t.evasion_attempts_per_min_critical:
                candidates.append((IncidentType.PROMPT_INJECTION, Severity.CRITICAL,
                                    f"{evasion_attempts_per_min}/min intentos de evasión (crítico)"))
            elif evasion_attempts_per_min >= t.evasion_attempts_per_min_warning:
                candidates.append((IncidentType.PROMPT_INJECTION, Severity.MEDIUM,
                                    f"{evasion_attempts_per_min}/min intentos de evasión"))

        if toxicity_score is not None and toxicity_score >= 0.8:
            candidates.append((IncidentType.UNSAFE_GENERATION, Severity.CRITICAL,
                                f"toxicity_score={toxicity_score} >= 0.8"))
        if guardrail_blocked_ratio is not None:
            if guardrail_blocked_ratio >= t.guardrail_blocked_ratio_critical:
                candidates.append((IncidentType.UNSAFE_GENERATION, Severity.CRITICAL,
                                    f"guardrail_blocked_ratio={guardrail_blocked_ratio:.2%}"))
            elif guardrail_blocked_ratio >= t.guardrail_blocked_ratio_warning:
                candidates.append((IncidentType.UNSAFE_GENERATION, Severity.HIGH,
                                    f"guardrail_blocked_ratio={guardrail_blocked_ratio:.2%}"))

        if hallucination_rate is not None:
            if hallucination_rate >= t.hallucination_rate_critical:
                candidates.append((IncidentType.HALLUCINATION, Severity.CRITICAL,
                                    f"hallucination_rate={hallucination_rate:.2%}"))
            elif hallucination_rate >= t.hallucination_rate_warning:
                candidates.append((IncidentType.HALLUCINATION, Severity.MEDIUM,
                                    f"hallucination_rate={hallucination_rate:.2%}"))

        if quality_score is not None:
            if quality_score <= t.quality_score_critical:
                candidates.append((IncidentType.QUALITY_DEGRADATION, Severity.HIGH,
                                    f"quality_score={quality_score:.2f}"))
            elif quality_score <= t.quality_score_warning:
                candidates.append((IncidentType.QUALITY_DEGRADATION, Severity.MEDIUM,
                                    f"quality_score={quality_score:.2f}"))

        if tool_error_rate is not None:
            if tool_error_rate >= t.tool_error_rate_critical:
                candidates.append((IncidentType.TOOL_FAILURE, Severity.CRITICAL,
                                    f"tool_error_rate={tool_error_rate:.2%}"))
            elif tool_error_rate >= t.tool_error_rate_warning:
                candidates.append((IncidentType.TOOL_FAILURE, Severity.MEDIUM,
                                    f"tool_error_rate={tool_error_rate:.2%}"))

        if latency_p99_s is not None:
            if latency_p99_s >= t.latency_p99_critical_s:
                candidates.append((IncidentType.LATENCY_ANOMALY, Severity.CRITICAL,
                                    f"latency_p99={latency_p99_s:.2f}s"))
            elif latency_p99_s >= t.latency_p99_warning_s:
                candidates.append((IncidentType.LATENCY_ANOMALY, Severity.MEDIUM,
                                    f"latency_p99={latency_p99_s:.2f}s"))

        if error_rate is not None:
            if error_rate >= t.error_rate_critical:
                candidates.append((IncidentType.SYSTEM_OVERLOAD, Severity.CRITICAL,
                                    f"error_rate={error_rate:.2%}"))
            elif error_rate >= t.error_rate_warning:
                candidates.append((IncidentType.SYSTEM_OVERLOAD, Severity.HIGH,
                                    f"error_rate={error_rate:.2%}"))

        if cost_increase_ratio is not None:
            if cost_increase_ratio >= t.cost_increase_ratio_critical:
                candidates.append((IncidentType.COST_ANOMALY, Severity.CRITICAL,
                                    f"cost_increase_ratio={cost_increase_ratio:.2%}"))
            elif cost_increase_ratio >= t.cost_increase_ratio_warning:
                candidates.append((IncidentType.COST_ANOMALY, Severity.MEDIUM,
                                    f"cost_increase_ratio={cost_increase_ratio:.2%}"))

        if not candidates:
            return None

        # Prioriza el candidato de mayor severidad; en caso de empate, el
        # primero evaluado (orden de prioridad de seguridad > calidad > infra).
        incident_type, severity, summary = max(candidates, key=lambda c: c[1].rank)

        metrics = {
            k: v for k, v in {
                "hallucination_rate": hallucination_rate,
                "guardrail_blocked_ratio": guardrail_blocked_ratio,
                "evasion_attempts_per_min": evasion_attempts_per_min,
                "pii_leak_events": pii_leak_events,
                "quality_score": quality_score,
                "tool_error_rate": tool_error_rate,
                "latency_p99_s": latency_p99_s,
                "error_rate": error_rate,
                "cost_increase_ratio": cost_increase_ratio,
                "toxicity_score": toxicity_score,
            }.items() if v is not None
        }

        return IncidentAlert(
            incident_type=incident_type,
            severity=severity,
            model=model,
            model_version=model_version,
            summary=summary,
            source="metrics_pipeline",
            metrics=metrics,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Clasificación desde un webhook de Alertmanager/Grafana
    # ------------------------------------------------------------------
    def classify_from_alertmanager(self, payload: Dict[str, Any]) -> Optional[IncidentAlert]:
        """Traduce un webhook estándar de Alertmanager
        (`{"alerts": [{"labels": {...}, "annotations": {...}}]}`) al primer
        `IncidentAlert` reconocido. Devuelve `None` si ninguna alerta del
        payload es reconocida."""

        alerts = payload.get("alerts", [payload])
        for raw in alerts:
            labels = raw.get("labels", {})
            annotations = raw.get("annotations", {})
            alertname = labels.get("alertname")
            incident_type_name = ALERT_NAME_TO_INCIDENT_TYPE.get(alertname)
            if not incident_type_name:
                continue

            severity_label = labels.get("severity", "warning").lower()
            severity = {
                "critical": Severity.CRITICAL,
                "warning": Severity.MEDIUM,
                "info": Severity.LOW,
            }.get(severity_label, Severity.MEDIUM)

            return IncidentAlert(
                incident_type=IncidentType(incident_type_name),
                severity=severity,
                model=labels.get("model", "unknown"),
                model_version=labels.get("model_version"),
                summary=annotations.get("summary", alertname),
                source="alertmanager",
                labels=labels,
                correlation_id=labels.get("request_id"),
                starts_at=raw.get("startsAt", None) or IncidentAlert.__dataclass_fields__["starts_at"].default_factory(),
            )

        logger.info("Webhook de Alertmanager recibido sin alertas reconocidas por UC-127")
        return None
