from classifier import TelemetryClassifier
from incident_metrics_types import DetectionSource, IncidentType, IngestedTrace, Severity


def make_trace(**kwargs) -> IngestedTrace:
    defaults = dict(source=DetectionSource.LANGFUSE, trace_id="t1", model="m",
                     latency_seconds=0.5, status="success", tags=[])
    defaults.update(kwargs)
    return IngestedTrace(**defaults)


def test_clean_trace_returns_none():
    classifier = TelemetryClassifier()
    assert classifier.classify(make_trace()) is None


def test_tag_match_hallucination():
    classifier = TelemetryClassifier()
    candidate = classifier.classify(make_trace(tags=["hallucination"]))
    assert candidate.incident_type == IncidentType.HALLUCINATION
    assert candidate.severity == Severity.MEDIUM


def test_tag_match_jailbreak_is_high_severity():
    classifier = TelemetryClassifier()
    candidate = classifier.classify(make_trace(tags=["jailbreak"]))
    assert candidate.incident_type == IncidentType.JAILBREAK
    assert candidate.severity == Severity.HIGH


def test_tag_with_error_status_escalates_severity():
    classifier = TelemetryClassifier()
    candidate = classifier.classify(make_trace(tags=["bias"], status="error"))
    assert candidate.incident_type == IncidentType.BIAS
    assert candidate.severity == Severity.HIGH  # escalado desde MEDIUM


def test_error_status_without_tag_is_tool_failure():
    classifier = TelemetryClassifier()
    candidate = classifier.classify(make_trace(status="error"))
    assert candidate.incident_type == IncidentType.TOOL_FAILURE
    assert candidate.severity == Severity.HIGH


def test_latency_spike_medium():
    classifier = TelemetryClassifier()
    candidate = classifier.classify(make_trace(latency_seconds=6.0))
    assert candidate.incident_type == IncidentType.LATENCY_SPIKE
    assert candidate.severity == Severity.MEDIUM


def test_latency_spike_critical():
    classifier = TelemetryClassifier()
    candidate = classifier.classify(make_trace(latency_seconds=20.0))
    assert candidate.incident_type == IncidentType.LATENCY_SPIKE
    assert candidate.severity == Severity.CRITICAL


def test_interrupted_status_does_not_trigger_incident():
    classifier = TelemetryClassifier()
    assert classifier.classify(make_trace(status="interrupted")) is None
