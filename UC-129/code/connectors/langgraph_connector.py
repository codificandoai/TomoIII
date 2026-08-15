"""
Codificando.AI - UC-129
Conector de LangGraph: traduce el evento de callback emitido por un grafo
instrumentado (nodo/herramienta finalizado) al formato común
`IngestedTrace`. LangGraph no define un webhook estándar; se asume que la
aplicación host reenvía sus callbacks (`on_chain_end`/`on_tool_end`, etc.)
con el siguiente esquema normalizado:

{
  "graph_id": "support-agent-v2",
  "node": "generate_response",
  "status": "success" | "error" | "interrupted",
  "duration_ms": 640.0,
  "tokens": {"input": 80, "output": 210},
  "model": "claude-3-5-sonnet",
  "flags": ["hallucination_flag", "toxicity_flag"]
}
"""

from typing import Any, Dict

from incident_metrics_types import DetectionSource, IngestedTrace


def parse_langgraph_event(payload: Dict[str, Any]) -> IngestedTrace:
    node = payload.get("node") or payload.get("node_id")
    graph_id = payload.get("graph_id", "unknown_graph")
    if not node:
        raise ValueError("Evento de LangGraph inválido: falta 'node'/'node_id'")

    trace_id = f"{graph_id}:{node}:{payload.get('run_id', payload.get('step', ''))}"
    tokens = payload.get("tokens") or {}
    status = payload.get("status", "success")
    # "interrupted" representa una pausa HITL explícita en el grafo (p.ej.
    # `interrupt()`), no un fallo; se normaliza como estado propio.
    normalized_status = status if status in ("success", "error", "interrupted") else "success"

    return IngestedTrace(
        source=DetectionSource.LANGGRAPH,
        trace_id=trace_id,
        model=payload.get("model", "unknown"),
        latency_seconds=float(payload.get("duration_ms", 0.0) or 0.0) / 1000.0,
        input_tokens=int(tokens.get("input", 0) or 0),
        output_tokens=int(tokens.get("output", 0) or 0),
        status=normalized_status,
        tags=[str(t).lower().replace("_flag", "") for t in payload.get("flags", [])],
        metadata={"graph_id": graph_id, "node": node},
        raw=payload,
    )
