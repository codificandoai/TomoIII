import json
import time

import pytest

from models_309 import CanonicalEvent, EventType, Outcome, UC300Auth
from privacy_guard import PrivacyGuard, pseudonymize
from trace_store import TraceStore, has_permission
from trace_correlator import validate_trace
from adapters_309 import from_langsmith, from_langfuse, from_langgraph
from metrics_aggregator import MetricsAggregator
from anomaly_detector import AnomalyDetector
from alert_manager_309 import AlertManager
from exporters_309 import to_loki_lines, to_tempo_spans, to_prometheus_text
from api_309 import create_app
from observability_orchestrator import ObservabilityOrchestrator


@pytest.fixture
def store():
    return TraceStore(max_records=1000, retention_seconds=3600, require_role=True)


@pytest.fixture
def orch():
    return ObservabilityOrchestrator(privacy=PrivacyGuard(sample_rate=1.0))


def _event(trace_id, span_id, event_type, step=0, **kwargs):
    base = {
        "trace_id": trace_id,
        "span_id": span_id,
        "step": step,
        "event_type": event_type,
        "timestamp_ns": int(time.time() * 1e9),
        "agent_id": "test-agent",
        "agent_version": "1",
    }
    base.update(kwargs)
    return base


def test_full_cycle_reconstruction(store):
    tid = "trace-1"
    store.store(CanonicalEvent.from_dict(_event(tid, tid, "trace_start", 0)))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "action_proposed", 1, action_proposed={"tool": "x"}, action_proposed_hash="h1")))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "uc300_authorization", 2, uc300={"authorized": True, "approved_action_hash": "h1"})))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "observation", 3, observed_action_hash="h1", tool_result_status="success")))
    store.store(CanonicalEvent.from_dict(_event(tid, tid, "final_outcome", 4, final_outcome="success")))
    events, report = validate_trace(store, tid, role="auditor")
    assert len(events) == 5
    assert report.to_dict()["valid"]
    assert not report.to_dict()["missing_start"]
    assert not report.to_dict()["missing_end"]


def test_parent_span_validation(store):
    tid = "trace-2"
    store.store(CanonicalEvent.from_dict(_event(tid, tid, "trace_start", 0)))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "observation", 1, parent_span_id="missing-parent")))
    _, report = validate_trace(store, tid, role="auditor")
    assert report.broken_parents == ["missing-parent"]


def test_redaction_and_pii():
    guard = PrivacyGuard()
    raw = {
        "trace_id": "t1",
        "span_id": "s1",
        "event_type": "observation",
        "action_proposed": {"tool": "x", "api_key": "sk-abc12345678901234567890", "email": "user@example.com"},
    }
    safe = guard.sanitize(raw)
    assert safe["action_proposed"]["api_key"] == "[REDACTED]"
    assert safe["pii_pseudonyms"]
    # Email should be replaced by a pseudonym
    assert "pii_" in json.dumps(safe)
    assert safe["redaction_findings"]


def test_pii_stability():
    assert pseudonymize("user@example.com") == pseudonymize("user@example.com")
    assert pseudonymize("user@example.com") != pseudonymize("other@example.com")
    guard_a = PrivacyGuard(pii_key=b"tenant-a")
    guard_b = PrivacyGuard(pii_key=b"tenant-b")
    assert guard_a.pseudonym_for("user@example.com") != guard_b.pseudonym_for("user@example.com")


def test_chain_of_thought_rejection():
    guard = PrivacyGuard()
    raw = {
        "trace_id": "t1",
        "span_id": "s1",
        "event_type": "thought_summary",
        "structured_reasoning_summary": "raw: First I thought about the secret plan",
        "chain_of_thought": "this should not be stored",
    }
    safe = guard.sanitize(raw)
    assert safe.get("chain_of_thought") is None
    assert "[SUMMARY_ONLY]" in (safe.get("structured_reasoning_summary") or "")
    assert any("private_reasoning_transformed" in f or "raw_reasoning_rejected" in f for f in safe["redaction_findings"])


def test_sampling_forced_errors():
    guard = PrivacyGuard(sample_rate=0.0, forced_capture=True)
    error = {"trace_id": "t1", "span_id": "s1", "event_type": "error", "error": "boom"}
    normal = {"trace_id": "t2", "span_id": "s2", "event_type": "observation"}
    assert guard.should_capture(error)
    assert not guard.should_capture(normal)


def test_retention(store):
    tid = "trace-ret"
    store.store(CanonicalEvent.from_dict(_event(tid, tid, "trace_start", 0)))
    store.set_retention(max_records=1, retention_seconds=3600, role="admin")
    tid2 = "trace-ret-2"
    store.store(CanonicalEvent.from_dict(_event(tid2, tid2, "trace_start", 0)))
    assert tid not in store.list_traces(role="admin")


def test_rbac(store):
    tid = "rbac"
    store.store(CanonicalEvent.from_dict(_event(tid, tid, "trace_start", 0)))
    with pytest.raises(PermissionError):
        store.get_trace(tid, role="nobody")
    with pytest.raises(PermissionError):
        store.get_trace(tid, role=None)
    assert has_permission("admin", "reset")
    assert not has_permission("viewer", "reset")


def test_label_cardinality():
    from privacy_guard import enforce_label_cardinality
    labels = {
        "tool_name": "update_price",
        "agent_id": "a1",
        "trace_id": "t1",
        "session_id": "s1",
        "unknown_high_card_label": "value",
    }
    safe = enforce_label_cardinality(labels)
    assert "trace_id" not in safe
    assert "session_id" not in safe
    assert "unknown_high_card_label" not in safe
    assert safe["tool_name"] == "update_price"


