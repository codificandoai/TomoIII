"""Central orchestrator for UC-309: privacy, storage, metrics, alerts and exports."""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from models_309 import CanonicalEvent
from privacy_guard import PrivacyGuard
from trace_store import TraceStore
from trace_correlator import validate_trace
from metrics_aggregator import MetricsAggregator
from anomaly_detector import AnomalyDetector
from alert_manager_309 import AlertManager
from adapters_309 import from_langsmith, from_langfuse, from_langgraph, AdapterError


class ObservabilityOrchestrator:
    def __init__(
        self,
        store: Optional[TraceStore] = None,
        privacy: Optional[PrivacyGuard] = None,
        metrics: Optional[MetricsAggregator] = None,
        detector: Optional[AnomalyDetector] = None,
        alerts: Optional[AlertManager] = None,
    ):
        self.store = store or TraceStore()
        self.privacy = privacy or PrivacyGuard()
        self.metrics = metrics or MetricsAggregator()
        self.detector = detector or AnomalyDetector()
        self.alerts = alerts or AlertManager()

    def emit(self, raw_event) -> Optional[CanonicalEvent]:
        """Canonical, provider-independent ingestion pipeline."""
        raw = raw_event.to_dict() if isinstance(raw_event, CanonicalEvent) else raw_event

        # Sampling before storing (privacy and storage are expensive)
        if not self.privacy.should_capture(raw):
            return None

        # Privacy guard
        safe = self.privacy.sanitize(raw)

        # Build canonical event
        event = CanonicalEvent.from_dict(safe)

        # Store and maintain hash chain
        self.store.store(event)

        # Recompute metrics and detect anomalies
        self._refresh_derived()
        return event

    def emit_raw_events(self, events: Iterable[Dict[str, Any]]) -> List[CanonicalEvent]:
        out: List[CanonicalEvent] = []
        for ev in events:
            c = self.emit(ev)
            if c:
                out.append(c)
        return out

    def ingest_adapter(self, adapter: str, payload: Dict[str, Any]) -> List[CanonicalEvent]:
        """Ingest an external adapter payload and translate to canonical events."""
        if adapter == "langsmith":
            events = from_langsmith(payload)
        elif adapter == "langfuse":
            events = from_langfuse(payload)
        elif adapter == "langgraph":
            events = from_langgraph(payload)
        else:
            raise AdapterError(f"unknown adapter: {adapter}")
        out: List[CanonicalEvent] = []
        for ev in events:
            raw = ev.to_dict()
            if not self.privacy.should_capture(raw):
                continue
            safe = self.privacy.sanitize(raw)
            c = CanonicalEvent.from_dict(safe)
            self.store.store(c)
            out.append(c)
        self._refresh_derived()
        return out

    def _refresh_derived(self):
        events = self.store.get_all_events(role="auditor")
        self.metrics.reset()
        self.metrics.update(events)
        anomalies = self.detector.detect(events, self.metrics)
        self.alerts.ingest(anomalies)

    def get_trace(self, trace_id: str, role: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self.store.get_trace(trace_id, role=role)
        return [e.to_dict() for e in events]

    def validate_trace(self, trace_id: str, role: Optional[str] = None) -> Dict[str, Any]:
        _, report = validate_trace(self.store, trace_id, role=role)
        return report.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.to_dict()

    def get_prometheus(self) -> str:
        return self.metrics.render_prometheus()

    def get_alerts(self, acknowledged: Optional[bool] = None) -> List[Dict[str, Any]]:
        return self.alerts.list_alerts(acknowledged=acknowledged)

    def acknowledge_alert(self, alert_id: str, user: Optional[str] = None) -> bool:
        return self.alerts.acknowledge(alert_id, user)

    def export_loki(self) -> List[str]:
        from exporters_309 import to_loki_lines
        return to_loki_lines(self.store.get_all_events(role="auditor"))

    def export_tempo(self) -> List[Dict[str, Any]]:
        from exporters_309 import to_tempo_spans
        return to_tempo_spans(self.store.get_all_events(role="auditor"))

    def export_prometheus_text(self) -> str:
        return self.metrics.render_prometheus()

    def status(self) -> Dict[str, Any]:
        return {
            "events": self.store.retention_stats()["total_events"],
            "traces": self.store.retention_stats()["total_traces"],
            "alerts": len(self.alerts.list_alerts()),
            "active_alerts": self.alerts.active_count(),
            "last_metric_update": self.metrics._last_update,
        }

    def retention(self, max_records: Optional[int] = None, retention_seconds: Optional[int] = None, role: Optional[str] = None):
        self.store.set_retention(max_records, retention_seconds, role=role)


    # -------------------------------------------------------------------
    # UC-324 Safe Shutdown: postmortem ingestion
    # -------------------------------------------------------------------

    def ingest_postmortem(self, postmortem: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest a redacted postmortem from UC-324 SafeShutdownCoordinator.

        Uses existing privacy sanitation (PrivacyGuard.sanitize) and immutable
        hash-chain store. Stores only the shutdown correlation and evidence
        hash; never raw secrets, chain-of-thought, or private memory contents.
        """
        import hashlib as _hl
        import json as _json
        import time as _time

        # First sanitize the postmortem dict before building the canonical event
        safe = self.privacy.sanitize({
            "trace_id": postmortem.get("trace_id", ""),
            "span_id": postmortem.get("shutdown_id", ""),
            "event_type": "uc324_containment",
            "agent_id": "uc324_safe_shutdown",
            "action_proposed": "shutdown_postmortem",
            "observation_summary": (
                f"Shutdown {postmortem.get('shutdown_id', '?')}: "
                f"state={postmortem.get('final_state', '?')}, "
                f"drained={postmortem.get('tasks_drained', 0)}, "
                f"cancelled={postmortem.get('tasks_cancelled', 0)}"
            ),
            "uc324": {
                "shutdown_id": postmortem.get("shutdown_id", ""),
                "final_state": postmortem.get("final_state", ""),
                "evidence_chain_hash": postmortem.get("evidence_chain_hash", ""),
                "evidence_chain_valid": postmortem.get("evidence_chain_valid", False),
            },
            "evidence_refs": [postmortem.get("evidence_chain_hash", "")],
            "timestamp_ns": int(postmortem.get("timestamp", _time.time()) * 1e9),
        })

        # Compute a stable digest of the sanitized postmortem for the hash chain
        pm_digest = _hl.sha256(
            _json.dumps(postmortem, sort_keys=True, default=str).encode()
        ).hexdigest()[:32]
        safe["observed_action_hash"] = pm_digest

        event = CanonicalEvent.from_dict(safe)
        self.store.store(event)
        self._refresh_derived()

        return {
            "adapter": "uc309_observability",
            "ingested": True,
            "event_hash": event.event_hash,
            "trace_id": event.trace_id,
        }

    def reset(self, role: Optional[str] = None):
        self.store.reset(role=role)
        self.metrics.reset()
        self.alerts.reset()
