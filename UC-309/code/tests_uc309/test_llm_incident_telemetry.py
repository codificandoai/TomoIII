"""Tests para LLMIncidentTelemetryPipeline."""
import pytest

from llm_incident_telemetry_pipeline import (
    LLMIncidentTelemetryPipeline,
    PolicyProposal,
)


@pytest.fixture
def pipeline():
    return LLMIncidentTelemetryPipeline()


def test_record_event(pipeline):
    ev = pipeline.record(
        trace_id="trace-1",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="What is 2+2?",
        output_text="4",
        latency_ms=120.0,
        tokens_input=10,
        tokens_output=5,
    )
    assert ev.message_id
    assert ev.tokens_total == 15
    assert pipeline.metrics()["llm_incident_events_total"] == 1


def test_redact_pii(pipeline):
    ev = pipeline.record(
        trace_id="trace-2",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="My email is test@example.com",
        output_text="Your email is test@example.com",
        latency_ms=100.0,
    )
    assert "test@example.com" not in ev.input_redacted
    assert "test@example.com" not in ev.output_redacted


def test_add_user_feedback(pipeline):
    ev = pipeline.record(
        trace_id="trace-3",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="hello",
        output_text="hi",
        latency_ms=50.0,
    )
    updated = pipeline.add_user_feedback(ev.message_id, "Bad answer", 1)
    assert updated is not None
    assert updated.user_rating == 1
    assert pipeline.metrics()["llm_incident_feedback_total"] == 1
    assert len(pipeline.list_proposals()) > 0


def test_link_postmortem(pipeline):
    ev = pipeline.record(
        trace_id="trace-4",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="hello",
        output_text="hi",
        latency_ms=50.0,
    )
    linked = pipeline.link_to_postmortem(ev.message_id, "postmortem-123")
    assert linked is not None
    assert linked.postmortem_id == "postmortem-123"
    assert pipeline.metrics()["llm_incident_postmortem_links_total"] == 1


def test_proposal_for_error(pipeline):
    ev = pipeline.record(
        trace_id="trace-5",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="hello",
        output_text="",
        latency_ms=50.0,
        status="error",
        error="timeout",
    )
    proposals = [p for p in pipeline.list_proposals() if p["trace_id"] == ev.trace_id]
    assert any(p["target"] == "uc087_retrain" for p in proposals)


def test_policy_sink_called(pipeline):
    proposals = []

    def sink(p):
        proposals.append(p)

    pipeline.policy_sink = sink
    ev = pipeline.record(
        trace_id="trace-6",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="hello",
        output_text="hi",
        latency_ms=50.0,
    )
    pipeline.add_user_feedback(ev.message_id, "Bad", 1)
    assert len(proposals) > 0


def test_export_prometheus(pipeline):
    pipeline.record(
        trace_id="trace-7",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4o-mini",
        model_version="2024-07",
        input_text="hello",
        output_text="hi",
        latency_ms=50.0,
    )
    text = pipeline.export_prometheus()
    assert isinstance(text, str)