def test_langsmith_adapter():
    payload = {
        "run_id": "ls-1",
        "session_id": "session-1",
        "name": "test-agent",
        "inputs": {"tools": {"update_price": {}}},
        "child_runs": [
            {"id": "child-1", "name": "update_price", "run_type": "tool", "runtime_ms": 80},
        ],
        "outputs": {"answer": "ok"},
    }
    events = from_langsmith(payload)
    assert any(e.event_type == EventType.TOOL_CALL for e in events)


def test_langfuse_adapter():
    payload = {
        "traceId": "lf-1",
        "sessionId": "s1",
        "name": "test-agent",
        "observations": [
            {"id": "o1", "name": "search", "type": "SPAN", "startTime": 1e9, "endTime": 1.1e9, "output": "result"},
        ],
    }
    events = from_langfuse(payload)
    assert any(e.event_type in (EventType.TOOL_CALL, EventType.OBSERVATION) for e in events)


def test_langgraph_adapter():
    payload = {
        "thread_id": "lg-1",
        "graph_id": "agent",
        "messages": [
            {"type": "ai", "content": "ok", "tool_calls": [{"name": "search", "args": {}}]},
        ],
    }
    events = from_langgraph(payload)
    assert any(e.tool_name == "search" for e in events)


def test_action_divergence_detected(store):
    tid = "div"
    store.store(CanonicalEvent.from_dict(_event(tid, tid, "trace_start", 0)))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "action_proposed", 1, action_proposed={"tool": "x"}, action_proposed_hash="approved")))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "uc300_authorization", 2, uc300={"authorized": True, "approved_action_hash": "approved"})))
    store.store(CanonicalEvent.from_dict(_event(tid, "s1", "observation", 3, observed_action_hash="observed")))
    _, report = validate_trace(store, tid, role="auditor")
    assert any("divergence" in i for i in report.issues)


def test_loops_and_anomaly():
    events = [
        CanonicalEvent.from_dict(_event("loop", "s1", "tool_call", 1, tool_name="search", tool_result_status="success")),
        CanonicalEvent.from_dict(_event("loop", "s2", "tool_call", 2, tool_name="search", tool_result_status="success")),
        CanonicalEvent.from_dict(_event("loop", "s3", "tool_call", 3, tool_name="search", tool_result_status="success")),
    ]
    det = AnomalyDetector()
    anomalies = det.detect(events)
    assert any(a["type"] == "abnormal_tool_frequency" for a in anomalies)


def test_prometheus_export():
    metrics = MetricsAggregator()
    events = [
        CanonicalEvent.from_dict(_event("m1", "s1", "tool_call", 1, tool_name="t", tool_result_status="success", latency_ms=100, input_tokens=10, output_tokens=5)),
        CanonicalEvent.from_dict(_event("m1", "s2", "tool_call", 2, tool_name="t", tool_result_status="error", latency_ms=200, input_tokens=20, output_tokens=5)),
    ]
    metrics.update(events)
    text = to_prometheus_text(metrics)
    assert "uc309_tool_calls_total" in text
    assert "trace_id" not in text
    assert "session_id" not in text


def test_loki_and_tempo_exports():
    events = [CanonicalEvent.from_dict(_event("l1", "s1", "tool_call", 1, tool_name="x"))]
    lines = to_loki_lines(events)
    assert len(lines) == 1
    spans = to_tempo_spans(events)
    assert spans[0]["traceId"] == "l1"


def test_api_endpoints(orch):
    app = create_app(orch)
    client = app.test_client()
    assert client.get("/health").status_code == 200
    schema = client.get("/schema").get_json()
    assert "input_cards" in schema
    assert "output_cards" in schema

    # Emit with role
    ev = {
        "trace_id": "api-1",
        "span_id": "api-1",
        "event_type": "trace_start",
        "agent_id": "x",
    }
    r = client.post("/events", json=ev, headers={"X-UC309-Role": "admin"})
    assert r.status_code == 200

    r = client.get("/traces", headers={"X-UC309-Role": "analyst"})
    assert r.status_code == 200
    assert "api-1" in r.get_json()["traces"]

    r = client.get("/traces/api-1", headers={"X-UC309-Role": "admin"})
    assert r.status_code == 200

    r = client.get("/metrics")
    assert r.status_code == 200
    assert "uc309" in r.data.decode().lower()

    assert client.get("/logs").status_code == 403
    r = client.get("/logs", headers={"X-UC309-Role": "analyst"})
    assert r.status_code == 200

    assert client.get("/spans").status_code == 403
    r = client.get("/spans", headers={"X-UC309-Role": "viewer"})
    assert r.status_code == 200

    assert client.get("/alerts").status_code == 403
    r = client.get("/alerts", headers={"X-UC309-Role": "auditor"})
    assert r.status_code == 200


def test_e2e_uc308_feed(orch):
    ev = {
        "trace_id": "uc308",
        "span_id": "uc308",
        "event_type": "final_outcome",
        "agent_id": "e2e",
        "final_outcome": "success",
        "input_tokens": 100,
        "output_tokens": 50,
    }
    orch.emit(ev)
    feed = orch.metrics.to_dict()
    assert "counters" in feed or "gauges" in feed
    assert "last_update" in feed
