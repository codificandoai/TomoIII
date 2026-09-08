"""UC-309 — LLM Incident Telemetry Pipeline.

Recopila, redacta y enriquece eventos LLM para fundamentar despliegues y
mejoras continuas del sistema LLMOps. Integra con UC-309 para:

- Almacenar eventos canónicos redactados (input/output, tokens, latencia,
  modelo, versión, mensaje, trace_id).
- Exportar logs a Loki, trazas a Tempo y métricas a Prometheus.
- Recibir comentarios de usuario y vincularlos a postmortems.
- Proponer actualizaciones de políticas/entrenamiento a UC-300 y UC-087.
- Proveer dashboards de incidentes para Grafana.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from models_309 import CanonicalEvent, EventType, Outcome
from observability_orchestrator import ObservabilityOrchestrator
from privacy_guard import PrivacyGuard


@dataclass
class LLMIncidentEvent:
    """Evento LLM enriquecido con telemetría."""
    trace_id: str
    message_id: str
    agent_id: str
    model: str
    model_version: str
    provider: str
    input_redacted: str
    output_redacted: str
    latency_ms: float
    tokens_input: int
    tokens_output: int
    tokens_total: int
    status: str
    error: str
    user_feedback: Optional[str] = None
    user_rating: Optional[int] = None
    postmortem_id: Optional[str] = None
    labels: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "message_id": self.message_id,
            "agent_id": self.agent_id,
            "model": self.model,
            "model_version": self.model_version,
            "provider": self.provider,
            "input_redacted": self.input_redacted,
            "output_redacted": self.output_redacted,
            "latency_ms": self.latency_ms,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_total": self.tokens_total,
            "status": self.status,
            "error": self.error,
            "user_feedback": self.user_feedback,
            "user_rating": self.user_rating,
            "postmortem_id": self.postmortem_id,
            "labels": self.labels,
        }


@dataclass
class PolicyProposal:
    """Propuesta de actualización derivada de un incidente."""
    proposal_id: str
    trace_id: str
    target: str
    reason: str
    evidence: Dict[str, Any]
    confidence: float
    requires_approval: bool
    proposed_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "trace_id": self.trace_id,
            "target": self.target,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "proposed_action": self.proposed_action,
        }


class LLMIncidentTelemetryPipeline:
    """Pipeline de telemetría de incidentes LLM."""

    def __init__(
        self,
        observability: Optional[ObservabilityOrchestrator] = None,
        privacy: Optional[PrivacyGuard] = None,
        policy_sink: Optional[Callable[[PolicyProposal], None]] = None,
    ) -> None:
        self.observability = observability or ObservabilityOrchestrator()
        self.privacy = privacy or PrivacyGuard()
        self.policy_sink = policy_sink
        self._incidents: Dict[str, LLMIncidentEvent] = {}
        self._proposals: List[PolicyProposal] = []
        self._metrics: Dict[str, Any] = {
            "events_total": 0,
            "errors_total": 0,
            "feedback_total": 0,
            "postmortem_links_total": 0,
            "proposals_total": 0,
            "latency_sum_ms": 0.0,
            "tokens_sum": 0,
        }

    def _record_metric(self, key: str, value: float) -> None:
        if key in ("events_total", "errors_total", "feedback_total", "postmortem_links_total", "proposals_total", "tokens_sum"):
            self._metrics[key] = self._metrics.get(key, 0) + int(value)
        elif key in ("latency_sum_ms",):
            self._metrics[key] = self._metrics.get(key, 0.0) + float(value)

    def _sanitize(self, text: str) -> str:
        if not text:
            return ""
        # Usa PrivacyGuard para redactar posible PII y chain-of-thought
        return self.privacy.sanitize({"content": text}).get("content", "")

    def record(
        self,
        trace_id: str,
        agent_id: str,
        provider: str,
        model: str,
        model_version: str,
        input_text: str,
        output_text: str,
        latency_ms: float,
        tokens_input: int = 0,
        tokens_output: int = 0,
        status: str = "success",
        error: str = "",
        labels: Optional[Dict[str, Any]] = None,
    ) -> LLMIncidentEvent:
        """Registra un evento LLM redactado y lo emite a UC-309."""
        message_id = str(uuid.uuid4())[:12]
        incident = LLMIncidentEvent(
            trace_id=trace_id,
            message_id=message_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            model_version=model_version,
            input_redacted=self._sanitize(input_text),
            output_redacted=self._sanitize(output_text),
            latency_ms=latency_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_input + tokens_output,
            status=status,
            error=error,
            labels=labels or {},
        )

        # Emitir como evento canónico en UC-309
        canonical = CanonicalEvent(
            trace_id=trace_id,
            span_id=message_id,
            agent_id=agent_id,
            agent_version=model_version,
            event_type=EventType.MODEL_REQUEST,
            labels={
                "provider": provider,
                "model": model,
                "model_version": model_version,
                "status": status,
            },
            final_outcome=Outcome.SUCCESS if status == "success" else Outcome.FAILURE,
            error=error,
            tool_result_status=status,
            latency_ms=latency_ms,
            input_tokens=tokens_input,
            output_tokens=tokens_output,
            evidence_refs=[],
        )
        self.observability.emit(canonical)

        self._incidents[message_id] = incident
        self._record_metric("events_total", 1)
        self._record_metric("latency_sum_ms", latency_ms)
        self._record_metric("tokens_sum", tokens_input + tokens_output)
        if status != "success":
            self._record_metric("errors_total", 1)

        # Evaluar si el evento por sí solo amerita propuestas
        if status != "success":
            self._maybe_propose_policy_update(incident)

        return incident

    def add_user_feedback(
        self,
        message_id: str,
        feedback: str,
        rating: Optional[int] = None,
    ) -> Optional[LLMIncidentEvent]:
        """Anota un incidente con comentarios del usuario."""
        incident = self._incidents.get(message_id)
        if incident is None:
            return None
        incident.user_feedback = feedback
        incident.user_rating = rating
        self._record_metric("feedback_total", 1)

        # Actualizar evento canónico con feedback
        canonical = CanonicalEvent(
            trace_id=incident.trace_id,
            span_id=message_id,
            agent_id=incident.agent_id,
            agent_version=incident.model_version,
            event_type=EventType.OBSERVATION,
            labels={
                "model": incident.model,
                "model_version": incident.model_version,
                "rating": str(rating) if rating is not None else "none",
            },
            final_outcome=Outcome.SUCCESS,
            evidence_refs=[],
        )
        self.observability.emit(canonical)

        # Evaluar si amerita propuesta de política
        self._maybe_propose_policy_update(incident)
        return incident

    def link_to_postmortem(
        self,
        message_id: str,
        postmortem_id: str,
    ) -> Optional[LLMIncidentEvent]:
        """Vincula un evento con un postmortem."""
        incident = self._incidents.get(message_id)
        if incident is None:
            return None
        incident.postmortem_id = postmortem_id
        self._record_metric("postmortem_links_total", 1)

        canonical = CanonicalEvent(
            trace_id=incident.trace_id,
            span_id=message_id,
            agent_id=incident.agent_id,
            agent_version=incident.model_version,
            event_type=EventType.OBSERVATION,
            labels={
                "postmortem_id": postmortem_id,
                "model": incident.model,
            },
            final_outcome=Outcome.SUCCESS,
            evidence_refs=[],
        )
        self.observability.emit(canonical)
        return incident

    def _maybe_propose_policy_update(self, incident: LLMIncidentEvent) -> None:
        """Genera propuestas de mejora basadas en feedback/incidente."""
        proposals: List[PolicyProposal] = []

        if incident.user_rating is not None and incident.user_rating <= 2:
            proposals.append(PolicyProposal(
                proposal_id=str(uuid.uuid4())[:12],
                trace_id=incident.trace_id,
                target="uc300_guardrails",
                reason="User rating is low; tighten input/output guardrails or review model selection.",
                evidence=incident.to_dict(),
                confidence=0.6,
                requires_approval=True,
                proposed_action="tighten_guardrails",
            ))

        if incident.error or incident.status != "success":
            proposals.append(PolicyProposal(
                proposal_id=str(uuid.uuid4())[:12],
                trace_id=incident.trace_id,
                target="uc087_retrain",
                reason="LLM error/incident detected; consider retraining or champion-challenger evaluation.",
                evidence=incident.to_dict(),
                confidence=0.7,
                requires_approval=True,
                proposed_action="retrain_or_rollback",
            ))

        if incident.tokens_total > 4000:
            proposals.append(PolicyProposal(
                proposal_id=str(uuid.uuid4())[:12],
                trace_id=incident.trace_id,
                target="uc300_quota",
                reason="High token usage; review context compression or quota limits.",
                evidence=incident.to_dict(),
                confidence=0.5,
                requires_approval=False,
                proposed_action="review_quota",
            ))

        for p in proposals:
            self._proposals.append(p)
            self._record_metric("proposals_total", 1)
            if self.policy_sink is not None:
                try:
                    self.policy_sink(p)
                except Exception:
                    pass

    def export_loki(self) -> List[str]:
        """Exporta eventos LLM como líneas Loki JSON."""
        return self.observability.export_loki()

    def export_tempo(self) -> List[Dict[str, Any]]:
        """Exporta trazas LLM como spans Tempo."""
        return self.observability.export_tempo()

    def export_prometheus(self) -> str:
        """Exporta métricas Prometheus."""
        return self.observability.export_prometheus_text()

    def metrics(self) -> Dict[str, Any]:
        """Métricas agregadas del pipeline."""
        m = self._metrics
        events = max(m["events_total"], 1)
        return {
            "llm_incident_events_total": m["events_total"],
            "llm_incident_errors_total": m["errors_total"],
            "llm_incident_feedback_total": m["feedback_total"],
            "llm_incident_postmortem_links_total": m["postmortem_links_total"],
            "llm_incident_proposals_total": m["proposals_total"],
            "llm_incident_avg_latency_ms": round(m["latency_sum_ms"] / events, 2),
            "llm_incident_avg_tokens": round(m["tokens_sum"] / events, 2),
        }

    def get_incident(self, message_id: str) -> Optional[Dict[str, Any]]:
        incident = self._incidents.get(message_id)
        return incident.to_dict() if incident else None

    def list_incidents(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self._incidents.values()]

    def list_proposals(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._proposals]
