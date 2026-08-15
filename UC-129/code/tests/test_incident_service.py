import time

import pytest

from incident_metrics_types import (
    DetectionSource, IncidentStatus, IncidentType, IngestedTrace, ResolutionType, Severity,
)


def test_report_event_creates_active_incident(service):
    record = service.report_event(IncidentType.JAILBREAK, Severity.HIGH)
    assert record.status == IncidentStatus.DETECTED
    assert service.get(record.incident_id) is record


def test_full_lifecycle_detect_and_resolve(service):
    record = service.report_event(IncidentType.HALLUCINATION, Severity.MEDIUM,
                                    event_time=time.time() - 5.0)
    service.record_detection(record.incident_id, detection_method="auto_guardrail")
    assert record.mttd_seconds >= 5.0

    resolved = service.record_resolution(record.incident_id, ResolutionType.AUTO_REMEDIATION,
                                          success=True, tokens_during_incident=100,
                                          latency_during_incident_s=1.2)
    assert resolved.status == IncidentStatus.RESOLVED
    assert resolved.mttr_seconds is not None
    assert resolved.tokens_during_incident == 100


def test_resolve_without_prior_detection_auto_detects(service):
    record = service.report_event(IncidentType.SYSTEM_OVERLOAD)
    resolved = service.record_resolution(record.incident_id, ResolutionType.ROLLBACK, success=True)
    assert resolved.detect_time is not None
    assert resolved.detection_method == "immediate"


def test_false_positive_marks_status(service):
    record = service.report_event(IncidentType.TOXICITY)
    service.record_detection(record.incident_id, detection_method="auto_guardrail")
    fp = service.record_false_positive(record.incident_id)
    assert fp.status == IncidentStatus.FALSE_POSITIVE
    assert fp.is_false_positive is True


def test_hitl_escalation_sets_fields(service):
    record = service.report_event(IncidentType.BIAS)
    escalated = service.record_hitl_escalation(record.incident_id, reason="ambiguous",
                                                reviewer_role="compliance")
    assert escalated.hitl_escalated is True
    assert escalated.escalation_reason == "ambiguous"
    assert escalated.reviewer_role == "compliance"


def test_close_incident_sets_root_cause(service):
    record = service.report_event(IncidentType.LATENCY_SPIKE)
    closed = service.close_incident(record.incident_id, root_cause="capacity_shortage")
    assert closed.root_cause == "capacity_shortage"


def test_unknown_incident_id_raises_keyerror(service):
    with pytest.raises(KeyError):
        service.record_detection("does-not-exist", detection_method="manual")


def test_ingest_trace_without_incident_signal_returns_none(service):
    trace = IngestedTrace(source=DetectionSource.LANGFUSE, trace_id="t1", latency_seconds=0.5)
    assert service.ingest_trace(trace) is None


def test_ingest_trace_with_tag_creates_incident(service):
    trace = IngestedTrace(source=DetectionSource.LANGSMITH, trace_id="t2",
                           latency_seconds=1.0, tags=["jailbreak"])
    incident = service.ingest_trace(trace)
    assert incident is not None
    assert incident.incident_type == IncidentType.JAILBREAK
    assert incident.detect_time is not None
    assert incident.trace_id == "t2"


def test_ingest_trace_auto_create_disabled(service, monkeypatch):
    from config import CONFIG
    monkeypatch.setattr(CONFIG.telemetry, "auto_create_incidents", False)
    trace = IngestedTrace(source=DetectionSource.LANGGRAPH, trace_id="t3", tags=["hallucination"])
    assert service.ingest_trace(trace) is None


def test_list_filters_by_type_and_status(service):
    r1 = service.report_event(IncidentType.HALLUCINATION)
    r2 = service.report_event(IncidentType.JAILBREAK)
    service.record_detection(r2.incident_id, "manual")
    service.record_resolution(r2.incident_id, ResolutionType.HITL_MANUAL, success=True)

    assert {r.incident_id for r in service.list(incident_type=IncidentType.HALLUCINATION)} == {r1.incident_id}
    assert {r.incident_id for r in service.list(status=IncidentStatus.RESOLVED)} == {r2.incident_id}


def test_summary_aggregates_metrics(service):
    r1 = service.report_event(IncidentType.HALLUCINATION, event_time=time.time() - 2)
    service.record_detection(r1.incident_id, "auto_guardrail")
    service.record_resolution(r1.incident_id, ResolutionType.AUTO_REMEDIATION, success=True)

    r2 = service.report_event(IncidentType.BIAS)
    service.record_detection(r2.incident_id, "monitoring_alert")
    service.record_false_positive(r2.incident_id)

    summary = service.summary()
    assert summary["total_incidents"] == 2
    assert summary["incidents_by_type"]["HALLUCINATION"] == 1
    assert summary["incidents_by_type"]["BIAS"] == 1
    assert summary["resolution_rate"] == 0.5
    assert summary["false_positive_rate"] == 0.5
    assert summary["mttd_seconds_avg"] is not None
