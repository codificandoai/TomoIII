"""
Codificando.AI
UC-328: ORQUESTA-R — Orquestador Resiliente con Gestión de Sobrecarga.

Capa empresarial de orquestación de RAG. Gestiona latencia, costo,
fragmentación, esquemas heterogéneos, ambigüedades, contexto persistente,
privacidad y recuperación ante fallos a gran escala.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

from typing import Dict, Any, Callable, Optional, List

from orchestrator import OrquestaREngine
from orquesta_models import OrquestaConfig, OrquestaResult, Budget, PrivacyPolicy


class UCOrquestaRLayer:
    """
    Wrapper de alto nivel para UC-328 ORQUESTA-R.

    Puede usarse directamente o como capa de orquestación entre UC-326/UC-325
    y fuentes externas.
    """

    def __init__(self, config: Optional[OrquestaConfig] = None):
        self.config = config or OrquestaConfig()
        self.engine = OrquestaREngine(config=self.config)

    def orchestrate(
        self,
        query: str,
        context: str = "",
        user_region: str = "global",
        external_connectors: Optional[Dict[str, Callable[[str, Dict[str, Any]], Any]]] = None,
    ) -> OrquestaResult:
        """Punto de entrada principal para ejecutar ORQUESTA-R."""
        return self.engine.execute(
            query=query,
            context=context,
            user_region=user_region,
            external_connectors=external_connectors,
        )

    def register_source(
        self,
        data: Dict[str, Any],
        connector: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        """Registra una fuente externa."""
        source = self.engine.register_source(data, connector)
        return source.to_dict()

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas consolidadas."""
        return self.engine.get_statistics()

    def reset(self) -> None:
        """Resetea todo el estado."""
        self.engine.reset()


def default_sources() -> List[Dict[str, Any]]:
    """Fuentes de ejemplo para demo y tests."""
    return [
        {
            "name": "Bloomberg API",
            "source_type": "api",
            "endpoint": "https://api.bloomberg.com/v1/data",
            "cost_per_call": 0.50,
            "cost_per_kb": 0.01,
            "base_latency_ms": 250.0,
            "reliability": 0.95,
            "rate_limit": 10,
            "capabilities": ["fundamental", "news"],
            "tags": ["financial", "premium"],
        },
        {
            "name": "Twitter/X API",
            "source_type": "api",
            "endpoint": "https://api.twitter.com/2/tweets/search",
            "cost_per_call": 0.05,
            "cost_per_kb": 0.001,
            "base_latency_ms": 150.0,
            "reliability": 0.75,
            "rate_limit": 50,
            "capabilities": ["sentiment", "social_media"],
            "tags": ["social", "volatile"],
        },
        {
            "name": "SEC EDGAR",
            "source_type": "database",
            "endpoint": "https://www.sec.gov/edgar",
            "cost_per_call": 0.0,
            "cost_per_kb": 0.0,
            "base_latency_ms": 400.0,
            "reliability": 0.98,
            "rate_limit": 5,
            "capabilities": ["regulatory", "sec"],
            "tags": ["regulatory", "free"],
        },
    ]


def demo() -> None:
    """Demostración de UC-328 ORQUESTA-R."""
    print("=" * 80)
    print("UC-328 — ORQUESTA-R: Orquestador Resiliente de RAG Empresarial")
    print("=" * 80)

    config = OrquestaConfig(
        budget=Budget(max_cost=5.0, max_latency_ms=3000.0, max_concurrent_calls=5),
        privacy_policies=[PrivacyPolicy.GDPR],
    )
    layer = UCOrquestaRLayer(config=config)

    # Registro de conectores simulados
    def bloomberg_connector(query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "company": "TechCorp",
            "revenue": 1200.5,
            "pe_ratio": 22.3,
            "confidence": 0.92,
            "timestamp": "2024-01-15",
        }

    def twitter_connector(query: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"content": "Bullish on TechCorp earnings", "sentiment": 0.8},
            {"content": "Market cautious", "sentiment": -0.2},
        ]

    def sec_connector(query: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "filing": "10-K",
            "risk_factors": ["market volatility", "regulatory changes"],
            "confidence": 0.95,
        }

    for src in default_sources():
        layer.engine.sources.register_from_dict(src)

    layer.engine.sources.register_connector("Bloomberg API", bloomberg_connector)
    layer.engine.sources.register_connector("Twitter/X API", twitter_connector)
    layer.engine.sources.register_connector("SEC EDGAR", sec_connector)

    query = "Recommend technology stocks today based on fundamentals, news and social media sentiment"
    result = layer.orchestrate(query, context="aggressive technology portfolio", user_region="EU")

    print(f"\nQuery: {result.query}")
    print(f"Verdict: {result.verdict.value}")
    print(f"Confidence: {result.confidence:.3f}")
    print(f"Duration: {result.duration_ms:.2f} ms")
    print(f"Subqueries: {len(result.subqueries)}")
    print(f"Partial results: {len(result.partial_results)}")
    print(f"Resolved facts: {len(result.resolved_facts)}")
    print(f"\nAnswer:\n{result.answer}")
    print(f"\nWarnings: {result.warnings}")
    print(f"Recommendations: {result.recommendations}")
    print(f"\nMetrics: {result.metrics.to_dict()}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    demo()
