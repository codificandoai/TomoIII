"""
UC-326 — Validación operacional de MAQRI.

Verifica los 8 procesos principales:
1. Modelos de datos y configuración.
2. Memoria episódica.
3. Memoria semántica.
4. Memoria procedimental.
5. Refinamiento de queries con memoria.
6. Evaluación con Critic.
7. Cross-retrieval.
8. Motor MAQRI completo.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def validate_models():
    """Valida modelos de datos."""
    from maqri_models import (
        MaqriConfig, MaqriResult, MaqriIteration, SearchEpisode,
        RetrievedDocument, QueryVariant, ProceduralRule, CriticAssessment,
        WorkingMemory, MemoryType, QueryStrategy, RetrievalVerdict,
    )

    config = MaqriConfig()
    assert config.max_iterations == 5
    assert config.convergence_threshold == 0.85

    doc = RetrievedDocument(content="test", source="a")
    assert doc.fingerprint != ""

    episode = SearchEpisode(original_query="a", refined_query="b", relevance_score=0.8)
    assert episode.to_dict()["success"] is True

    assessment = CriticAssessment(relevance_score=0.8, coverage_score=0.7, novelty_score=0.6)
    assert assessment.overall_score > 0

    wm = WorkingMemory(original_goal="goal", accumulated_facts=["fact1"])
    assert wm.to_dict()["original_goal"] == "goal"

    return True


def validate_episodic_memory():
    """Valida memoria episódica."""
    from episodic_memory import EpisodicMemory
    from maqri_models import SearchEpisode

    mem = EpisodicMemory()
    ep1 = SearchEpisode(original_query="pricing", refined_query="pricing strategies", relevance_score=0.9)
    ep2 = SearchEpisode(original_query="cost", refined_query="cost optimization", relevance_score=0.3, failure_reason="too broad")
    mem.add(ep1)
    mem.add(ep2)

    assert len(mem) == 2
    assert len(mem.get_recent(2)) == 2

    similar = mem.find_similar("pricing strategies", top_k=2, threshold=0.3)
    assert len(similar) >= 1

    assert mem.is_redundant("pricing strategies", threshold=0.7) is True
    assert mem.is_redundant("machine learning", threshold=0.7) is False

    failed = mem.get_failed_strategies()
    assert len(failed) == 1

    return True


def validate_semantic_memory():
    """Valida memoria semántica."""
    from semantic_memory import SemanticMemory

    mem = SemanticMemory()
    mem.add_document("Dynamic pricing based on elasticity", source="pricing")
    mem.add_document("Competitor-based pricing", source="pricing")
    mem.add_document("LSTM demand prediction", source="ml")

    results = mem.retrieve("pricing", top_k=2)
    assert len(results) == 2
    assert all(r.source == "pricing" for r in results)

    stats = mem.get_stats()
    assert stats["total_documents"] == 3

    return True


def validate_procedural_memory():
    """Valida memoria procedimental."""
    from procedural_memory import ProceduralMemory

    mem = ProceduralMemory()
    assert len(mem.get_rules()) >= 4

    strategies = mem.get_recommended_strategies(num_results=2, avg_relevance=0.2)
    assert len(strategies) > 0

    active = mem.evaluate(num_results=1, avg_relevance=0.2)
    assert len(active) > 0

    return True


def validate_query_refiner():
    """Valida refinamiento de queries."""
    from query_refiner_326 import QueryRefiner326
    from episodic_memory import EpisodicMemory
    from procedural_memory import ProceduralMemory
    from maqri_models import SearchEpisode

    episodic = EpisodicMemory()
    episodic.add(SearchEpisode(
        original_query="pricing",
        refined_query="dynamic pricing strategies",
        relevance_score=0.9,
    ))

    refiner = QueryRefiner326(episodic=episodic)
    variants = refiner.generate_variants("pricing optimization", context="trading")
    assert len(variants) > 0
    assert any("pricing" in v.query.lower() for v in variants)

    variant = refiner.refine_from_failure(
        query="pricing",
        missing_info="implementation details",
        failure_reason="too broad",
        accumulated_facts=["Dynamic pricing uses elasticity"],
    )
    assert variant.query != ""

    return True


def validate_critic():
    """Valida módulo Critic."""
    from critic_evaluator import CriticEvaluator
    from maqri_models import RetrievedDocument, WorkingMemory

    critic = CriticEvaluator()
    docs = [
        RetrievedDocument(content="Dynamic pricing based on elasticity", source="a", score=0.8),
        RetrievedDocument(content="Competitor-based pricing", source="b", score=0.7),
    ]
    wm = WorkingMemory(accumulated_facts=[])
    assessment = critic.evaluate("pricing strategies", docs, wm)
    assert assessment.relevance_score > 0
    assert assessment.overall_score > 0

    continue_flag = critic.should_continue(assessment)
    assert isinstance(continue_flag, bool)

    return True


def validate_cross_retriever():
    """Valida cross-retrieval."""
    from cross_retriever import CrossRetriever
    from semantic_memory import SemanticMemory

    semantic = SemanticMemory()
    semantic.add_document("Dynamic pricing based on elasticity pricing strategies", source="pricing")

    cr = CrossRetriever(semantic=semantic)
    docs = cr.search("pricing strategies elasticity")
    assert len(docs) > 0

    def external_retriever(query, top_k):
        return [{"content": f"External: {query}", "source": "api", "score": 0.9}]

    cr.register_external_retriever("external", external_retriever)
    docs2 = cr.search("pricing")
    assert any(d.memory_type.value == "external" for d in docs2)

    return True


def validate_maqri_engine():
    """Valida motor MAQRI completo."""
    from maqri_engine import MaqriEngine
    from semantic_memory import SemanticMemory
    from maqri_models import RetrievalVerdict

    semantic = SemanticMemory()
    semantic.add_document("MAQRI improves iterative query refinement with memory", source="maqri")
    semantic.add_document("Episodic memory avoids redundant searches", source="memory")
    semantic.add_document("Critic evaluates retrieved documents", source="critic")

    engine = MaqriEngine(semantic=semantic)
    result = engine.search("How does MAQRI work?", context="building RAG", domain="agi", max_iterations=3)

    assert result.query != ""
    assert result.trace_id != ""
    assert result.iterations_executed > 0
    assert result.iterations_executed <= 3
    assert result.verdict in (
        RetrievalVerdict.CONVERGED,
        RetrievalVerdict.MAX_ITERATIONS,
    )
    assert result.duration_ms > 0
    assert isinstance(result.success, bool)

    return True


def main():
    """Ejecuta todas las validaciones."""
    print("=" * 70)
    print("UC-326 — Validación Operacional MAQRI")
    print("=" * 70)

    validations = [
        ("Modelos de datos y configuración", validate_models),
        ("Memoria episódica", validate_episodic_memory),
        ("Memoria semántica", validate_semantic_memory),
        ("Memoria procedimental", validate_procedural_memory),
        ("Refinamiento de queries con memoria", validate_query_refiner),
        ("Evaluación con Critic", validate_critic),
        ("Cross-retrieval", validate_cross_retriever),
        ("Motor MAQRI completo", validate_maqri_engine),
    ]

    all_ok = True
    for name, fn in validations:
        try:
            result = fn()
            status = "[OK]" if result else "[FAIL]"
            if not result:
                all_ok = False
        except Exception as e:
            status = "[FAIL]"
            all_ok = False
            print(f"  {status} {name}: {e}")
            continue
        print(f"  {status} {name}")

    print("=" * 70)
    if all_ok:
        print("  Todos los 8 procesos están funcionando correctamente.")
    else:
        print("  ALGUNOS PROCESOS FALLARON.")
        sys.exit(1)


if __name__ == "__main__":
    main()
