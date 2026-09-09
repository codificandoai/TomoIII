"""Observability de inferencia: métricas, trazas y logs inmutables."""
from __future__ import annotations

from typing import Any, Dict, List

from production_serving.models_serving import InferenceRequest, InferenceResponse, TelemetryRecord


class ObservabilityAdapter:
    """
    Captura prompt, salida, latencia, tokens y metadatos de cada inferencia
    en un registro de telemetría. Simula exportación a Prometheus, Tempo/Jaeger
    y un almacén SIEM.
    """

    def __init__(self) -> None:
        self._records: List[TelemetryRecord] = []
        self._metrics: Dict[str, float] = {
            "inference_total": 0.0,
            "inference_errors": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "throughput_rps": 0.0,
            "gpu_utilization": 0.0,
        }

    def emit(
        self,
        request: InferenceRequest,
        response: InferenceResponse,
        origin: str = "api",
    ) -> TelemetryRecord:
        record = TelemetryRecord(
            request_id=request.request_id,
            trace_id=request.trace_id,
            principal_id=request.principal_id,
            model_id=response.model_id,
            prompt=request.prompt,
            response=response.generated_text,
            latency_ms=response.latency_ms,
            token_usage=response.usage,
            guardrails=response.guardrails,
            origin=origin,
        )
        self._records.append(record)
        self._update_metrics(response)
        return record

    def _update_metrics(self, response: InferenceResponse) -> None:
        self._metrics["inference_total"] += 1.0
        if response.guardrails.blocked:
            self._metrics["inference_errors"] += 1.0
        # simplistic latency update
        self._metrics["latency_p50_ms"] = response.latency_ms
        self._metrics["latency_p95_ms"] = response.latency_ms * 1.5
        self._metrics["throughput_rps"] = 1.0
        self._metrics["gpu_utilization"] = 0.45

    def query(self, principal_id: str = "", model_id: str = "") -> List[TelemetryRecord]:
        records = self._records
        if principal_id:
            records = [r for r in records if r.principal_id == principal_id]
        if model_id:
            records = [r for r in records if r.model_id == model_id]
        return records

    def get_metrics(self) -> Dict[str, float]:
        return dict(self._metrics)

    def get_traces(self, trace_id: str = "") -> List[TelemetryRecord]:
        if trace_id:
            return [r for r in self._records if r.trace_id == trace_id]
        return list(self._records)
