from analyzers.cost import CostPerformanceAnalyzer


def test_cost_calculation_basic():
    analyzer = CostPerformanceAnalyzer(input_cost_per_1k=1.0, output_cost_per_1k=2.0)
    result = analyzer.analyze(
        input_tokens=1000,
        output_tokens=1000,
        ttft_ms=100.0,
        total_latency_ms=1100.0,
    )
    assert result.input_cost_usd == 1.0
    assert result.output_cost_usd == 2.0
    assert result.total_cost_usd == 3.0
    assert result.total_tokens == 2000


def test_tokens_per_second_uses_generation_time_excluding_ttft():
    analyzer = CostPerformanceAnalyzer()
    result = analyzer.analyze(
        input_tokens=10,
        output_tokens=100,
        ttft_ms=100.0,
        total_latency_ms=1100.0,  # 1000ms de generación tras el TTFT
    )
    assert result.tokens_per_second == 100.0


def test_wasted_tokens_when_context_exceeds_limit():
    analyzer = CostPerformanceAnalyzer(max_context_tokens=100)
    result = analyzer.analyze(
        input_tokens=10,
        output_tokens=10,
        ttft_ms=50.0,
        total_latency_ms=200.0,
        context_tokens_sent=150,
    )
    assert result.wasted_tokens == 50


def test_cache_hit_flag_propagated():
    analyzer = CostPerformanceAnalyzer()
    result = analyzer.analyze(
        input_tokens=1, output_tokens=1, ttft_ms=1.0, total_latency_ms=10.0, cache_hit=True
    )
    assert result.cache_hit is True
