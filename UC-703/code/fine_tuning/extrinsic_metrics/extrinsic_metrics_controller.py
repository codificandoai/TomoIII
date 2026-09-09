"""Controller de métricas extrínsecas y contextuales para LLMOps."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fine_tuning.extrinsic_metrics.calculators import (
    ContextualRecallCalculator,
    ExtrinsicCalculator,
)
from fine_tuning.extrinsic_metrics.event_correlator import EventCorrelator
from fine_tuning.extrinsic_metrics.models_em import (
    ApplicationEvent,
    InferenceEvent,
    MetricsSnapshot,
    UnifiedSession,
)
from fine_tuning.extrinsic_metrics.observability import LokiLogger, PrometheusExporter


class ExtrinsicMetricsController:
    """
    Orquesta la ingesta, correlación y exportación de métricas extrínsecas y
    de recuperación contextual.

    Uso:
        em = ExtrinsicMetricsController()
        em.ingest_application_event({...})
        em.ingest_inference_event({...})
        snapshot = em.compute_metrics(window_start, window_end)
        prom = em.render_prometheus()
    """

    def __init__(
        self,
        correlator: Optional[EventCorrelator] = None,
        extrinsic_calc: Optional[ExtrinsicCalculator] = None,
        contextual_calc: Optional[ContextualRecallCalculator] = None,
        prometheus: Optional[PrometheusExporter] = None,
        loki: Optional[LokiLogger] = None,
    ) -> None:
        self.correlator = correlator or EventCorrelator()
        self.extrinsic_calc = extrinsic_calc or ExtrinsicCalculator()
        self.contextual_calc = contextual_calc or ContextualRecallCalculator()
        self.prometheus = prometheus or PrometheusExporter()
        self.loki = loki or LokiLogger()
        self._snapshots: List[MetricsSnapshot] = []

    def ingest_application_event(self, data: Dict[str, Any]) -> UnifiedSession:
        event = ApplicationEvent(
            session_id=data.get("session_id", ""),
            event_type=data.get("event_type", ""),
            timestamp=data.get("timestamp", time.time()),
            user_id=data.get("user_id", ""),
            task_id=data.get("task_id", ""),
            task_name=data.get("task_name", ""),
            success=data.get("success"),
            revenue_usd=float(data.get("revenue_usd", 0.0)),
            metadata=data.get("metadata", {}),
        )
        session = self.correlator.ingest_application_event(event)
        self.loki.log(
            event="application_event_ingested",
            session_id=event.session_id,
            trace_id="",
            step="ingest",
            status="success",
            payload=event.to_dict(),
        )
        return session

    def ingest_inference_event(self, data: Dict[str, Any]) -> UnifiedSession:
        event = InferenceEvent(
            trace_id=data.get("trace_id", ""),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp", time.time()),
            model=data.get("model", ""),
            prompt=data.get("prompt", ""),
            completion=data.get("completion", ""),
            tokens_input=int(data.get("tokens_input", 0)),
            tokens_output=int(data.get("tokens_output", 0)),
            latency_ms=float(data.get("latency_ms", 0.0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
            context_chunks_used=int(data.get("context_chunks_used", 0)),
            context_references=list(data.get("context_references", [])),
            llm_judge_context_score=data.get("llm_judge_context_score"),
            metadata=data.get("metadata", {}),
        )
        session = self.correlator.ingest_inference_event(event)
        self.loki.log(
            event="inference_event_ingested",
            session_id=event.session_id,
            trace_id=event.trace_id,
            step="ingest",
            status="success",
            payload=event.to_dict(),
        )
        return session

    def compute_metrics(
        self,
        window_start: float,
        window_end: float,
        baseline_retention_rate: Optional[float] = None,
    ) -> MetricsSnapshot:
        sessions = self.correlator.sessions()
        extrinsic = self.extrinsic_calc.calculate(
            sessions, window_start, window_end, baseline_retention_rate
        )
        contextual = self.contextual_calc.calculate(sessions, window_start, window_end)
        self.prometheus.emit_extrinsic(extrinsic)
        self.prometheus.emit_contextual(contextual)
        snapshot = MetricsSnapshot(extrinsic=extrinsic, contextual=contextual)
        self._snapshots.append(snapshot)
        self.loki.log(
            event="metrics_snapshot",
            session_id="aggregate",
            trace_id="",
            step="compute",
            status="success",
            payload=snapshot.to_dict(),
        )
        return snapshot

    def render_prometheus(self) -> str:
        return self.prometheus.render()

    def get_logs(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.loki.get_entries()]

    def get_snapshots(self) -> List[MetricsSnapshot]:
        return list(self._snapshots)

    def get_session(self, session_id: str) -> Optional[UnifiedSession]:
        return self.correlator.get_session(session_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessions": len(self.correlator.sessions()),
            "snapshots": [s.to_dict() for s in self._snapshots],
        }
