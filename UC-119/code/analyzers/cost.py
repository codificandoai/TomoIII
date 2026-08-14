"""Métricas de coste y rendimiento: tokens, coste, TTFT, latencia,
tokens/segundo, errores y caché."""

from dataclasses import dataclass
from typing import Optional

from config import CONFIG


@dataclass
class CostPerformanceMetrics:
    """Métricas de coste y rendimiento de una solicitud."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    wasted_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    ttft_ms: float
    total_latency_ms: float
    tokens_per_second: float
    cache_hit: bool
    error_occurred: bool
    rate_limited: bool


class CostPerformanceAnalyzer:
    """Calcula coste y métricas de rendimiento de una solicitud al LLM."""

    def __init__(
        self,
        input_cost_per_1k: Optional[float] = None,
        output_cost_per_1k: Optional[float] = None,
        max_context_tokens: Optional[int] = None,
    ):
        self.input_cost_per_1k = input_cost_per_1k or CONFIG.cost.input_cost_per_1k
        self.output_cost_per_1k = output_cost_per_1k or CONFIG.cost.output_cost_per_1k
        self.max_context_tokens = max_context_tokens or CONFIG.cost.max_context_tokens

    def analyze(
        self,
        input_tokens: int,
        output_tokens: int,
        ttft_ms: float,
        total_latency_ms: float,
        cache_hit: bool = False,
        error_occurred: bool = False,
        rate_limited: bool = False,
        context_tokens_sent: Optional[int] = None,
    ) -> CostPerformanceMetrics:
        total_tokens = input_tokens + output_tokens

        wasted_tokens = 0
        if context_tokens_sent is not None and context_tokens_sent > self.max_context_tokens:
            wasted_tokens = context_tokens_sent - self.max_context_tokens

        input_cost = (input_tokens / 1000) * self.input_cost_per_1k
        output_cost = (output_tokens / 1000) * self.output_cost_per_1k
        total_cost = input_cost + output_cost

        generation_time_s = max((total_latency_ms - ttft_ms) / 1000, 1e-6)
        tokens_per_second = output_tokens / generation_time_s if output_tokens > 0 else 0.0

        return CostPerformanceMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            wasted_tokens=wasted_tokens,
            input_cost_usd=round(input_cost, 6),
            output_cost_usd=round(output_cost, 6),
            total_cost_usd=round(total_cost, 6),
            ttft_ms=round(ttft_ms, 2),
            total_latency_ms=round(total_latency_ms, 2),
            tokens_per_second=round(tokens_per_second, 2),
            cache_hit=cache_hit,
            error_occurred=error_occurred,
            rate_limited=rate_limited,
        )
