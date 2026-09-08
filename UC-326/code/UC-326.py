"""
Codificando.AI
UC-326: Refinamiento Iterativo de Consultas Aumentado por Memoria (MAQRI)

Capa de memoria y búsqueda inteligente del agente AGI.
- Indexa recuerdos, experiencias y conocimiento semántico.
- Recupera información cruzando memoria episódica, semántica y fuentes externas.
- Refina queries iterativamente usando aprendizaje de experiencias pasadas.
- Sirve como retriever inyectable para UC-325 (ReasoningLoopEngine).

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

from typing import List, Dict, Any, Callable, Optional

from maqri_engine import MaqriEngine
from maqri_models import (
    MaqriConfig,
    MaqriResult,
    SearchEpisode,
    RetrievedDocument,
    MemoryType,
)
from episodic_memory import EpisodicMemory
from semantic_memory import SemanticMemory


class UCMaqriLayer:
    """
    Wrapper de alto nivel para UC-326 como capa de memoria/búsqueda.

    Diseñado para ser inyectado en UC-325 como retriever:
        retriever = UCMaqriLayer()
        result = retriever.retrieve_with_context("query", context="...")
    """

    def __init__(
        self,
        config: Optional[MaqriConfig] = None,
        seed_kb: Optional[List[Dict[str, Any]]] = None,
    ):
        self.config = config or MaqriConfig()
        self.engine = MaqriEngine(config=self.config)

        # Sembrar base de conocimiento semántica si se proporciona
        if seed_kb:
            self.engine.semantic.add_documents(seed_kb)

    def retrieve_with_context(
        self,
        query: str,
        context: str = "",
        domain: str = "general",
        max_iterations: Optional[int] = None,
        agent_id: str = "",
        use_governed_memory: bool = True,
    ) -> MaqriResult:
        """
        Método principal para ser usado por UC-325.

        Recibe un query + contexto, ejecuta MAQRI, y retorna documentos
        refinados con metadata. Soporta memoria gobernada compartida.
        """
        return self.engine.search(
            query=query,
            context=context,
            domain=domain,
            max_iterations=max_iterations,
            agent_id=agent_id,
            use_governed_memory=use_governed_memory,
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Interfaz compatible con retriever simple para UC-325.

        Retorna lista de dicts con 'content', 'source', 'score', 'metadata'.
        """
        result = self.retrieve_with_context(query=query, **kwargs)
        return [d.to_dict() for d in result.docs[:top_k]]

    def add_documents(
        self,
        documents: List[Dict[str, Any]],
        source: str = "user",
    ) -> List[RetrievedDocument]:
        """Agrega documentos a la memoria semántica."""
        return self.engine.semantic.add_documents(documents, source=source)

    def add_experience(
        self,
        query: str,
        refined_query: str,
        docs: List[RetrievedDocument],
        relevance_score: float,
        missing_info: str = "",
        failure_reason: str = "",
    ) -> SearchEpisode:
        """Agrega una experiencia a la memoria episódica."""
        episode = SearchEpisode(
            original_query=query,
            refined_query=refined_query,
            retrieved_docs=docs,
            relevance_score=relevance_score,
            missing_info=missing_info,
            failure_reason=failure_reason,
        )
        self.engine.episodic.add(episode)
        return episode

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de la capa MAQRI."""
        return {
            "episodic": self.engine.episodic.get_statistics(),
            "semantic": self.engine.semantic.get_stats(),
            "observability": self.engine.get_observability_summary(),
            "history_count": len(self.engine._history),
        }

    def reset(self) -> None:
        """Resetea todo el estado."""
        self.engine.reset()


# ─── DEFAULT KNOWLEDGE BASE ─────────────────────────────────────────────────

def default_kb() -> List[Dict[str, Any]]:
    """Base de conocimiento de ejemplo para demo y tests."""
    return [
        {
            "content": "MAQRI es un motor de refinamiento iterativo de consultas aumentado por memoria episódica y semántica.",
            "source": "maqri_theory",
            "metadata": {"topic": "maqri"},
        },
        {
            "content": "La memoria episódica registra experiencias pasadas de búsqueda para evitar consultas redundantes.",
            "source": "episodic_memory",
            "metadata": {"topic": "memory"},
        },
        {
            "content": "La memoria semántica almacena conocimiento del dominio y permite recuperar documentos relevantes por similitud.",
            "source": "semantic_memory",
            "metadata": {"topic": "memory"},
        },
        {
            "content": "El módulo Critic evalúa si los documentos recuperados responden realmente a la pregunta del agente.",
            "source": "critic_module",
            "metadata": {"topic": "evaluation"},
        },
        {
            "content": "La divergencia forzada modifica la consulta para salir de mínimos locales cuando las búsquedas son redundantes.",
            "source": "divergence",
            "metadata": {"topic": "refinement"},
        },
        {
            "content": "Cross-retrieval combina resultados de memoria episódica, memoria semántica y fuentes externas.",
            "source": "cross_retrieval",
            "metadata": {"topic": "retrieval"},
        },
        {
            "content": "UC-325 utiliza a UC-326 como sistema de memoria y búsqueda inteligente para obtener antecedentes relevantes.",
            "source": "architecture",
            "metadata": {"topic": "integration"},
        },
        {
            "content": "Los patrones de reescritura exitosos se aprenden y reutilizan para refinar consultas futuras.",
            "source": "learning",
            "metadata": {"topic": "meta-learning"},
        },
        {
            "content": "Un agente RAG agentivo no solo busca en un manual, sino que recuerda qué funcionó antes y mejora sus preguntas.",
            "source": "agentive_rag",
            "metadata": {"topic": "agent"},
        },
        {
            "content": "La memoria de trabajo mantiene hechos acumulados, hipótesis activas y enfoques fallidos durante una sesión.",
            "source": "working_memory",
            "metadata": {"topic": "memory"},
        },
    ]


# ─── DEMO ───────────────────────────────────────────────────────────────────

def demo() -> None:
    """Demostración de UC-326 MAQRI."""
    print("=" * 80)
    print("UC-326 — MAQRI: Sistema de Memoria y Búsqueda Inteligente")
    print("=" * 80)

    layer = UCMaqriLayer(seed_kb=default_kb())

    queries = [
        "¿Cómo mejora MAQRI el refinamiento iterativo de consultas?",
        "¿Cuál es el papel de la memoria episódica en RAG agentivo?",
    ]

    for query in queries:
        print(f"\n{'─' * 80}")
        print(f"Query: {query}")
        print(f"{'─' * 80}")

        result = layer.retrieve_with_context(
            query=query,
            context="Estamos construyendo una capa de razonamiento que necesita memoria.",
            domain="agi",
            max_iterations=3,
        )

        print(f"\n  Verdict:          {result.verdict.value}")
        print(f"  Final query:      {result.final_query[:100]}")
        print(f"  Iterations:       {result.iterations_executed}")
        print(f"  Docs returned:    {len(result.docs)}")
        print(f"  Final score:      {result.final_score:.3f}")
        print(f"  Duration:         {result.duration_ms:.1f} ms")
        print(f"  Success:          {result.success}")

        if result.docs:
            print("\n  Top documents:")
            for i, doc in enumerate(result.docs[:3], 1):
                print(f"    {i}. [{doc.memory_type.value}] {doc.content[:80]}... (score: {doc.score:.3f})")

        if result.iterations:
            last = result.iterations[-1]
            print(f"\n  Last iteration assessment:")
            if last.assessment:
                a = last.assessment
                print(f"    relevance={a.relevance_score:.3f}, coverage={a.coverage_score:.3f}, "
                      f"novelty={a.novelty_score:.3f}, confidence={a.confidence:.3f}")

    print(f"\n{'─' * 80}")
    print("MAQRI Stats:")
    stats = layer.get_stats()
    print(f"  Episodic memory:  {stats['episodic']}")
    print(f"  Semantic memory:  {stats['semantic']}")
    print("=" * 80)


if __name__ == "__main__":
    demo()
