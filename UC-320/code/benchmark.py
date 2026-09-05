"""UC-320 — Benchmark de modelos: comparación paralela con métricas."""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from hf_gateway import HuggingFaceModelGateway, ModelResult


@dataclass
class BenchmarkResult:
    model_id: str
    provider: str
    text: str
    latency_ms: float
    cost_estimate: float
    success: bool
    error: Optional[str] = None
    request_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "text": self.text[:200],
            "latency_ms": round(self.latency_ms, 2),
            "cost_estimate": self.cost_estimate,
            "success": self.success,
            "error": self.error,
            "request_id": self.request_id,
        }


class ModelBenchmark:
    """Compara varios modelos con el mismo prompt en paralelo.

    UC-315 pide el benchmark; UC-317 ejecuta; UC-324 valida presupuesto,
    adversarial tests y promoción. El resultado es una evaluación, no una
    votación automática que ejecute una orden.
    """

    def __init__(self, gateway: HuggingFaceModelGateway, max_workers: int = 3) -> None:
        self.gateway = gateway
        self.max_workers = max_workers

    def _evaluate_one(
        self,
        model_id: str,
        provider: str,
        prompt: str,
        request_id: str,
    ) -> BenchmarkResult:
        try:
            result = self.gateway.chat(
                model_id=model_id,
                provider=provider,
                request_id=request_id,
                messages=[{"role": "user", "content": prompt}],
            )
            return BenchmarkResult(
                model_id=model_id,
                provider=provider,
                text=result.text,
                latency_ms=result.latency_ms,
                cost_estimate=result.cost_estimate,
                success=True,
                request_id=result.request_id,
            )
        except Exception as exc:
            return BenchmarkResult(
                model_id=model_id,
                provider=provider,
                text="",
                latency_ms=0.0,
                cost_estimate=0.0,
                success=False,
                error=str(exc),
                request_id=request_id,
            )

    def benchmark(
        self,
        prompt: str,
        models: Optional[List[Tuple[str, str]]] = None,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        tid = trace_id or f"bench_{uuid.uuid4().hex[:8]}"
        if models is None:
            models = [
                ("mock/sentiment-mock", "mock"),
                ("ProsusAI/finbert", "hf-inference"),
            ]

        results: List[BenchmarkResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(
                    self._evaluate_one,
                    model_id,
                    provider,
                    prompt,
                    f"{tid}:{i}",
                ): (model_id, provider)
                for i, (model_id, provider) in enumerate(models)
            }
            for future in as_completed(futures):
                results.append(future.result())

        # Ordenar por latencia ascendente.
        results.sort(key=lambda r: r.latency_ms)
        return [r.to_dict() for r in results]

    def compare(self, prompt: str, models: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
        """Retorna benchmark + análisis comparativo."""
        results = self.benchmark(prompt, models)
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        analysis = {
            "total_models": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "fastest": min(successful, key=lambda r: r["latency_ms"]) if successful else None,
            "cheapest": min(successful, key=lambda r: r["cost_estimate"]) if successful else None,
            "avg_latency_ms": sum(r["latency_ms"] for r in successful) / len(successful) if successful else 0,
            "avg_cost": sum(r["cost_estimate"] for r in successful) / len(successful) if successful else 0,
            "results": results,
        }
        return analysis
