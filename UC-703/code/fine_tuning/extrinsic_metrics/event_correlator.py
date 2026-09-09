"""Correlaciona eventos de aplicación y eventos de inferencia por session_id/trace_id."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fine_tuning.extrinsic_metrics.models_em import (
    ApplicationEvent,
    InferenceEvent,
    UnifiedSession,
)


class EventCorrelator:
    """
    Une eventos de negocio (aplicación) con eventos técnicos (inferencia) usando
    `session_id` como clave común. También mantiene el mapeo `trace_id → session_id`.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, UnifiedSession] = {}
        self._trace_to_session: Dict[str, str] = {}
        self._app_events: List[ApplicationEvent] = []
        self._inf_events: List[InferenceEvent] = []

    def ingest_application_event(self, event: ApplicationEvent) -> UnifiedSession:
        self._app_events.append(event)
        session = self._sessions.setdefault(
            event.session_id, UnifiedSession(session_id=event.session_id)
        )
        session.application_events.append(event)
        if event.event_type == "session_closed":
            session.closed_at = event.timestamp
        return session

    def ingest_inference_event(self, event: InferenceEvent) -> UnifiedSession:
        self._inf_events.append(event)
        session = self._sessions.get(event.session_id)
        if session is None:
            # If session not yet seen, create it and remember trace mapping.
            session = UnifiedSession(session_id=event.session_id)
            self._sessions[event.session_id] = session
        session.inference_events.append(event)
        if event.trace_id and event.trace_id not in session.trace_ids:
            session.trace_ids.append(event.trace_id)
            self._trace_to_session[event.trace_id] = event.session_id
        return session

    def get_session(self, session_id: str) -> Optional[UnifiedSession]:
        return self._sessions.get(session_id)

    def get_session_by_trace(self, trace_id: str) -> Optional[UnifiedSession]:
        session_id = self._trace_to_session.get(trace_id)
        if session_id is None:
            return None
        return self._sessions.get(session_id)

    def sessions(self) -> List[UnifiedSession]:
        return list(self._sessions.values())

    def trace_to_session(self) -> Dict[str, str]:
        return dict(self._trace_to_session)
