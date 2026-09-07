"""
Codificando.AI
UC-329: GraphRAG-GoT — Razonamiento sobre Grafos de Conocimiento.

Capa externa especializada en razonamiento sobre grafos para UTRON.ai AGI.
Convierte la cadena de pensamiento de secuencia/árbol frágil en una red
robusta de hipótesis interconectadas, ancladas en evidencia y explorable.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

from typing import Dict, Any, List, Optional

from orchestrator_329 import GraphRAGGoTEngine
from graph_models import GraphRAGGoTConfig, GraphRAGGoTResult


class UCGraphRAGGoTLayer:
    """
    Wrapper de alto nivel para UC-329 GraphRAG-GoT.

    Puede usarse directamente o invocado por UC-325 cuando el razonamiento
    requiere exploración estructurada de entidades y relaciones.
    """

    def __init__(self, config: Optional[GraphRAGGoTConfig] = None):
        self.config = config or GraphRAGGoTConfig()
        self.engine = GraphRAGGoTEngine(config=self.config)

    def ingest(
        self,
        text: str,
        source_id: Optional[str] = None,
        domain: str = "default",
    ) -> Dict[str, Any]:
        """Ingesta evidencia textual al grafo de conocimiento."""
        return self.engine.ingest(text, source_id=source_id, domain=domain)

    def reason(
        self,
        query: str,
        context: str = "",
        domain: str = "default",
    ) -> GraphRAGGoTResult:
        """Ejecuta GraphRAG-GoT sobre el conocimiento almacenado."""
        return self.engine.reason(query, context=context, domain=domain)

    def feedback(
        self,
        trace_id: str,
        outcome: str,
        intensity: float = 1.0,
    ) -> Dict[str, Any]:
        """Envía retroalimentación sobre un resultado."""
        return self.engine.feedback(trace_id, outcome, intensity)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas del motor."""
        return self.engine.get_statistics()

    def reset(self) -> None:
        """Resetea todo el estado."""
        self.engine.reset()


def demo() -> None:
    """Demostración de UC-329 GraphRAG-GoT."""
    print("=" * 80)
    print("UC-329 — GraphRAG-GoT: Razonamiento sobre Grafos de Conocimiento")
    print("=" * 80)

    layer = UCGraphRAGGoTLayer(
        config=GraphRAGGoTConfig(
            max_search_depth=3,
            top_k_paths=3,
            relevance_threshold=0.1,
        )
    )

    # Vocabulario de dominio para mejorar extracción en el demo
    layer.engine.entity_extractor.add_vocabulary([
        "solar subsidy", "production cost", "Chinese competitor", "panel efficiency",
        "TSMC", "Germany", "Japan", "Chinese competition", "technology improvement",
        "solar panel", "customers", "profitability", "margin compression",
    ])

    # Ingesta de evidencia
    evidence = [
        "Solar subsidy of 30% (2026-2030) reduces costs for customers.",
        "Current production cost is 0.15 USD per Watt.",
        "Chinese competitor reduces prices 10% per year.",
        "Panel efficiency improves 0.5% per year.",
        "TSMC diversifies manufacturing to Germany and Japan.",
    ]
    for i, text in enumerate(evidence):
        layer.ingest(text, source_id=f"doc_{i}", domain="energy")

    # Ingesta de relaciones más complejas
    layer.ingest(
        "Chinese competition causes margin compression for local manufacturers.",
        source_id="analysis_1",
        domain="energy",
    )
    layer.ingest(
        "Technology improvement reduces solar panel production costs.",
        source_id="analysis_2",
        domain="energy",
    )

    query = (
        "How would the new solar subsidy policy affect profitability "
        "considering international competition and technological advances?"
    )
    result = layer.reason(query, domain="energy")

    print(f"\nQuery: {result.query}")
    print(f"Answer:\n{result.answer}")
    print(f"\nNarrative:\n{result.narrative}")
    print(f"\nMetrics: {result.metrics.to_dict()}")
    print(f"\nContradictions: {result.contradictions}")
    print(f"\nRecommendations: {result.recommendations}")
    print(f"\nUncertainties: {result.uncertainties}")
    print(f"\nThought graph: {result.thought_graph.get('node_count', 0)} nodes, "
          f"{result.thought_graph.get('edge_count', 0)} edges")
    print(f"\nDuration: {result.duration_ms:.2f} ms")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    demo()
