import pytest

from connectors import parse_langfuse_webhook, parse_langgraph_event, parse_langsmith_webhook
from incident_metrics_types import DetectionSource


def test_parse_langfuse_success():
    trace = parse_langfuse_webhook({
        "id": "trace-1", "latency": 1.5, "usage": {"input": 10, "output": 20},
        "level": "DEFAULT", "tags": ["Hallucination"], "metadata": {"model": "llama-3-8b"},
    })
    assert trace.source == DetectionSource.LANGFUSE
    assert trace.trace_id == "trace-1"
    assert trace.status == "success"
    assert trace.total_tokens == 30
    assert trace.tags == ["hallucination"]


def test_parse_langfuse_error_level():
    trace = parse_langfuse_webhook({"id": "trace-2", "level": "ERROR"})
    assert trace.status == "error"


def test_parse_langfuse_missing_id_raises():
    with pytest.raises(ValueError):
        parse_langfuse_webhook({"latency": 1.0})


def test_parse_langsmith_success():
    trace = parse_langsmith_webhook({
        "id": "run-1", "status": "success", "latency_ms": 2000,
        "prompt_tokens": 50, "completion_tokens": 100,
        "tags": ["Jailbreak"], "extra": {"metadata": {"model": "gpt-4o-mini"}},
    })
    assert trace.source == DetectionSource.LANGSMITH
    assert trace.latency_seconds == 2.0
    assert trace.input_tokens == 50
    assert trace.output_tokens == 100
    assert trace.tags == ["jailbreak"]


def test_parse_langsmith_error_field():
    trace = parse_langsmith_webhook({"id": "run-2", "error": "ToolException: boom"})
    assert trace.status == "error"


def test_parse_langsmith_missing_id_raises():
    with pytest.raises(ValueError):
        parse_langsmith_webhook({"status": "success"})


def test_parse_langgraph_success():
    trace = parse_langgraph_event({
        "graph_id": "agent-1", "node": "call_tool", "status": "success",
        "duration_ms": 400, "tokens": {"input": 10, "output": 5}, "model": "claude-3-5-sonnet",
        "flags": ["toxicity_flag"],
    })
    assert trace.source == DetectionSource.LANGGRAPH
    assert trace.latency_seconds == 0.4
    assert trace.tags == ["toxicity"]
    assert trace.metadata["node"] == "call_tool"


def test_parse_langgraph_interrupted_status_preserved():
    trace = parse_langgraph_event({"graph_id": "agent-1", "node": "human_review", "status": "interrupted"})
    assert trace.status == "interrupted"


def test_parse_langgraph_missing_node_raises():
    with pytest.raises(ValueError):
        parse_langgraph_event({"graph_id": "agent-1"})
