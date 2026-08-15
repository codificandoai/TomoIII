"""
Codificando.AI - UC-129
Clasificador que traduce una traza normalizada (`IngestedTrace`, ver
`incident_metrics_types.py`), proveniente de Langfuse, LangSmith o
LangGraph, en un candidato de incidente (tipo + severidad), reutilizando
las etiquetas/tags emitidas por los guardrails de cada plataforma y los
umbrales de latencia/error definidos en `config.py`.

Sigue el mismo patrón de "clasificador desacoplado de la fuente" usado en
`UC-127/code/classifier.py`.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from config import CONFIG, INCIDENT_TAG_MAP
from incident_metrics_types import IncidentType, IngestedTrace, Severity

logger = logging.getLogger(__name__)


@dataclass
class IncidentCandidate:
    incident_type: IncidentType
    severity: Severity
    reason: str


class TelemetryClassifier:
    """Clasifica una `IngestedTrace` en un `IncidentCandidate`, o `None` si
    la traza no amerita la apertura de un incidente."""

    def classify(self, trace: IngestedTrace) -> Optional[IncidentCandidate]:
        # 1. Coincidencia directa por tag (la más confiable: viene de un
        #    guardrail/evaluador que ya etiquetó la traza).
        for tag in trace.tags:
            incident_type_name = INCIDENT_TAG_MAP.get(tag.lower())
            if incident_type_name:
                severity = self._severity_for_tag(incident_type_name, trace)
                return IncidentCandidate(
                    incident_type=IncidentType(incident_type_name),
                    severity=severity,
                    reason=f"tag '{tag}' presente en la traza de {trace.source.value}",
                )

        # 2. Fallo explícito reportado por la plataforma (error de
        #    ejecución de una herramienta/nodo del grafo).
        if trace.status == "error":
            return IncidentCandidate(
                incident_type=IncidentType.TOOL_FAILURE,
                severity=Severity.HIGH,
                reason=f"status='error' reportado por {trace.source.value}",
            )

        # 3. Latencia anómala.
        thresholds = CONFIG.thresholds
        if trace.latency_seconds >= thresholds.latency_critical_seconds:
            return IncidentCandidate(
                incident_type=IncidentType.LATENCY_SPIKE,
                severity=Severity.CRITICAL,
                reason=f"latencia {trace.latency_seconds:.1f}s >= {thresholds.latency_critical_seconds}s",
            )
        if trace.latency_seconds >= thresholds.latency_spike_seconds:
            return IncidentCandidate(
                incident_type=IncidentType.LATENCY_SPIKE,
                severity=Severity.MEDIUM,
                reason=f"latencia {trace.latency_seconds:.1f}s >= {thresholds.latency_spike_seconds}s",
            )

        return None

    @staticmethod
    def _severity_for_tag(incident_type_name: str, trace: IngestedTrace) -> Severity:
        # Severidad por defecto según el tipo; una traza con status="error"
        # simultáneo escala la severidad a CRITICAL.
        base = {
            "JAILBREAK": Severity.HIGH,
            "PROMPT_INJECTION": Severity.HIGH,
            "HALLUCINATION": Severity.MEDIUM,
            "BIAS": Severity.MEDIUM,
            "TOXICITY": Severity.HIGH,
            "TOOL_FAILURE": Severity.HIGH,
        }.get(incident_type_name, Severity.MEDIUM)

        if trace.status == "error" and base != Severity.CRITICAL:
            order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
            return order[min(order.index(base) + 1, len(order) - 1)]
        return base
