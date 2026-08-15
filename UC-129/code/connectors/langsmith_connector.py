"""
Codificando.AI - UC-129
Conector de LangSmith: traduce el payload de un webhook/callback de
finalización de "run" de LangSmith al formato común `IngestedTrace`.

Esquema esperado (simplificado del esquema de Run de LangSmith):
{
  "id": "run-abc123",
  "run_type": "llm",
  "status": "success" | "error",
  "error": null | "ToolException: ...",
  "latency_ms": 980.0,
  "prompt_tokens": 100,
  "completion_tokens": 250,
  "total_tokens": 350,
  "tags": ["bias_flag"],
  "extra": {"metadata": {"model": "gpt-4o-mini"}}
}
"""

from typing import Any, Dict

from incident_metrics_types import DetectionSource, IngestedTrace


def parse_langsmith_webhook(payload: Dict[str, Any]) -> IngestedTrace:
    run_id = payload.get("id") or payload.get("run_id")
    if not run_id:
        raise ValueError("Payload de LangSmith inválido: falta 'id'/'run_id'")

    extra = payload.get("extra") or {}
    metadata = extra.get("metadata") or payload.get("metadata") or {}
    status = "error" if payload.get("error") or payload.get("status") == "error" else "success"

    latency_ms = payload.get("latency_ms")
    if latency_ms is None:
        start_time, end_time = payload.get("start_time"), payload.get("end_time")
        latency_ms = 0.0
        if isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
            latency_ms = max(end_time - start_time, 0.0) * 1000.0

    return IngestedTrace(
        source=DetectionSource.LANGSMITH,
        trace_id=str(run_id),
        model=metadata.get("model", payload.get("model", "unknown")),
        latency_seconds=float(latency_ms or 0.0) / 1000.0,
        input_tokens=int(payload.get("prompt_tokens", 0) or 0),
        output_tokens=int(payload.get("completion_tokens", 0) or 0),
        status=status,
        tags=[str(t).lower() for t in payload.get("tags", [])],
        metadata=metadata,
        raw=payload,
    )
