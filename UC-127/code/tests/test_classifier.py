from classifier import IncidentClassifier
from incident_types import IncidentType, Severity


def test_no_metrics_returns_none():
    classifier = IncidentClassifier()
    assert classifier.classify_from_metrics(model="m") is None


def test_pii_leak_is_critical():
    classifier = IncidentClassifier()
    alert = classifier.classify_from_metrics(model="m", pii_leak_events=1)
    assert alert.incident_type == IncidentType.DATA_LEAK
    assert alert.severity == Severity.CRITICAL


def test_hallucination_warning_vs_critical():
    classifier = IncidentClassifier()
    warning = classifier.classify_from_metrics(model="m", hallucination_rate=0.25)
    critical = classifier.classify_from_metrics(model="m", hallucination_rate=0.5)
    assert warning.incident_type == IncidentType.HALLUCINATION
    assert warning.severity == Severity.MEDIUM
    assert critical.severity == Severity.CRITICAL


def test_highest_severity_candidate_wins():
    classifier = IncidentClassifier()
    # hallucination_rate -> MEDIUM, pii_leak_events -> CRITICAL
    alert = classifier.classify_from_metrics(model="m", hallucination_rate=0.25, pii_leak_events=1)
    assert alert.incident_type == IncidentType.DATA_LEAK
    assert alert.severity == Severity.CRITICAL


def test_latency_and_error_rate_classified():
    classifier = IncidentClassifier()
    latency_alert = classifier.classify_from_metrics(model="m", latency_p99_s=6.0)
    error_alert = classifier.classify_from_metrics(model="m", error_rate=0.15)
    assert latency_alert.incident_type == IncidentType.LATENCY_ANOMALY
    assert error_alert.incident_type == IncidentType.SYSTEM_OVERLOAD


def test_classify_from_alertmanager_recognized():
    classifier = IncidentClassifier()
    payload = {
        "alerts": [
            {
                "labels": {"alertname": "PIILeakDetected", "severity": "critical", "model": "llama-3-8b"},
                "annotations": {"summary": "PII detectada"},
                "startsAt": "2025-01-01T00:00:00Z",
            }
        ]
    }
    alert = classifier.classify_from_alertmanager(payload)
    assert alert.incident_type == IncidentType.DATA_LEAK
    assert alert.severity == Severity.CRITICAL
    assert alert.model == "llama-3-8b"


def test_classify_from_alertmanager_unknown_returns_none():
    classifier = IncidentClassifier()
    payload = {"alerts": [{"labels": {"alertname": "SomeUnrelatedAlert"}, "annotations": {}}]}
    assert classifier.classify_from_alertmanager(payload) is None
