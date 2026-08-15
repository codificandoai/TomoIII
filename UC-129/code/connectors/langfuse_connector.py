"""
Codificando.AI - UC-129
Conector de Langfuse: traduce el payload de un webhook de traza de
Langfuse (disparado al finalizar una traza/generación) al formato común
`IngestedTrace`.

Esquema esperado (simplificado del webhook real de Langfuse):
{
  "id": "trace-abc123",
  "name": "chat-completion",
  "latency": 1.23,                     # segundos
  "usage": {"input": 120, "output": 340, "total": 460},
  "level": "DEFAULT" | "WARNING" | "ERROR",
  "statusMessage": "...",
  "tags": ["jailbreak_suspected"],
  "metadata": {"model": "llama-3-8b"}
}
"""

from typing import Any, Dict

from incident_metrics_types import DetectionSource, IngestedTrace


def parse_langfuse_webhook(payload: Dict[str, Any]) -> IngestedTrace:
    trace_id = payload.get("id") or payload.get("traceId")
    if not trace_id:
        raise ValueError("Payload de Langfuse inválido: falta 'id'/'traceId'")

    usage = payload.get("usage") or {}
    metadata = payload.get("metadata") or {}
    level = str(payload.get("level", "DEFAULT")).upper()
    status = "error" if level == "ERROR" else "success"

    return IngestedTrace(
        source=DetectionSource.LANGFUSE,
        trace_id=str(trace_id),
        model=metadata.get("model", payload.get("model", "unknown")),
        latency_seconds=float(payload.get("latency", 0.0) or 0.0),
        input_tokens=int(usage.get("input", usage.get("promptTokens", 0)) or 0),
        output_tokens=int(usage.get("output", usage.get("completionTokens", 0)) or 0),
        status=status,
        tags=[str(t).lower() for t in payload.get("tags", [])],
        metadata=metadata,
        raw=payload,
    )
